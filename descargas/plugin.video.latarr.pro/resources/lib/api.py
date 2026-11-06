import os
import json
import urllib.parse
import xbmc
import xbmcvfs
import xbmcgui
import xbmcaddon

try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError
except ImportError:
    from urllib2 import urlopen, Request, URLError

addon = xbmcaddon.Addon()
POSTER_BASE = "https://image.tmdb.org/t/p/w500"
FANART_BASE = "https://image.tmdb.org/t/p/w1280"

# ── URL base del catalogo (Cloudflare Pages CDN) ──
GITHUB_RAW = addon.getSetting('github_url').rstrip('/')
if not GITHUB_RAW:
    GITHUB_RAW = "https://latarr-repo.pages.dev"

# ── Cache en memoria ──
_CACHE = {}

def clear_cache():
    global _CACHE
    _CACHE.clear()


def _fetch_json(url, timeout=15, use_cache=True):
    """Descarga un JSON desde Cloudflare Pages CDN y lo cachea en memoria."""
    if use_cache and url in _CACHE:
        return _CACHE[url]
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*'
        }
        req = Request(url, headers=headers)
        resp = urlopen(req, timeout=timeout)
        data = json.loads(resp.read().decode('utf-8'))
        if use_cache and data is not None:
            _CACHE[url] = data
        return data
    except Exception as e:
        xbmc.log(f"[LATARR-GH] Error descargando {url}: {e}", xbmc.LOGERROR)
        return None


def _github(path):
    """Construye la URL completa de un archivo en el repo."""
    return f"{GITHUB_RAW}/{path}"


# ══════════════════════════════════════════════════
# CATALOGO COMPLETO (se descarga 1 vez y se filtra local)
# ══════════════════════════════════════════════════

def _load_catalog(media_type):
    """Carga el JSON completo de peliculas/series/anime."""
    filemap = {
        'movies': 'peliculas.json',
        'series': 'series.json',
        'anime': 'anime.json',
    }
    filename = filemap.get(media_type, 'peliculas.json')
    return _fetch_json(_github(filename)) or []


def _normalize(text):
    """Minusculas sin tildes para busqueda."""
    if not text:
        return ''
    import unicodedata
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


# ══════════════════════════════════════════════════
# PELICULAS
# ══════════════════════════════════════════════════

def get_top_movies(limit=25):
    data = _fetch_json(_github('top_movies.json'))
    return (data or [])[:limit]

def get_recent_movies(year=None, limit=25):
    catalog = _load_catalog('movies')
    if year:
        catalog = [m for m in catalog if str(m.get('year', '')) == str(year)]
    return catalog[:limit]

def get_movies_by_genre(genre, limit=25):
    catalog = _load_catalog('movies')
    norm_genre = _normalize(genre)
    filtered = [m for m in catalog if _normalize(m.get('genre', '')) == norm_genre]
    return filtered[:limit]

def get_movie_detail(tmdb_id):
    return _fetch_json(_github(f'links/movies/{tmdb_id}.json'))

def search_all(query, media_type='movies', limit=30):
    """Busca en el catalogo descargado filtrando por titulo."""
    catalog = _load_catalog(media_type)
    q = _normalize(query)
    results = [
        item for item in catalog
        if q in _normalize(item.get('clean_title', ''))
        or q in _normalize(item.get('title', ''))
    ]
    return {"total": len(results), "limit": limit, "offset": 0, "results": results[:limit]}

def get_catalog_years(media_type='movies'):
    filemap = {
        'movies': 'movies_years.json',
        'series': 'series_years.json',
        'anime': 'anime_years.json',
    }
    return _fetch_json(_github(filemap.get(media_type, 'movies_years.json'))) or []

def get_catalog_genres(media_type='movies', year=None):
    filemap = {
        'movies': 'movies_genres.json',
        'series': 'series_genres.json',
        'anime': 'anime_genres.json',
    }
    return _fetch_json(_github(filemap.get(media_type, 'movies_genres.json'))) or []

