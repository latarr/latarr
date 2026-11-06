import os
import json
import time
import threading
import urllib.parse
import xbmc
import xbmcgui
import xbmcaddon
from .. import api
from .. import history

# Fila "Continuar Viendo" en el Inicio: desactivada por ahora.
# La lógica de historial sigue funcionando (se guarda el progreso); solo no se muestra la fila.
# Poner en True para volver a mostrarla.
SHOW_CONTINUE_WATCHING = False

addon = xbmcaddon.Addon()
POSTER_BASE = "https://image.tmdb.org/t/p/w342"
FANART_BASE = "https://image.tmdb.org/t/p/w1280"

CONTAINER_IDS = [5000, 5001, 5002, 5003]

class LatarrHomeWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.initial_container = kwargs.pop('initial_container', 5001)
        self.initial_pos = kwargs.pop('initial_pos', 0)
        super().__init__(*args, **kwargs)
        self.initialized = False
        self.active_item = None
        self.addon_path = addon.getAddonInfo('path')
        self._target_fanart = ''
        self._last_nav_time = 0.0
        self._last_vertical_nav = 0.0
        self._current_focus = 5001
        self._fanart_worker_active = False
        self._closed = False
        self.played = False
        self.resume_data = None

    def onInit(self):
        if self.initialized:
            return
        self.initialized = True
        self._closed = False
        
        # Cargar los catálogos en los carruseles
        self._load_shelves()
        
        # Restaurar foco en el carrusel y posición específica si venimos de reproducir
        target_container = self.initial_container or 5001
        try:
            # Si el inicio es por defecto (5001), pero hay Continuar Viendo, dar foco a Continuar Viendo
            if target_container == 5001 and self.initial_pos == 0:
                c5000 = self.getControl(5000)
                if c5000.size() > 0:
                    target_container = 5000

            ctrl = self.getControl(target_container)
            self.setFocus(ctrl)
            if self.initial_pos > 0:
                ctrl.selectItem(self.initial_pos)
        except Exception:
            self.setFocusId(target_container)
        self._update_hero_from_container(target_container, immediate_fanart=True)

    def _load_shelves(self):
        """Carga Continuar Viendo y los 3 catálogos principales de Lo Mejor de Latarr."""
        # Fila 0: Continuar Viendo (Historial Local) - oculta mientras SHOW_CONTINUE_WATCHING sea False
        if SHOW_CONTINUE_WATCHING:
            self._refresh_history_shelf()

        # Fila 1: Lo Mejor en Películas
        top_movies = api.get_top_movies(limit=30)
        self._populate_container(5001, top_movies, media_type='movies')

        # Fila 2: Lo Mejor en Series
        top_series = api.get_top_series(limit=30)
        self._populate_container(5002, top_series, media_type='series')

        # Fila 3: Lo Mejor en Anime
        top_anime = api.get_top_anime(limit=30)
        self._populate_container(5003, top_anime, media_type='anime')

    def _refresh_history_shelf(self):
        """Puebla el contenedor 5000 con los ítems pendientes de Continuar Viendo."""
        try:
            hist_items = history.get_history()
            ctrl = self.getControl(5000)
            ctrl.reset()
            if not hist_items:
                return

            list_items = []
            for item in hist_items:
                title = item.get('display_title') or item.get('title') or 'Sin Título'
                poster = item.get('poster') or ''
                fanart = item.get('fanart') or ''
                
                li = xbmcgui.ListItem(label=title)
                li.setArt({
                    'poster': poster,
                    'thumb': poster,
                    'fanart': fanart
                })
                li.setProperty('title', title)
                li.setProperty('plot', item.get('plot') or '')
                li.setProperty('year', str(item.get('year') or ''))
                li.setProperty('rating', str(item.get('rating') or '7.5'))
                li.setProperty('genre', str(item.get('genre') or 'Cine'))
                li.setProperty('percent', str(item.get('percent', 0)))
                li.setProperty('resume_time', item.get('resume_time') or '')
                li.setProperty('time_display', item.get('time_display') or '')
                li.setProperty('item_json', json.dumps(item))
                list_items.append(li)

            ctrl.addItems(list_items)
        except Exception as e:
            xbmc.log(f"[LATARR] Error cargando Continuar Viendo: {str(e)}", xbmc.LOGERROR)

    def _populate_container(self, container_id, items, media_type='movies'):
        try:
            ctrl = self.getControl(container_id)
            ctrl.reset()
            list_items = []
            
            for item in items:
                # Filtrar ratings ficticios de 10.0
                try:
                    r_val = float(item.get('rating') or 0)
                    if r_val >= 10.0:
                        continue
                except (ValueError, TypeError):
                    pass

                title = item.get('clean_title') or item.get('title') or 'Sin Título'
                p_path = item.get('poster_path')
                poster_url = f"{POSTER_BASE}{p_path}" if p_path else ''
                fanart_url = f"{FANART_BASE}{p_path}" if p_path else ''
                
                li = xbmcgui.ListItem(label=title)
                li.setArt({
                    'poster': poster_url,
                    'thumb': poster_url,
                    'fanart': fanart_url
                })
                
                li.setProperty('title', title)
                li.setProperty('plot', item.get('overview') or '')
                li.setProperty('year', str(item.get('year') or ''))
                
                r = item.get('rating')
                rating_str = f"{float(r):.1f}" if r else "7.5"
                li.setProperty('rating', rating_str)
                
                li.setProperty('genre', str(item.get('genre') or 'Cine'))
                li.setProperty('tmdb_id', str(item.get('tmdb_id') or ''))
                li.setProperty('media_type', media_type)
                
                list_items.append(li)
                
            ctrl.addItems(list_items)
        except Exception as e:
            xbmc.log(f"[LATARR] Error poblando fila {container_id}: {str(e)}", xbmc.LOGERROR)

    def _update_hero_from_container(self, container_id, immediate_fanart=False):
        """Actualiza el Hero Banner optimizado con debounce para TV Boxes."""
        try:
            ctrl = self.getControl(container_id)
            item = ctrl.getSelectedItem()
            if not item:
                return
            
            self.active_item = item
            title = item.getProperty('title') or item.getLabel()
            plot = item.getProperty('plot') or ''
            year = item.getProperty('year') or ''
            rating = item.getProperty('rating') or '7.5'
            genre = item.getProperty('genre') or 'Cine'
            
            # Texto y metadatos: Actualización instantánea (0ms)
            self.setProperty('hero_title', title)
            self.setProperty('hero_plot', plot)
            self.setProperty('hero_year', year)
            self.setProperty('hero_rating', rating)
            self.setProperty('hero_genre', genre)

            fanart = item.getArt('fanart') or ''
            if immediate_fanart or not fanart:
                self.setProperty('hero_fanart', fanart)
            else:
                self._schedule_fanart(fanart)
        except Exception as e:
            xbmc.log(f"[LATARR] Error actualizando Hero Banner: {str(e)}", xbmc.LOGERROR)

    def _schedule_fanart(self, fanart_url):
        """Evita descargas masivas al pasar rápido por los pósteres (Debounce 220ms)."""
        self._target_fanart = fanart_url
        self._last_nav_time = time.time()
        
        if not self._fanart_worker_active:
            self._fanart_worker_active = True
            t = threading.Thread(target=self._fanart_worker, daemon=True)
            t.start()

    def _fanart_worker(self):
        while not self._closed:
            time.sleep(0.08)
            now = time.time()
            if (now - self._last_nav_time) >= 0.22:
                target = self._target_fanart
                if target and not self._closed:
                    self.setProperty('hero_fanart', target)
                self._fanart_worker_active = False
                break

    def _focus_container(self, container_id):
        try:
            ctrl = self.getControl(container_id)
            if ctrl.size() > 0:
                self.setFocus(ctrl)
                self._update_hero_from_container(container_id)
                self._current_focus = container_id
                return True
        except Exception:
            pass
        return False

    def _focus_header(self):
        try:
            self.setFocus(self.getControl(101))
        except Exception:
            self.setFocusId(101)
        xbmc.executebuiltin("SetFocus(101)")
        self._current_focus = 101

    def onAction(self, action):
        action_id = action.getId()
        
        # Salir con tecla Atrás o Escape
        if action_id in (xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK):
            self._closed = True
            xbmc.executebuiltin("ActivateWindow(home)")
            self.close()
            return

        # Navegación vertical directa con debounce anti-rebote (evita cualquier cascada o doble salto)
        if action_id == xbmcgui.ACTION_MOVE_DOWN:
            now = time.time()
            if (now - self._last_vertical_nav) < 0.22:
                return
            self._last_vertical_nav = now

            focus_id = self.getFocusId()
            if focus_id in (0, None):
                focus_id = getattr(self, '_current_focus', 5000)

            has_history = False
            try:
                c5000 = self.getControl(5000)
                if c5000.size() > 0:
                    has_history = True
            except Exception:
                pass

            if focus_id in (100, 101, 102, 103, 104, 105, 106, 107, 108, 109):
                target = 5000 if has_history else 5001
                self._focus_container(target)
                return
            elif focus_id == 5000:
                self._focus_container(5001)
                return
            elif focus_id == 5001:
                self._focus_container(5002)
                return
            elif focus_id == 5002:
                self._focus_container(5003)
                return
            elif focus_id == 5003:
                return  # Tope inferior: al llegar a Anime no baja más
            else:
                return  # Si es Anime o cualquier foco inferior, no baja más

        elif action_id == xbmcgui.ACTION_MOVE_UP:
            now = time.time()
            if (now - self._last_vertical_nav) < 0.22:
                return
            self._last_vertical_nav = now

            focus_id = self.getFocusId()
            if focus_id in (0, None):
                focus_id = getattr(self, '_current_focus', 5000)

            has_history = False
            try:
                c5000 = self.getControl(5000)
                if c5000.size() > 0:
                    has_history = True
            except Exception:
                pass

            if focus_id in (100, 101, 102, 103, 104, 105, 106, 107, 108, 109):
                return
            elif focus_id == 5000:
                self._focus_header()
                return
            elif focus_id == 5001:
                if has_history:
                    self._focus_container(5000)
                else:
                    self._focus_header()
                return
            elif focus_id == 5002:
                self._focus_container(5001)
                return
            elif focus_id == 5003:
                self._focus_container(5002)
                return

        # Para navegación horizontal (izquierda/derecha dentro de la fila) y selección
        try:
            super().onAction(action)
        except Exception:
            pass

        # Actualizar metadatos del Hero Banner al moverse horizontalmente
        focus_id = self.getFocusId()
        if focus_id in CONTAINER_IDS:
            self._update_hero_from_container(focus_id)

    def onClick(self, control_id):
        # 1. Clic en póster
        if control_id in CONTAINER_IDS:
            self._on_item_selected(control_id)
            return

        # 2. Barra Superior
        if control_id == 101: # Inicio
            if not self._focus_container(5000):
                self._focus_container(5001)
        elif control_id == 102: # Películas
            self._open_catalog('movies')
        elif control_id == 103: # Series
            self._open_catalog('series')
        elif control_id == 104: # Anime
            self._open_catalog('anime')
        elif control_id == 109: # TV en Vivo
            self._open_tv()
        elif control_id == 105: # Buscar
            self._open_search()
        elif control_id == 107: # Historial
            self._open_history()
        elif control_id == 108: # Colecciones (por actor)
            self._open_actors()
        elif control_id == 106: # Ajustes
            addon.openSettings()
            if addon.getSetting('ui_mode') == "1":
                self._closed = True
                self.close()
        elif control_id == 110: # RETRO ARCADE
            self._open_retro()

    def _open_catalog(self, media_type):
        from .catalog import LatarrCatalogDialog
        dlg = LatarrCatalogDialog(
            'script-latarr-catalog.xml',
            self.addon_path,
            defaultSkin='Default',
            defaultRes='1080i',
            media_type=media_type,
            addon_path=self.addon_path
        )
        dlg.doModal()
        if getattr(dlg, 'played', False):
            self.played = True
            self.resume_data = getattr(dlg, 'resume_data', None)
            self._closed = True
            del dlg
            self.close()
            return
        del dlg

    def _on_item_selected(self, container_id):
        try:
            ctrl = self.getControl(container_id)
            item = ctrl.getSelectedItem()
            pos = ctrl.getSelectedPosition()
            if not item:
                return
            self.active_item = item

            if container_id == 5000:
                self._open_resume_dialog(item, pos=pos)
            else:
                self._open_detail(item, container_id=container_id, pos=pos)
        except Exception as e:
            xbmc.log(f"[LATARR] Error al seleccionar ítem: {str(e)}", xbmc.LOGERROR)

    def _open_resume_dialog(self, item, pos=0):
        raw_json = item.getProperty('item_json')
        if not raw_json:
            return
        try:
            item_data = json.loads(raw_json)
        except Exception:
            return

        from .resume import LatarrResumeDialog
        dlg = LatarrResumeDialog(
            'script-latarr-resume.xml',
            self.addon_path,
            defaultSkin='Default',
            defaultRes='1080i',
            item_data=item_data
        )
        dlg.doModal()
        action = getattr(dlg, 'action_selected', None)
        del dlg

        if action == 'resume':
            self._resume_playback(item_data, start_time=item_data.get('current_time', 0))
        elif action == 'restart':
            self._resume_playback(item_data, start_time=0)
        elif action == 'delete':
            history.delete_item(item_data.get('id'))
            self._refresh_history_shelf()
            xbmcgui.Dialog().notification('Latarr', 'Eliminado de Continuar Viendo', xbmcgui.NOTIFICATION_INFO, 1500)
            if not self._focus_container(5000):
                self._focus_container(5001)

    def _resume_playback(self, item_data, start_time=0):
        magnet = item_data.get('magnet')
        if not magnet:
            xbmcgui.Dialog().notification('Latarr', 'Enlace no disponible', xbmcgui.NOTIFICATION_WARNING)
            return

        engine = addon.getSetting('torrent_engine')
        mag_encoded = urllib.parse.quote_plus(magnet)
        
        if engine == "1": # Torrest
            play_url = f"plugin://plugin.video.torrest/play_magnet?magnet={mag_encoded}"
        else: # Elementum
            # SIN &resume=1: eso hacía que Elementum abriera su propio diálogo de 5 s
            # y la reanudación la hacemos nosotros con seekTime() (ver main.wait_for_playback)
            play_url = f"plugin://plugin.video.elementum/play?uri={mag_encoded}"
            f_idx = item_data.get('file_index')
            if f_idx is not None and str(f_idx) != '':
                play_url += f"&index={f_idx}"

        display_title = item_data.get('display_title') or item_data.get('title') or "Latarr Video"
        li = xbmcgui.ListItem(label=display_title)
        media_type = item_data.get('media_type', 'movies')
        
        info = {
            'title': display_title,
            'tvshowtitle': item_data.get('title') if media_type in ('series', 'anime') else '',
            'plot': item_data.get('plot') or '',
            'year': int(item_data.get('year')) if str(item_data.get('year', '')).isdigit() else 0,
            'genre': item_data.get('genre') or '',
            'rating': float(item_data.get('rating')) if item_data.get('rating') else 0.0,
            'mediatype': 'episode' if media_type in ('series', 'anime') else 'movie'
        }
        sn = item_data.get('season')
        ep = item_data.get('episode')
        if sn and str(sn).isdigit():
            info['season'] = int(sn)
        if ep and str(ep).isdigit():
            info['episode'] = int(ep)
        li.setInfo('video', info)

        art = {}
        if item_data.get('poster'):
            art['poster'] = item_data['poster']
            art['thumb'] = item_data['poster']
        if item_data.get('fanart'):
            art['fanart'] = item_data['fanart']
        if art:
            li.setArt(art)

        # Copia del ítem + segundo al que hay que saltar cuando el video ya esté corriendo
        playback_data = dict(item_data)
        playback_data['seek_to'] = float(start_time or 0)
        history.set_current_playback(playback_data)
        xbmc.Player().play(play_url, li)
        self._wait_for_player_and_close()

    def _wait_for_player_and_close(self):
        monitor = xbmc.Monitor()
        player = xbmc.Player()
        started = False
        
        for _ in range(4000):  # hasta 20 minutos para torrents lentos
            if monitor.abortRequested():
                break
            if player.isPlayingVideo():
                started = True
                break
            monitor.waitForAbort(0.3)

        if started:
            self.played = True
            self.resume_data = {'section': 'home', 'container': 5000, 'pos': 0}
            self._closed = True
            self.close()
            xbmc.executebuiltin("Dialog.Close(busydialog)")
            xbmc.executebuiltin("Dialog.Close(busydialognocancel)")
            xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")
        else:
            self.played = False

    def _open_detail(self, item, container_id=5001, pos=0):
        tmdb_id = item.getProperty('tmdb_id')
        media_type = item.getProperty('media_type') or 'movies'
        title = item.getProperty('title')
        
        if not tmdb_id:
            return
            
        from .sources import LatarrSourcesDialog
        dlg = LatarrSourcesDialog(
            'script-latarr-sources.xml',
            self.addon_path,
            defaultSkin='Default',
            defaultRes='1080i',
            tmdb_id=tmdb_id,
            media_type=media_type,
            title=title,
            poster=item.getArt('poster'),
            fanart=item.getArt('fanart'),
            plot=item.getProperty('plot'),
            year=item.getProperty('year'),
            rating=item.getProperty('rating'),
            genre=item.getProperty('genre')
        )
        dlg.doModal()
        was_played = getattr(dlg, 'played', False)
        del dlg

        if was_played:
            self.played = True
            if media_type in ('series', 'anime'):
                # Para series o anime: volver directo a la pantalla de fuentes (episodios)
                self.resume_data = {
                    'section': 'sources',
                    'tmdb_id': tmdb_id,
                    'media_type': media_type,
                    'title': title,
                    'poster': item.getArt('poster'),
                    'fanart': item.getArt('fanart'),
                    'plot': item.getProperty('plot'),
                    'year': item.getProperty('year'),
                    'rating': item.getProperty('rating'),
                    'genre': item.getProperty('genre'),
                    'parent': {
                        'section': 'home',
                        'container': container_id,
                        'pos': pos
                    }
                }
            else:
                # Para películas: volver al carrusel sobre la misma película
                self.resume_data = {
                    'section': 'home',
                    'container': container_id,
                    'pos': pos
                }
            self._closed = True
            self.close()

    def _open_history(self, initial_pos=0):
        """Modal informativo con lo último que has empezado a ver (series, anime y películas)."""
        if not history.get_history():
            xbmcgui.Dialog().notification('Latarr', 'El historial está vacío. Lo que empieces a ver aparecerá aquí.', xbmcgui.NOTIFICATION_INFO, 3000)
            return

        from .history_win import LatarrHistoryDialog
        dlg = LatarrHistoryDialog(
            'script-latarr-history.xml',
            self.addon_path,
            defaultSkin='Default',
            defaultRes='1080i',
            addon_path=self.addon_path,
            initial_pos=initial_pos
        )
        dlg.doModal()
        if getattr(dlg, 'played', False):
            self.played = True
            self.resume_data = getattr(dlg, 'resume_data', None)
            self._closed = True
            del dlg
            self.close()
            return
        del dlg

    def _open_tv(self, initial_pos=0, initial_country=None, initial_category='Todas'):
        """Televisión en Vivo por países y categorías."""
        from .tv_win import LatarrTVDialog
        dlg = LatarrTVDialog(
            'script-latarr-tv.xml',
            self.addon_path,
            defaultSkin='Default',
            defaultRes='1080i',
            addon_path=self.addon_path,
            initial_pos=initial_pos,
            initial_country=initial_country,
            initial_category=initial_category,
        )
        dlg.doModal()
        if getattr(dlg, 'played', False):
            self.played = True
            self.resume_data = getattr(dlg, 'resume_data', None)
            self._closed = True
            del dlg
            self.close()
            return
        del dlg

    def _open_actors(self, initial_pos=0):
        """Cuadrícula de actores con películas disponibles en Latarr (Colecciones)."""
        from .actors_win import LatarrActorsDialog
        dlg = LatarrActorsDialog(
            'script-latarr-actors.xml',
            self.addon_path,
            defaultSkin='Default',
            defaultRes='1080i',
            addon_path=self.addon_path,
            initial_pos=initial_pos,
        )
        dlg.doModal()
        if getattr(dlg, 'played', False):
            self.played = True
            self.resume_data = getattr(dlg, 'resume_data', None)
            self._closed = True
            del dlg
            self.close()
            return
        del dlg

    def _open_retro(self):
        """Seccion Retro Arcade: descarga y lanza ROMs clasicas en Kodi RetroPlayer."""
        from .retro_win import LatarrRetroDialog
        import xbmc
        from .. import api as retro_api

        dlg = LatarrRetroDialog(
            'script-latarr-retro.xml',
            self.addon_path,
            defaultSkin='Default',
            defaultRes='1080i',
            addon_path=self.addon_path
        )
        dlg.doModal()

        # Leer el juego elegido ANTES de destruir el dialogo
        juego_a_lanzar = getattr(dlg, 'juego_a_lanzar', None)

        # Destruir completamente el dialogo modal
        del dlg

        # Si el usuario eligio un juego, lanzarlo ahora que el dialogo ya no existe
        # Esto evita el conflicto "active modal dialogs" que mataba a MAME a los 11s
        if juego_a_lanzar:
            xbmc.log(f"[LATARR-RETRO] Lanzando juego desde home: {juego_a_lanzar.get('titulo')}", xbmc.LOGINFO)
            xbmc.sleep(500)  # dar tiempo a que el dialogo se destruya completamente
            retro_api.launch_retro_game(juego_a_lanzar)
            # Esperar que el juego termine para no volver al home prematuramente
            xbmc.sleep(1000)
            player = xbmc.Player()
            if player.isPlaying():
                monitor = xbmc.Monitor()
                xbmc.log('[LATARR-RETRO] Esperando fin del juego...', xbmc.LOGINFO)
                while player.isPlaying() and not monitor.abortRequested():
                    xbmc.sleep(500)
                xbmc.log('[LATARR-RETRO] Juego terminado, volviendo al home', xbmc.LOGINFO)

    def _open_search(self):
        query = xbmcgui.Dialog().input('¿Qué deseas ver en Latarr?', type=xbmcgui.INPUT_ALPHANUM)
        if not query:
            return

        xbmcgui.Dialog().notification('Latarr', f'Buscando: {query}', xbmcgui.NOTIFICATION_INFO, 1500)
        m_res = api.search_all(query, media_type='movies') or {}
        s_res = api.search_all(query, media_type='series') or {}
        a_res = api.search_all(query, media_type='anime') or {}
        
        movies = m_res.get('results', []) if isinstance(m_res, dict) else []
        series = s_res.get('results', []) if isinstance(s_res, dict) else []
        anime = a_res.get('results', []) if isinstance(a_res, dict) else []
        
        for m in movies:
            m['media_type'] = 'movies'
            m['is_anime'] = False
        for s in series:
            s['media_type'] = 'series'
            s['is_anime'] = False
        for a in anime:
            a['media_type'] = 'series' if a.get('media_type') in ('series', 'serie') else 'movies'
            a['is_anime'] = True

        total_items = movies + series + anime
        
        if total_items:
            from .search import LatarrSearchDialog
            dlg = LatarrSearchDialog(
                'script-latarr-search.xml',
                self.addon_path,
                defaultSkin='Default',
                defaultRes='1080i',
                query=query,
                items=total_items,
                addon_path=self.addon_path
            )
            dlg.doModal()
            if getattr(dlg, 'played', False):
                self.played = True
                self.resume_data = getattr(dlg, 'resume_data', None)
                self._closed = True
                del dlg
                self.close()
                return
            del dlg
        else:
            xbmcgui.Dialog().notification('Latarr', 'Sin resultados para la búsqueda', xbmcgui.NOTIFICATION_WARNING)
