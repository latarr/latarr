import os
import re
import json
import time
import xbmc
import xbmcaddon
import xbmcvfs

addon = xbmcaddon.Addon()

_CURRENT_PLAYBACK = None

def set_current_playback(item_data):
    """Almacena en memoria el ítem que se está reproduciendo actualmente."""
    global _CURRENT_PLAYBACK
    _CURRENT_PLAYBACK = item_data
    xbmc.log(f"[LATARR] Sesión de reproducción registrada: {item_data.get('title')}", xbmc.LOGINFO)

def get_current_playback():
    """Obtiene el ítem de la sesión actual."""
    global _CURRENT_PLAYBACK
    return _CURRENT_PLAYBACK

def clear_current_playback():
    """Limpia la sesión de reproducción actual."""
    global _CURRENT_PLAYBACK
    _CURRENT_PLAYBACK = None

def _get_history_path():
    """Ruta del archivo local history.json en el perfil de usuario de Kodi."""
    profile_dir = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir, exist_ok=True)
    return os.path.join(profile_dir, 'history.json')

def get_history():
    """Obtiene la lista de elementos pendientes ordenados por fecha descendente sin duplicados."""
    path = _get_history_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                # Limpiar posibles duplicados por ID o título
                seen_ids = set()
                deduped = []
                for item in sorted(data, key=lambda x: x.get('updated_at', 0), reverse=True):
                    iid = item.get('id') or item.get('tmdb_id') or item.get('title')
                    if iid and iid not in seen_ids:
                        seen_ids.add(iid)
                        deduped.append(item)
                return deduped
    except Exception as e:
        xbmc.log(f"[LATARR] Error leyendo historial: {str(e)}", xbmc.LOGERROR)
    return []

def save_progress(item_data, current_time, total_time, file_name=None, file_index=None):
    """
    Guarda o actualiza el progreso de un video.
    - Menos del 3%: se ignora (salida accidental), se conserva lo que hubiera.
    - 90% o más:
        * Películas: se eliminan del historial (ya la terminaste).
        * Series y anime: se CONSERVAN, marcadas como 'finished', para recordar
          hasta qué capítulo llegaste (una sola entrada por título).
    - Entre 3% y 90%: se guarda actualizando el ítem existente sin duplicar.
    """
    if not total_time or total_time <= 0:
        return
    
    current_time = float(current_time or 0)
    total_time = float(total_time)
    percent = (current_time / total_time) * 100.0

    unique_id = _generate_id(item_data, file_name, file_index)
    tmdb_id = str(item_data.get('tmdb_id') or '').strip()
    history = get_history()

    media_type = item_data.get('media_type', 'movies')
    is_series = media_type in ('series', 'anime')
    finished = percent >= 90.0

    # Película terminada: sale del historial. Serie/anime terminado: se queda como "completado"
    if finished and not is_series:
        xbmc.log(f"[LATARR] Película completada ({percent:.1f}% >= 90%). Eliminando de historial: {unique_id}", xbmc.LOGINFO)
        delete_item(unique_id)
        return

    # Si vio menos del 3%, no se guarda marca
    if not finished and percent < 3.0:
        xbmc.log(f"[LATARR] Video ignorado ({percent:.1f}% < 3%): {unique_id}", xbmc.LOGINFO)
        return

    # Formatear tiempos legibles (MM:SS o HH:MM:SS)
    curr_str = _format_seconds(current_time)
    tot_str = _format_seconds(total_time)
    rem_sec = max(0, total_time - current_time)
    rem_str = _format_seconds(rem_sec)
    time_display = f"{curr_str} / {tot_str} ({int(percent)}%)"
    progress_text = "Capítulo completado" if finished else f"Te quedaste en el minuto {curr_str}  •  Restan {rem_str}"

    entry = {
        'id': unique_id,
        'tmdb_id': tmdb_id,
        'media_type': media_type,
        'title': item_data.get('title') or 'Sin Título',
        'display_title': item_data.get('display_title') or item_data.get('title') or 'Sin Título',
        'poster': item_data.get('poster') or '',
        'fanart': item_data.get('fanart') or '',
        'plot': item_data.get('plot') or '',
        'year': str(item_data.get('year') or ''),
        'rating': str(item_data.get('rating') or '7.0'),
        'genre': str(item_data.get('genre') or 'Cine'),
        'magnet': item_data.get('magnet') or '',
        'file_name': file_name or item_data.get('file_name'),
        'file_index': file_index if file_index is not None else item_data.get('file_index'),
        'season': item_data.get('season'),
        'episode': item_data.get('episode'),
        'episode_label': episode_label(item_data.get('season'), item_data.get('episode')),
        'current_time': current_time,
        'total_time': total_time,
        'percent': min(100, int(percent)),
        'finished': bool(finished),
        'resume_time': curr_str,
        'remaining_time': rem_str,
        'time_display': time_display,
        'progress_text': progress_text,
        'updated_at': time.time()
    }

    # Descartar cualquier versión anterior del mismo contenido (por ID, tmdb_id o título)
    updated = [entry]
    for h in history:
        # Si coincide el ID único
        if h.get('id') == unique_id:
            continue
        # Si es la misma serie o película por tmdb_id
        if tmdb_id and str(h.get('tmdb_id') or '').strip() == tmdb_id:
            continue
        # Si coincide el título base
        if h.get('title') and entry.get('title') and h.get('title').strip().lower() == entry.get('title').strip().lower():
            continue
        updated.append(h)

    # Limitar a máximo 30 elementos
    updated = updated[:30]

    _write_history(updated)
    xbmc.log(f"[LATARR] Progreso actualizado: {entry['display_title']} ({int(percent)}%) [ID: {unique_id}]", xbmc.LOGINFO)

