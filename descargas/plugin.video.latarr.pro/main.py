import sys
import re
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

addon = xbmcaddon.Addon()

POSTER_BASE = "https://image.tmdb.org/t/p/w342"
FANART_BASE = "https://image.tmdb.org/t/p/w1280"


# ---- helpers de salud de enlace ----

def _semillas(valor):
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0

def _numero(valor):
    """Primer numero de un valor. Acepta 3, '3' o '1 a 5'."""
    if isinstance(valor, bool):
        return 0
    if isinstance(valor, (int, float)):
        return int(valor)
    m = re.search(r"\d+", str(valor or ""))
    return int(m.group()) if m else 0

def _ordenar(items, clave):
    try:
        return sorted(items, key=clave)
    except Exception as e:
        xbmc.log(f"[LATARR] No se pudo ordenar: {str(e)}", xbmc.LOGERROR)
        return list(items)

def _color_salud(seeds):
    s = _semillas(seeds)
    if s >= 100:
        return 'FF2ECC71'
    if s >= 50:
        return 'FFF1C40F'
    return 'FFE74C3C'

def _punto(seeds):
    return f"[COLOR {_color_salud(seeds)}]o[/COLOR]"

def _calidad(calidad, seeds):
    return f"[COLOR {_color_salud(seeds)}]{calidad}[/COLOR]"


# ==========================================
# MONITOR DE REPRODUCCION
# ==========================================

def _detectar_episodio_en_curso(player):
    """
    En un pack, el capitulo lo elige Elementum DESPUES de que el addon lanza
    la reproduccion. Aqui leemos el nombre del archivo real y corregimos la sesion.
    Devuelve True cuando ya no hace falta seguir intentando.
    """
    from resources.lib import history
    cur = history.get_current_playback()
    if not cur:
        return True
    if cur.get('media_type') not in ('series', 'anime'):
        return True
    if str(cur.get('episode') or '').strip() not in ('', '0'):
        return True

    candidatos = []
    try:
        candidatos.append(player.getPlayingFile())
    except Exception:
        pass
    for lbl in ('Player.Filename', 'Player.Filenameandpath'):
        try:
            candidatos.append(xbmc.getInfoLabel(lbl))
        except Exception:
            pass

    for raw in candidatos:
        if not raw or str(raw).startswith('plugin://'):
            continue
        nombre = urllib.parse.unquote(str(raw)).split('?')[0]
        sn, ep = history.parse_episode(nombre)
        if not ep:
            continue
        season_final = sn or _numero(cur.get('season')) or 0
        label = history.episode_label(season_final, ep)
        cur['season'] = str(season_final) if season_final else ''
        cur['episode'] = str(ep)
        cur['file_name'] = nombre.replace('\\', '/').split('/')[-1]
        cur['display_title'] = f"{cur.get('title') or 'Serie'} - Episodio {label}"
        xbmc.log(f"[LATARR] Episodio detectado en pack: {label} <- {cur['file_name']}", xbmc.LOGINFO)
        return True
    return False