def get_catalog_items(media_type='movies', year=None, genre=None, offset=0, limit=40):
    """Carga catalogo completo y filtra/pagina localmente."""
    catalog = _load_catalog(media_type)

    if year and year != 'Todos':
        catalog = [i for i in catalog if str(i.get('year', '')) == str(year)]
    if genre and genre != 'Todos':
        norm_genre = _normalize(genre)
        catalog = [i for i in catalog if _normalize(i.get('genre', '')) == norm_genre]

    total = len(catalog)
    page = catalog[offset:offset + limit]
    return {"total": total, "limit": limit, "offset": offset, "results": page}


# ══════════════════════════════════════════════════
# SERIES
# ══════════════════════════════════════════════════

def get_top_series(limit=25):
    data = _fetch_json(_github('top_series.json'))
    return (data or [])[:limit]

def get_serie_detail(tmdb_id):
    return _fetch_json(_github(f'links/series/{tmdb_id}.json'))


# ══════════════════════════════════════════════════
# ANIME
# ══════════════════════════════════════════════════

def get_top_anime(limit=25):
    data = _fetch_json(_github('top_anime.json'))
    return (data or [])[:limit]

def get_anime_detail(tmdb_id, anime_type='series'):
    return _fetch_json(_github(f'links/anime/{tmdb_id}.json'))


# ══════════════════════════════════════════════════
# ACTORES
# ══════════════════════════════════════════════════

def get_actors(min_movies=5):
    data = _fetch_json(_github('actors.json'), use_cache=False) or []
    return [entry.get('actor', {}) for entry in data
            if len(entry.get('movies', [])) >= min_movies]

def get_actor_movies(actor_id):
    data = _fetch_json(_github('actors.json')) or []
    for entry in data:
        actor = entry.get('actor', {})
        aid = actor.get('id') or actor.get('actor_id')
        if aid == actor_id:
            movies = entry.get('movies', [])
            return {"total": len(movies), "results": movies}
    return {"total": 0, "results": []}


# ══════════════════════════════════════════════════
# TELEVISIÓN EN VIVO
# ══════════════════════════════════════════════════