def delete_item(unique_id):
    """Elimina un ítem del historial por su identificador único o tmdb_id."""
    history = get_history()
    filtered = [h for h in history if h.get('id') != unique_id and str(h.get('tmdb_id') or '') != unique_id]
    _write_history(filtered)
    xbmc.log(f"[LATARR] Ítem eliminado del historial: {unique_id}", xbmc.LOGINFO)

def clear_all():
    """Vacía por completo el historial."""
    _write_history([])
    xbmc.log("[LATARR] Historial vaciado por el usuario", xbmc.LOGINFO)

def _write_history(data):
    path = _get_history_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        xbmc.log(f"[LATARR] Error guardando historial: {str(e)}", xbmc.LOGERROR)

def _generate_id(item_data, file_name=None, file_index=None):
    """
    Genera un ID único por contenido:
    - Una serie/anime siempre tiene un único ID (ej: tv_73375).
    - Una película siempre tiene un único ID (ej: movie_1022789).
    """
    if item_data.get('id'):
        return str(item_data['id'])

    tmdb_id = str(item_data.get('tmdb_id') or '').strip()
    media_type = item_data.get('media_type', 'movies')

    if tmdb_id:
        if media_type in ('series', 'anime'):
            return f"tv_{tmdb_id}"
        return f"movie_{tmdb_id}"

    clean_title = (item_data.get('title') or 'unknown').lower().strip()
    if media_type in ('series', 'anime'):
        return f"tv_{clean_title}"
    return f"movie_{clean_title}"

def parse_episode(text):
    """
    Saca (temporada, episodio) del nombre de un archivo de video.
    Devuelve (None, None) si no encuentra nada fiable.
    Soporta: S01E04, S01.E04, 1x04, "Temporada 1 Capitulo 4", "Episodio 4",
    E04 / EP04 y la numeración típica de anime: "Serie - 04 (1080p)", "[04]".
    """
    if not text:
        return (None, None)
    name = str(text).replace('\\', '/').split('/')[-1]
    name = re.sub(r'\.(mkv|mp4|avi|m4v|mov|wmv|ts|webm)$', '', name, flags=re.I)
    name = name.replace('_', ' ')

    # 1) S01E04 (con separadores opcionales); se toma el primer episodio si hay varios
    m = re.search(r'(?<![A-Za-z])S(\d{1,2})\s*[ ._-]?\s*E(\d{1,3})(?!\d)', name, re.I)
    if m:
        return (int(m.group(1)), int(m.group(2)))

    # 2) 1x04
    m = re.search(r'(?<!\d)(\d{1,2})x(\d{2,3})(?!\d|p)', name, re.I)
    if m:
        return (int(m.group(1)), int(m.group(2)))

    # 3) "Temporada 1 ... Capitulo 4" / "Season 1 ... Episode 4"
    m = re.search(r'(?:temporada|season|temp)\s*(\d{1,2}).{0,20}?(?:episodio|capitulo|capítulo|episode|cap|ep)\.?\s*(\d{1,3})', name, re.I)
    if m:
        return (int(m.group(1)), int(m.group(2)))

    # Limpiar ruido que se confunde con números (resolución, códecs, años, hashes)
    clean = re.sub(r'\[[0-9A-Fa-f]{8}\]', ' ', name)
    clean = re.sub(r'(?i)\b\d{3,4}\s*[pi]\b', ' ', clean)
    clean = re.sub(r'(?i)\b[xh]\.?26[45]\b|\bhevc\b|\bav1\b|\b(?:aac|ac3|dts|eac3|flac)\d?(?:\.\d)?\b|\b\d(?:\.\d)\b|\b\d{1,2}\s*bits?\b', ' ', clean)
    clean = re.sub(r'[\(\[]\s*(?:19|20)\d{2}\s*[\)\]]|\b(?:19|20)\d{2}\b', ' ', clean)

    # 4) "Episodio 4", "Capitulo 4", "Cap 4", "EP04", "E04"
    m = re.search(r'(?i)(?:episodio|capitulo|capítulo|episode|cap|ep)\.?\s*(\d{1,3})(?!\d)', clean)
    if m:
        return (None, int(m.group(1)))
    m = re.search(r'(?<![A-Za-z0-9])E(\d{1,3})(?![A-Za-z0-9])', clean)
    if m:
        return (None, int(m.group(1)))

    # 5) Anime: "Serie - 04", "Serie - 04v2", "[04]"
    m = re.search(r'\s-\s*(\d{1,3})(?:v\d)?(?=\s|\[|\(|\.|$)', clean)
    if m:
        return (None, int(m.group(1)))
    m = re.search(r'\[(\d{2,3})(?:v\d)?\]', clean)
    if m:
        return (None, int(m.group(1)))

    return (None, None)

def episode_label(season, episode):
    """'S01E04' si hay temporada, 'E04' si solo hay episodio, '' si no hay nada."""
    try:
        ep = int(episode)
    except (ValueError, TypeError):
        return ''
    if ep <= 0:
        return ''
    try:
        sn = int(season)
    except (ValueError, TypeError):
        sn = 0
    if sn == 0:
        return f"Especial {ep}"
    return f"S{sn:02d}E{ep:02d}"

def _format_seconds(seconds):
    try:
        seconds = int(float(seconds))
    except (ValueError, TypeError):
        return "00:00"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