def wait_for_playback(player, monitor):
    """Monitorea la reproduccion y guarda el progreso al terminar."""
    import time as _time
    last_time = 0.0
    total_time = 0.0
    fullscreen_sent_at = None   # momento en que se envio el ultimo ActivateWindow
    fullscreen_confirmed = False  # True cuando ya llevamos >3s reproduciendo bien

    try:
        from resources.lib import history as _h
        _cur = _h.get_current_playback() or {}
        seek_to = float(_cur.get('seek_to') or 0)
    except Exception:
        seek_to = 0.0

    ep_detected = False
    ep_tries = 0
    seek_done = seek_to <= 0
    seek_tries = 0
    seek_first_seen = None
    seek_last_try = 0.0

    while player.isPlaying():
        if monitor.abortRequested():
            return
        try:
            if player.isPlayingVideo():
                now = _time.time()
                # Reenviar ActivateWindow(fullscreenvideo) cada vez que se
                # detecte reproduccion activa, hasta confirmar pantalla completa.
                # - Primera vez: enviar de inmediato.
                # - Reintentos: cada 2 s durante los primeros 120 s.
                # - Se deja de reintentar cuando el usuario lleva >3 s en
                #   reproduccion continua (total_time ya tiene valor estable).
                if not fullscreen_confirmed:
                    elapsed_play = now - fullscreen_sent_at if fullscreen_sent_at else 9999
                    should_send = (
                        fullscreen_sent_at is None          # primer intento
                        or (elapsed_play >= 2.0             # reintento cada 2 s
                            and (now - fullscreen_sent_at) < 120)  # hasta 120 s
                    )
                    if should_send:
                        xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")
                        fullscreen_sent_at = now
                    # Considerar confirmado si total_time ya es estable y llevamos
                    # al menos 3 s de reproduccion real
                    if total_time > 0 and last_time > 3.0:
                        fullscreen_confirmed = True
                t = player.getTime()
                tot = player.getTotalTime()
                if tot > 0:
                    if not ep_detected and ep_tries < 60:
                        ep_tries += 1
                        ep_detected = _detectar_episodio_en_curso(player)
                        if not ep_detected and ep_tries == 60:
                            xbmc.log("[LATARR] No se pudo detectar episodio del pack", xbmc.LOGWARNING)
                    if not seek_done:
                        now = _time.time()
                        if seek_first_seen is None:
                            seek_first_seen = now
                        if t >= seek_to - 5:
                            xbmc.log(f"[LATARR] Reanudacion OK en {t:.0f}s (objetivo {seek_to:.0f}s)", xbmc.LOGINFO)
                            seek_done = True
                        elif seek_to >= tot - 10:
                            seek_done = True
                        elif seek_tries >= 8:
                            xbmc.log("[LATARR] No se pudo reanudar tras 8 intentos", xbmc.LOGWARNING)
                            seek_done = True
                        elif now - seek_first_seen >= 1.5 and now - seek_last_try >= 4.0:
                            seek_tries += 1
                            seek_last_try = now
                            xbmc.log(f"[LATARR] seekTime({seek_to:.0f}) intento {seek_tries}", xbmc.LOGINFO)
                            player.seekTime(seek_to)
                    last_time = t
                    total_time = tot
        except Exception:
            pass
        monitor.waitForAbort(0.3)

    try:
        from resources.lib import history
        cur_item = history.get_current_playback()
        if cur_item and total_time > 0:
            history.save_progress(
                item_data=cur_item,
                current_time=last_time,
                total_time=total_time,
                file_name=cur_item.get('file_name'),
                file_index=cur_item.get('file_index')
            )
            history.clear_current_playback()
    except Exception as e:
        xbmc.log(f"[LATARR] Error guardando progreso: {str(e)}", xbmc.LOGERROR)

    xbmc.executebuiltin("Dialog.Close(all, true)")


# ==========================================
# INTERFAZ CINEMA (modo principal)
# ==========================================