def _fetch_local_or_remote(rel_path, use_cache=True):
    """Carga desde disco local si existe (para pruebas directas), o desde Cloudflare CDN."""
    # 1. Buscar en disco local si existe
    local_dev = os.path.join(r"C:\API LATAR\github_edition  PRO\catalogo", rel_path.replace('/', os.sep))
    if os.path.exists(local_dev):
        try:
            with open(local_dev, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            xbmc.log(f"[LATARR-TV] Error leyendo local {local_dev}: {e}", xbmc.LOGWARNING)
            
    # 2. Descargar desde Cloudflare CDN
    return _fetch_json(_github(rel_path), use_cache=use_cache)



# ═══════════════════════════════════════════════════════════════════
# DEPORTES PRO — Pool de cuentas IPTV con rotación automática
# ═══════════════════════════════════════════════════════════════════

import threading

_pool_lock = threading.Lock()
_pool_index = [0]  # índice rotativo de cuenta activa


def _load_pool():
    """Carga el pool de cuentas desde el JSON local del addon."""
    pool_path = os.path.join(
        addon.getAddonInfo('path'),
        'catalogo', 'tv', 'pool_cuentas.json'
    )
    pool_path = os.path.normpath(pool_path)
    try:
        with open(pool_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        xbmc.log(f"[LATARR-PRO] Error cargando pool: {e}", xbmc.LOGERROR)
        return {"servidores": [], "cuentas": []}



# ── Mapeo de categoría interna → category_id del servidor IPTV (mallorca.plus) ──
# Las 6 copas se consultan EN VIVO al servidor; DEPORTES PREMIUM lee del JSON local.
SPORTS_CAT_LIVE_IDS = {
    'champions_league':    358,
    'copa_libertadores':   233,
    'copa_sudamericana':   234,
    'europa_league':       230,
    'conference_league':   431,
    'premier_league':      225,
}


def get_sports_channels_live(server_cat_id):
    """
    Consulta al servidor IPTV en tiempo real los canales de una categoría.
    Usa la primera cuenta activa del pool en el primer servidor.
    Devuelve lista de dicts con 'nombre', 'stream_id', 'logo'.
    Si falla, devuelve lista vacía (el llamador hará fallback al JSON local).
    """
    try:
        pool = _load_pool()
        servidores = pool.get('servidores', [])
        cuentas    = pool.get('cuentas', [])

        if not servidores or not cuentas:
            xbmc.log('[LATARR-PRO] get_sports_channels_live: pool vacio', xbmc.LOGWARNING)
            return []

        servidor = servidores[0].rstrip('/')
        with _pool_lock:
            idx = _pool_index[0] % len(cuentas)
        cuenta = cuentas[idx]
        usuario = cuenta['username']
        clave   = cuenta['password']

        url = (
            f"{servidor}/player_api.php"
            f"?username={usuario}&password={clave}"
            f"&action=get_live_streams&category_id={server_cat_id}"
        )

        xbmc.log(f'[LATARR-PRO] Live fetch categoria {server_cat_id} → {servidor}', xbmc.LOGINFO)

        from urllib.request import urlopen, Request
        req  = Request(url, headers={'User-Agent': 'LATARR PRO/2.0'})
        resp = urlopen(req, timeout=15)
        raw  = json.loads(resp.read().decode('utf-8'))

        canales = []
        for ch in (raw or []):
            nombre    = ch.get('name', '') or ch.get('stream_display_name', '')
            stream_id = ch.get('stream_id') or ch.get('id')
            logo      = ch.get('stream_icon', '') or ch.get('thumbnail', '')
            if stream_id:
                canales.append({
                    'nombre':    nombre,
                    'stream_id': stream_id,
                    'logo':      logo,
                })

        xbmc.log(f'[LATARR-PRO] Live fetch OK: {len(canales)} canales en categoria {server_cat_id}', xbmc.LOGINFO)
        return canales

    except Exception as e:
        xbmc.log(f'[LATARR-PRO] get_sports_channels_live ERROR cat {server_cat_id}: {e}', xbmc.LOGERROR)
        return []


def get_sports_categories():
    """Devuelve las 7 categorías deportivas PRO (sin los canales, solo metadatos)."""
    sports_path = os.path.join(
        addon.getAddonInfo('path'),
        'catalogo', 'tv', 'deportes_pro.json'
    )
    sports_path = os.path.normpath(sports_path)
    try:
        with open(sports_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        cats = data.get('categorias', [])
        # Devolver sin la lista completa de canales (solo metadatos para la cuadrícula)
        return [{k: v for k, v in c.items() if k != 'canales'} for c in cats]
    except Exception as e:
        xbmc.log(f"[LATARR-PRO] Error cargando deportes_pro.json: {e}", xbmc.LOGERROR)
        return []


def get_sports_channels(category_id):
    """
    Devuelve los canales de una categoría deportiva.

    - 'deportes_premium' → lee del JSON local (estático, rápido, sin red)
    - Las 6 copas         → consulta en VIVO al servidor IPTV (siempre actualizado)
                            con fallback al JSON local si la red falla.
    """
    # ── Leer JSON local (sirve como fuente para Premium y como fallback para copas) ──
    sports_path = os.path.normpath(os.path.join(
        addon.getAddonInfo('path'),
        'catalogo', 'tv', 'deportes_pro.json'
    ))
    canales_local = []
    try:
        with open(sports_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for cat in data.get('categorias', []):
            if cat.get('id') == category_id:
                canales_local = cat.get('canales', [])
                break
    except Exception as e:
        xbmc.log(f'[LATARR-PRO] Error leyendo JSON local para {category_id}: {e}', xbmc.LOGWARNING)

    # ── DEPORTES PREMIUM: siempre desde JSON local (rápido, sin red) ──
    if category_id == 'deportes_premium':
        return canales_local

    # ── Las 6 copas: consulta EN VIVO al servidor IPTV ──
    server_cat_id = SPORTS_CAT_LIVE_IDS.get(category_id)
    if server_cat_id is None:
        xbmc.log(f'[LATARR-PRO] category_id desconocido: {category_id}', xbmc.LOGWARNING)
        return canales_local  # fallback seguro

    canales_live = get_sports_channels_live(server_cat_id)

    if canales_live:
        return canales_live
    else:
        # Red no disponible o error → usar datos del JSON local como respaldo
        xbmc.log(f'[LATARR-PRO] Fallback a JSON local para {category_id}', xbmc.LOGWARNING)
        return canales_local


def get_pool_stream_url(stream_id):
    """
    Genera la URL de stream usando el pool de cuentas con rotación automática.
    Prueba: cuenta actual en servidor 1, si falla → servidor 2, si falla → siguiente cuenta.
    Devuelve (url_principal, [url_alternativa, ...])
    """
    pool = _load_pool()
    cuentas = pool.get('cuentas', [])
    servidores = pool.get('servidores', ['http://mallorca.plus:80'])

    if not cuentas or not servidores:
        return None, []

    with _pool_lock:
        idx = _pool_index[0] % len(cuentas)

    cuenta = cuentas[idx]
    u = cuenta['username']
    p = cuenta['password']

    # URL principal: servidor 1 con cuenta actual
    url_principal = f"{servidores[0]}/live/{u}/{p}/{stream_id}.m3u8"

    # Alternativas: servidor 2 misma cuenta + server 1 con siguiente cuenta
    alternativas = []
    if len(servidores) > 1:
        alternativas.append(f"{servidores[1]}/live/{u}/{p}/{stream_id}.m3u8")

    next_idx = (idx + 1) % len(cuentas)
    next_cuenta = cuentas[next_idx]
    u2 = next_cuenta['username']
    p2 = next_cuenta['password']
    alternativas.append(f"{servidores[0]}/live/{u2}/{p2}/{stream_id}.m3u8")
    if len(servidores) > 1:
        alternativas.append(f"{servidores[1]}/live/{u2}/{p2}/{stream_id}.m3u8")

    return url_principal, alternativas


def rotate_pool_account():
    """Avanza al siguiente índice de cuenta en el pool (llamar cuando falla una cuenta)."""
    pool = _load_pool()
    total = len(pool.get('cuentas', [1]))
    with _pool_lock:
        _pool_index[0] = (_pool_index[0] + 1) % total
    xbmc.log(f"[LATARR-PRO] Pool rotado → cuenta #{_pool_index[0]}", xbmc.LOGINFO)

def get_tv_countries():
    """Obtiene la lista de países disponibles con sus totales de canales."""
    data = _fetch_local_or_remote('tv/paises.json', use_cache=True)
    return data.get('paises', []) if data else []


def get_tv_channels(country_code='CL'):
    """Obtiene los canales y categorías de un país específico."""
    country_code = (country_code or 'CL').upper()
    data = _fetch_local_or_remote(f'tv/tv_{country_code}.json', use_cache=True)
    return data if data else {"canales": [], "categorias": [], "total": 0}


# ═══════════════════════════════════════════════════════════════════
# RETRO ARCADE — Descarga y lanzamiento de ROMs desde Cloudflare
# ═══════════════════════════════════════════════════════════════════

# URL base del catálogo retro en Cloudflare Pages
RETRO_BASE_URL = "https://latarr-pro.pages.dev/retro"

def get_retro_games():
    """Carga el índice de juegos retro. Primero intenta local, luego Cloudflare."""
    import urllib.request as _req
    json_path = os.path.normpath(os.path.join(
        addon.getAddonInfo('path'),
        'catalogo', 'retro', 'juegos.json'
    ))
    # Intentar leer local
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            xbmc.log(f'[LATARR-RETRO] Error leyendo juegos.json local: {e}', xbmc.LOGERROR)
    # Fallback: descargar de Cloudflare Pages
    url = RETRO_BASE_URL + '/juegos.json'
    try:
        xbmc.log(f'[LATARR-RETRO] Descargando juegos.json de {url}', xbmc.LOGINFO)
        with _req.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode('utf-8'))
        # Guardar local para proximas veces
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data
    except Exception as e:
        xbmc.log(f'[LATARR-RETRO] Error descargando juegos.json: {e}', xbmc.LOGERROR)
        return []


def get_retro_games_by_platform(plataforma=None):
    """Filtra juegos por plataforma (None = todos)."""
    juegos = get_retro_games()
    if not plataforma or plataforma == 'Todos':
        return juegos
    return [j for j in juegos if j.get('plataforma') == plataforma]


def _retro_local_dir():
    """Carpeta temporal donde se guardan las ROMs descargadas en el dispositivo."""
    try:
        import xbmcvfs
        temp_dir = xbmcvfs.translatePath('special://temp/latarr_retro/')
    except (ImportError, AttributeError):
        try:
            temp_dir = xbmc.translatePath('special://temp/latarr_retro/')
        except Exception:
            temp_dir = os.path.join(os.path.expanduser('~'), '.latarr_retro')
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def _download_retro_file(url, dest_path, progress_dialog=None):
    """
    Descarga un archivo desde Cloudflare Pages al disco local.
    Muestra progreso si se pasa un DialogProgress.
    """
    try:
        from urllib.request import urlopen, Request
        req  = Request(url, headers={'User-Agent': 'LATARR RETRO/2.0'})
        resp = urlopen(req, timeout=30)

        total = int(resp.headers.get('Content-Length', 0))
        downloaded = 0
        chunk = 65536  # 64 KB por chunk

        with open(dest_path, 'wb') as f:
            while True:
                data = resp.read(chunk)
                if not data:
                    break
                f.write(data)
                downloaded += len(data)
                if progress_dialog and total > 0:
                    pct = int(downloaded * 100 / total)
                    mb  = downloaded / 1024 / 1024
                    progress_dialog.update(pct, f"Descargando... {mb:.1f} MB")
                    if progress_dialog.iscanceled():
                        return False
        return True
    except Exception as e:
        xbmc.log(f'[LATARR-RETRO] Error descargando {url}: {e}', xbmc.LOGERROR)
        return False


def launch_retro_game(juego):
    """
    1. Auto-instala el core si no esta instalado
    2. Descarga BIOS + ROM desde Cloudflare
    3. Lanza con RetroPlayer de Kodi
    """
    import xbmcgui
    import xbmcaddon as _xbmcaddon

    titulo   = juego.get('titulo', 'Juego')
    archivo  = juego.get('archivo_rom', '')
    bios_rel = juego.get('requiere_bios')
    core     = juego.get('core', 'game.libretro.mame2003_plus')

    local_dir  = _retro_local_dir()
    rom_nombre = os.path.basename(archivo)
    rom_local  = os.path.join(local_dir, rom_nombre)

    pDialog = xbmcgui.DialogProgress()
    pDialog.create('LATARR RETRO', f'Preparando {titulo}...')

    try:
        # ── 1. Auto-instalar core si no esta ──────────────────
        pDialog.update(5, 'Verificando emulador...')
        try:
            _xbmcaddon.Addon(core)
            xbmc.log(f'[LATARR-RETRO] Core {core} ya instalado', xbmc.LOGINFO)
        except RuntimeError:
            xbmc.log(f'[LATARR-RETRO] Instalando core {core}...', xbmc.LOGINFO)
            pDialog.update(10, 'Instalando emulador MAME... Espera un momento...')
            xbmc.executebuiltin(f'InstallAddon({core})')
            # Esperar hasta 30 segundos a que se instale
            for _ in range(30):
                xbmc.sleep(1000)
                try:
                    _xbmcaddon.Addon(core)
                    xbmc.log(f'[LATARR-RETRO] Core {core} instalado OK', xbmc.LOGINFO)
                    break
                except RuntimeError:
                    pass
            else:
                # Si fallo la instalacion, intentar de todas formas
                xbmc.log(f'[LATARR-RETRO] Core puede no haberse instalado, intentando igual', xbmc.LOGWARNING)

        # ── 2. Descargar BIOS Neo-Geo si necesaria ────────────
        if bios_rel:
            bios_nombre = os.path.basename(bios_rel)
            bios_local  = os.path.join(local_dir, bios_nombre)
            if not os.path.exists(bios_local):
                bios_url = f"{RETRO_BASE_URL}/{bios_rel}"
                pDialog.update(20, 'Descargando BIOS Neo-Geo...')
                if not _download_retro_file(bios_url, bios_local, pDialog):
                    pDialog.close()
                    xbmcgui.Dialog().notification('LATARR RETRO', 'Error descargando BIOS', xbmcgui.NOTIFICATION_ERROR, 4000)
                    return False

        # ── 3. Descargar ROM ──────────────────────────────────
        if not os.path.exists(rom_local):
            rom_url = f"{RETRO_BASE_URL}/{archivo}"
            xbmc.log(f'[LATARR-RETRO] Descargando: {rom_url}', xbmc.LOGINFO)
            pDialog.update(30, f'Descargando {titulo}...')
            if not _download_retro_file(rom_url, rom_local, pDialog):
                pDialog.close()
                xbmcgui.Dialog().notification('LATARR RETRO', 'Error descargando ROM', xbmcgui.NOTIFICATION_ERROR, 4000)
                return False
        else:
            xbmc.log(f'[LATARR-RETRO] ROM en cache: {rom_local}', xbmc.LOGINFO)

        pDialog.update(95, f'Lanzando {titulo}...')
        xbmc.sleep(500)
        pDialog.close()

        # ── 4. Lanzar con RetroPlayer (API oficial Kodi v20/v21) ──
        rom_safe = rom_local.replace('\\', '/')
        plataforma = juego.get('plataforma', 'Arcade')

        # Crear ListItem explícito para juegos
        li = xbmcgui.ListItem(label=titulo, path=rom_local, offscreen=True)

        # Metodo oficial Kodi 20/21: InfoTagGame
        # Esto le indica OBLIGATORIAMENTE a Kodi que es un JUEGO y NO un video
        try:
            game_tag = li.getGameInfoTag()
            game_tag.setTitle(titulo)
            game_tag.setPlatform(plataforma)
            game_tag.setGameClient(core)
            xbmc.log(f'[LATARR-RETRO] getGameInfoTag configurado: {titulo} -> {core}', xbmc.LOGINFO)
        except Exception as e_tag:
            xbmc.log(f'[LATARR-RETRO] getGameInfoTag no disponible ({e_tag}), usando fallback clasico', xbmc.LOGDEBUG)
            try:
                li.setInfo('game', {
                    'title': titulo,
                    'platform': plataforma,
                    'gameclient': core
                })
            except Exception:
                pass

        # Propiedades adicionales para compatibilidad total
        li.setProperty('gameclient', core)
        li.setProperty('GameClient', core)
        li.setProperty('mimetype', 'kodi.gameclient')
        try:
            li.setContentLookup(False)
        except Exception:
            pass

        # Reproducir con RetroPlayer
        try:
            player = xbmc.Player()
            player.play(item=li)
            xbmc.log(f'[LATARR-RETRO] Player().play enviado con InfoTagGame: {rom_local}', xbmc.LOGINFO)
            # Esperar a que RetroPlayer empiece (hasta 10 segundos)
            timeout = 0
            while not player.isPlaying() and timeout < 100:
                xbmc.sleep(100)
                timeout += 1
            xbmc.log(f'[LATARR-RETRO] RetroPlayer iniciado: {player.isPlaying()}', xbmc.LOGINFO)
            return True
        except Exception as e_play:
            xbmc.log(f'[LATARR-RETRO] Player().play fallo: {e_play}', xbmc.LOGWARNING)

        # Fallback PlayMedia con sintaxis de gameclient
        try:
            xbmc.executebuiltin(f'PlayMedia("{rom_safe}",gameclient={core})')
            xbmc.log(f'[LATARR-RETRO] PlayMedia fallback enviado: {rom_safe}', xbmc.LOGINFO)
            return True
        except Exception as e_pm:
            xbmc.log(f'[LATARR-RETRO] PlayMedia fallo: {e_pm}', xbmc.LOGERROR)

        xbmcgui.Dialog().notification('LATARR RETRO', 'Error al iniciar RetroPlayer', xbmcgui.NOTIFICATION_ERROR, 5000)
        return False

    except Exception as e:
        try:
            pDialog.close()
        except Exception:
            pass
        xbmc.log(f'[LATARR-RETRO] Error lanzando {titulo}: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('LATARR RETRO', f'Error: {e}', xbmcgui.NOTIFICATION_ERROR, 5000)
        return False