def launch_cinema():
    try:
        from resources.lib.windows.home import LatarrHomeWindow
        from resources.lib.windows.catalog import LatarrCatalogDialog
        from resources.lib.windows.sources import LatarrSourcesDialog
        from resources.lib.windows.search import LatarrSearchDialog
        monitor = xbmc.Monitor()
        player = xbmc.Player()

        resume_data = None

        while not monitor.abortRequested():
            # CASO 1: Reanudar en Fuentes (series/anime)
            if resume_data and resume_data.get('section') == 'sources':
                s_data = resume_data
                resume_data = None

                dlg = LatarrSourcesDialog(
                    'script-latarr-sources.xml',
                    addon.getAddonInfo('path'),
                    defaultSkin='Default',
                    defaultRes='1080i',
                    tmdb_id=s_data.get('tmdb_id'),
                    media_type=s_data.get('media_type'),
                    title=s_data.get('title'),
                    poster=s_data.get('poster'),
                    fanart=s_data.get('fanart'),
                    plot=s_data.get('plot'),
                    year=s_data.get('year'),
                    rating=s_data.get('rating'),
                    genre=s_data.get('genre')
                )
                dlg.doModal()
                was_played = getattr(dlg, 'played', False)
                del dlg

                if was_played:
                    resume_data = s_data
                    wait_for_playback(player, monitor)
                    continue
                else:
                    parent = s_data.get('parent')
                    if parent:
                        resume_data = parent
                    continue

            # CASO 2: Reanudar en Catalogo
            elif resume_data and resume_data.get('section') == 'catalog':
                r_type = resume_data.get('media_type', 'movies')
                r_off = resume_data.get('offset', 0)
                r_yr = resume_data.get('year', 'Todos')
                r_gn = resume_data.get('genre', 'Todos')
                r_pos = resume_data.get('pos', 0)
                resume_data = None

                dlg = LatarrCatalogDialog(
                    'script-latarr-catalog.xml',
                    addon.getAddonInfo('path'),
                    defaultSkin='Default',
                    defaultRes='1080i',
                    media_type=r_type,
                    addon_path=addon.getAddonInfo('path'),
                    initial_offset=r_off,
                    initial_year=r_yr,
                    initial_genre=r_gn,
                    initial_pos=r_pos
                )
                dlg.doModal()
                was_played = getattr(dlg, 'played', False)
                if was_played:
                    resume_data = getattr(dlg, 'resume_data', None)
                del dlg

                if was_played:
                    wait_for_playback(player, monitor)
                    continue
                else:
                    continue

            # CASO 3: Reanudar en Busqueda
            elif resume_data and resume_data.get('section') == 'search':
                s_query = resume_data.get('query', '')
                s_items = resume_data.get('items', [])
                s_pos = resume_data.get('pos', 0)
                resume_data = None

                dlg = LatarrSearchDialog(
                    'script-latarr-search.xml',
                    addon.getAddonInfo('path'),
                    defaultSkin='Default',
                    defaultRes='1080i',
                    query=s_query,
                    items=s_items,
                    addon_path=addon.getAddonInfo('path'),
                    initial_pos=s_pos
                )
                dlg.doModal()
                was_played = getattr(dlg, 'played', False)
                if was_played:
                    resume_data = getattr(dlg, 'resume_data', None)
                del dlg

                if was_played:
                    wait_for_playback(player, monitor)
                    continue
                else:
                    continue

            # CASO 4: Reanudar en Historial
            elif resume_data and resume_data.get('section') == 'history':
                from resources.lib.windows.history_win import LatarrHistoryDialog
                h_pos = resume_data.get('pos', 0)
                resume_data = None

                dlg = LatarrHistoryDialog(
                    'script-latarr-history.xml',
                    addon.getAddonInfo('path'),
                    defaultSkin='Default',
                    defaultRes='1080i',
                    addon_path=addon.getAddonInfo('path'),
                    initial_pos=h_pos
                )
                dlg.doModal()
                was_played = getattr(dlg, 'played', False)
                if was_played:
                    resume_data = getattr(dlg, 'resume_data', None)
                del dlg

                if was_played:
                    wait_for_playback(player, monitor)
                    continue
                else:
                    continue

            # CASO 4b: Reanudar en Colecciones → películas de un actor
            elif resume_data and resume_data.get('section') == 'actor_movies':
                from resources.lib.windows.actors_movies_win import LatarrActorMoviesDialog
                am_actor_id   = resume_data.get('actor_id', 0)
                am_actor_name = resume_data.get('actor_name', 'Actor')
                am_pos        = resume_data.get('pos', 0)
                am_actors_pos = resume_data.get('actors_pos', 0)
                resume_data = None

                dlg = LatarrActorMoviesDialog(
                    'script-latarr-actor-movies.xml',
                    addon.getAddonInfo('path'),
                    defaultSkin='Default',
                    defaultRes='1080i',
                    actor_id=am_actor_id,
                    actor_name=am_actor_name,
                    addon_path=addon.getAddonInfo('path'),
                    initial_pos=am_pos,
                )
                dlg.doModal()
                was_played = getattr(dlg, 'played', False)
                if was_played:
                    resume_data = getattr(dlg, 'resume_data', None)
                    # Si el resume_data del hijo es actor_movies otra vez,
                    # preservar la posición del actor para cuando salgamos.
                    if resume_data and resume_data.get('section') == 'actor_movies':
                        resume_data.setdefault('actors_pos', am_actors_pos)
                del dlg

                if was_played:
                    wait_for_playback(player, monitor)
                    continue
                else:
                    # Usuario salió sin reproducir → volver a la lista de actores
                    resume_data = {'section': 'actors', 'pos': am_actors_pos}
                    continue

            # CASO 4c: Reanudar en Colecciones → lista de actores
            elif resume_data and resume_data.get('section') == 'actors':
                from resources.lib.windows.actors_win import LatarrActorsDialog
                a_pos = resume_data.get('pos', 0)
                resume_data = None

                dlg = LatarrActorsDialog(
                    'script-latarr-actors.xml',
                    addon.getAddonInfo('path'),
                    defaultSkin='Default',
                    defaultRes='1080i',
                    addon_path=addon.getAddonInfo('path'),
                    initial_pos=a_pos,
                )
                dlg.doModal()
                was_played = getattr(dlg, 'played', False)
                if was_played:
                    resume_data = getattr(dlg, 'resume_data', None)
                del dlg

                if was_played:
                    wait_for_playback(player, monitor)
                    continue
                else:
                    continue

            # CASO 4d: Reanudar en Zapping TV
            elif resume_data and resume_data.get('section') == 'zapping':
                from resources.lib.windows.tv_win import LatarrTVDialog
                tv_country = resume_data.get('country')
                tv_cat = resume_data.get('category', 'Todas')
                tv_pos = resume_data.get('pos', 0)
                resume_data = None

                dlg = LatarrTVDialog(
                    'script-latarr-tv.xml',
                    addon.getAddonInfo('path'),
                    defaultSkin='Default',
                    defaultRes='1080i',
                    addon_path=addon.getAddonInfo('path'),
                    initial_country=tv_country,
                    initial_category=tv_cat,
                    initial_pos=tv_pos,
                    is_zapping=True,
                )
                dlg.doModal()
                was_played = getattr(dlg, 'played', False)
                if was_played:
                    resume_data = getattr(dlg, 'resume_data', None)
                del dlg

                if was_played:
                    wait_for_playback(player, monitor)
                    continue
                else:
                    continue

            # CASO 4d: Reanudar en Televisión en Vivo
            elif resume_data and resume_data.get('section') == 'tv':
                from resources.lib.windows.tv_win import LatarrTVDialog
                tv_country = resume_data.get('country')
                tv_cat = resume_data.get('category', 'Todas')
                tv_pos = resume_data.get('pos', 0)
                resume_data = None

                dlg = LatarrTVDialog(
                    'script-latarr-tv.xml',
                    addon.getAddonInfo('path'),
                    defaultSkin='Default',
                    defaultRes='1080i',
                    addon_path=addon.getAddonInfo('path'),
                    initial_country=tv_country,
                    initial_category=tv_cat,
                    initial_pos=tv_pos,
                )
                dlg.doModal()
                was_played = getattr(dlg, 'played', False)
                if was_played:
                    resume_data = getattr(dlg, 'resume_data', None)
                del dlg

                if was_played:
                    wait_for_playback(player, monitor)
                    continue
                else:
                    continue

            # CASO 5: Home principal
            h_container = 5001
            h_pos = 0
            if resume_data and resume_data.get('section') == 'home':
                h_container = resume_data.get('container', 5001)
                h_pos = resume_data.get('pos', 0)
                resume_data = None

            win = LatarrHomeWindow(
                'script-latarr-main.xml',
                addon.getAddonInfo('path'),
                defaultSkin='Default',
                defaultRes='1080i',
                initial_container=h_container,
                initial_pos=h_pos
            )
            win.doModal()
            was_played = getattr(win, 'played', False)
            if was_played:
                resume_data = getattr(win, 'resume_data', None)
            del win

            if was_played:
                wait_for_playback(player, monitor)
            else:
                xbmc.executebuiltin("ActivateWindow(home)")
                break

    except Exception as e:
        xbmc.log(f"[LATARR] Error en ciclo Cinema: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification('Latarr', f'Error UI: {str(e)}', xbmcgui.NOTIFICATION_ERROR)
    finally:
        xbmc.executebuiltin("Dialog.Close(busydialog)")
        xbmc.executebuiltin("Dialog.Close(busydialognocancel)")
        xbmc.executebuiltin("ActivateWindow(home)")


# ==========================================
# PUNTO DE ENTRADA
# ==========================================

if __name__ == '__main__':
    # Cerrar el directorio de Kodi inmediatamente y lanzar la UI Cinema
    handle = int(sys.argv[1]) if len(sys.argv) > 1 else -1
    if handle >= 0:
        xbmcplugin.endOfDirectory(handle, False)
    xbmc.executebuiltin("Dialog.Close(busydialog)")
    xbmc.executebuiltin("Dialog.Close(busydialognocancel)")
    xbmc.executebuiltin("Dialog.Close(all, true)")

    # Salida rápida estilo Netflix (Atrás / Esc / Backspace detiene el video)
    try:
        from resources.lib import keymap
        keymap.ensure_netflix_keymap()
    except Exception as _km_err:
        xbmc.log(f"[LATARR] Error iniciando keymap: {_km_err}", xbmc.LOGWARNING)

    launch_cinema()
