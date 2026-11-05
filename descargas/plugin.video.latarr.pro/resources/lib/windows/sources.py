import urllib.parse
import xbmc
import xbmcgui
import xbmcaddon
from .. import api
from .. import history

addon = xbmcaddon.Addon()

def _format_seeds(seeds, in_focus=False):
    s = int(seeds or 0)
    if s >= 100:
        color = "FF30D158" # Verde Apple
    elif s >= 50:
        color = "FFFFD60A" # Amarillo Apple
    else:
        color = "FFFF453A" # Rojo sutil
        
    text_color = "FF000000" if in_focus else "FFFFFFFF"
    return f"[COLOR {color}]●[/COLOR] [COLOR {text_color}]{s} seeds[/COLOR]"

def _clean_quality(q):
    q_str = str(q or '1080P').upper()
    if '2160' in q_str or '4K' in q_str:
        return '4K'
    if '1080' in q_str:
        return '1080P'
    if '720' in q_str:
        return '720P'
    return 'HD'

class LatarrSourcesDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.tmdb_id = kwargs.pop('tmdb_id', None)
        self.media_type = kwargs.pop('media_type', 'movies')
        self.title = kwargs.pop('title', 'Detalles')
        self.poster = kwargs.pop('poster', '')
        self.fanart = kwargs.pop('fanart', '')
        self.plot = kwargs.pop('plot', '')
        self.year = kwargs.pop('year', '')
        self.rating = kwargs.pop('rating', '')
        self.genre = kwargs.pop('genre', '')
        super().__init__(*args, **kwargs)
        self.initialized = False
        self.played = False

    def onInit(self):
        if self.initialized:
            return
        self.initialized = True
        
        self.setProperty('dialog_title', self.title)
        self.setProperty('dialog_subtitle', 'Buscando enlaces disponibles en la red P2P...')
        self.setProperty('item_poster', self.poster)
        self.setProperty('item_fanart', self.fanart)
        self.setProperty('item_plot', self.plot)
        self.setProperty('item_year', str(self.year or ''))
        self.setProperty('item_rating', str(self.rating or '7.5'))
        self.setProperty('item_genre', str(self.genre or 'Cine'))
        
        self._load_sources()

    def _load_sources(self):
        if not self.tmdb_id:
            self.setProperty('dialog_subtitle', 'Error: Identificador no válido')
            return

        ctrl = self.getControl(6001)
        ctrl.reset()

        data = None
        if self.media_type == 'movies':
            data = api.get_movie_detail(self.tmdb_id)
            raw_links = data.get('links', []) if data else []
        elif self.media_type == 'anime':
            # Consultar anime en backend (series o películas)
            data = api.get_anime_detail(self.tmdb_id, anime_type='series')
            raw_links = []
            if data and not data.get('error'):
                for p in data.get('packs', []):
                    sn = p.get('season') or 0
                    p_title = "PACK COMPLETO" if sn == 0 else f"Pack Temporada {sn}"
                    p['custom_label'] = f"[PACK] {p_title}"
                    raw_links.append(p)
                for ep in data.get('episodes', []):
                    try:
                        s_val = int(ep.get('season') or 0)
                    except (ValueError, TypeError):
                        s_val = 0
                    try:
                        e_val = int(ep.get('episode') or 0)
                    except (ValueError, TypeError):
                        e_val = 0

                    if s_val == 0:
                        ep['custom_label'] = f"⭐ Especial {e_val}" if e_val > 0 else "⭐ Especial"
                    else:
                        s_num = str(s_val).zfill(2)
                        e_num = str(e_val).zfill(2)
                        ep['custom_label'] = f"Episodio S{s_num}E{e_num}"
                    raw_links.append(ep)
                for l in data.get('links', []):
                    raw_links.append(l)

            if not raw_links:
                data_mov = api.get_anime_detail(self.tmdb_id, anime_type='movie')
                if data_mov and not data_mov.get('error'):
                    data = data_mov
                    raw_links = data_mov.get('links', [])
        else:
            data = api.get_serie_detail(self.tmdb_id)
            raw_links = []
            if data and not data.get('error'):
                # Combinar packs y episodios si es serie
                for p in data.get('packs', []):
                    sn = p.get('season') or 0
                    p_title = "PACK COMPLETO" if sn == 0 else f"Pack Temporada {sn}"
                    p['custom_label'] = f"[PACK] {p_title}"
                    raw_links.append(p)
                for ep in data.get('episodes', []):
                    try:
                        s_val = int(ep.get('season') or 0)
                    except (ValueError, TypeError):
                        s_val = 0
                    try:
                        e_val = int(ep.get('episode') or 0)
                    except (ValueError, TypeError):
                        e_val = 0

                    if s_val == 0:
                        ep['custom_label'] = f"⭐ Especial {e_val}" if e_val > 0 else "⭐ Especial"
                    else:
                        s_num = str(s_val).zfill(2)
                        e_num = str(e_val).zfill(2)
                        ep['custom_label'] = f"Episodio S{s_num}E{e_num}"
                    raw_links.append(ep)

        # Si la respuesta trae metadata, actualizar propiedades si faltaban
        if isinstance(data, dict):
            meta = data.get('metadata') or {}
            if meta:
                if not self.plot and meta.get('overview'):
                    self.plot = meta.get('overview')
                    self.setProperty('item_plot', self.plot)
                if not self.poster and meta.get('poster_path'):
                    self.poster = f"https://image.tmdb.org/t/p/w500{meta.get('poster_path')}"
                    self.setProperty('item_poster', self.poster)
                if not self.fanart and meta.get('poster_path'):
                    self.fanart = f"https://image.tmdb.org/t/p/w1280{meta.get('poster_path')}"
                    self.setProperty('item_fanart', self.fanart)
                if not self.year and meta.get('year'):
                    self.year = str(meta.get('year'))
                    self.setProperty('item_year', self.year)
                if not self.rating and meta.get('rating'):
                    self.rating = f"{float(meta.get('rating')):.1f}"
                    self.setProperty('item_rating', self.rating)
                if not self.genre and meta.get('genre'):
                    self.genre = str(meta.get('genre'))
                    self.setProperty('item_genre', self.genre)

        if not raw_links:
            self.setProperty('dialog_subtitle', 'No se encontraron fuentes disponibles actualmente.')
            return

        # Ordenar fuentes de manera inteligente:
        # - En Películas: Las de más semillas primero
        # - En Series y Anime: 
        #   1. Packs primero (Temporada 1, 2, etc.)
        #   2. Episodios en estricto orden cronológico (S01E01, S01E02... S02E01...)
        #   3. Si hay duplicados del mismo capítulo, el de más semillas primero
        if self.media_type == 'movies':
            links = sorted(raw_links, key=lambda l: int(l.get('seeds') or 0), reverse=True)
        else:
            def _tv_sort_key(item):
                is_pack = 0 if item.get('is_pack') or '[PACK]' in (item.get('custom_label') or '') else 1
                try:
                    season = int(item.get('season') or 0)
                except (ValueError, TypeError):
                    season = 0
                try:
                    episode = int(item.get('episode') or 0)
                except (ValueError, TypeError):
                    episode = 0
                try:
                    seeds = int(item.get('seeds') or 0)
                except (ValueError, TypeError):
                    seeds = 0
                return (is_pack, season, episode, -seeds)

            links = sorted(raw_links, key=_tv_sort_key)

        self.setProperty('dialog_subtitle', f'Selecciona una versión  •  {len(links)} enlaces disponibles')

        list_items = []
        for l in links:
            seeds = int(l.get('seeds') or 0)
            quality = _clean_quality(l.get('quality'))
            size = l.get('size') or 'Desconocido'
            source = l.get('source') or 'P2P'
            magnet = l.get('magnet') or ''
            
            label = l.get('custom_label') or f"{self.title} ({quality})"
            details = f"Subs Español  |  {size}  |  {source.lower()}"

            li = xbmcgui.ListItem(label=label)
            li.setProperty('quality', quality)
            li.setProperty('details', details)
            li.setProperty('seeds_display', _format_seeds(seeds, in_focus=False))
            li.setProperty('seeds_display_focus', _format_seeds(seeds, in_focus=True))
            li.setProperty('magnet', magnet)
            li.setProperty('item_label', label)
            if l.get('season'):
                li.setProperty('season', str(l.get('season')))
            if l.get('episode'):
                li.setProperty('episode', str(l.get('episode')))
            if l.get('file_index') is not None:
                li.setProperty('file_index', str(l.get('file_index')))
            if l.get('file_name'):
                li.setProperty('file_name', str(l.get('file_name')))
            
            list_items.append(li)

        ctrl.addItems(list_items)
        self.setFocusId(6001)

    def onClick(self, control_id):
        if control_id == 6001:
            ctrl = self.getControl(6001)
            item = ctrl.getSelectedItem()
            if item:
                magnet = item.getProperty('magnet')
                if magnet:
                    label = item.getProperty('item_label') or item.getLabel()
                    self._play_magnet(magnet, label=label, item=item)
                    self._wait_for_player_and_close()
        elif control_id == 6002: # Botón Cerrar
            self.close()

    def onAction(self, action):
        if action.getId() in (xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK):
            self.close()

    def _play_magnet(self, magnet, label='', item=None):
        engine = addon.getSetting('torrent_engine')
        mag_encoded = urllib.parse.quote_plus(magnet)
        
        if engine == "1": # Torrest
            play_url = f"plugin://plugin.video.torrest/play_magnet?magnet={mag_encoded}"
        else: # Elementum (Predeterminado)
            play_url = f"plugin://plugin.video.elementum/play?uri={mag_encoded}"
            if item and item.getProperty('file_index'):
                play_url += f"&index={item.getProperty('file_index')}"

        # Título formateado para el reproductor de Kodi (OSD y barra de pausa)
        if self.media_type in ('series', 'anime') and label:
            display_title = f"{self.title} - {label}"
        else:
            display_title = self.title or label or "Latarr Video"

        li = xbmcgui.ListItem(label=display_title)
        info = {
            'title': display_title,
            'tvshowtitle': self.title if self.media_type in ('series', 'anime') else '',
            'plot': self.plot or '',
            'year': int(self.year) if self.year and str(self.year).isdigit() else 0,
            'genre': self.genre or '',
            'rating': float(self.rating) if self.rating else 0.0,
            'mediatype': 'episode' if self.media_type in ('series', 'anime') else 'movie'
        }
        if item:
            sn = item.getProperty('season')
            ep = item.getProperty('episode')
            if sn and str(sn).isdigit():
                info['season'] = int(sn)
            if ep and str(ep).isdigit():
                info['episode'] = int(ep)

        li.setInfo('video', info)

        art = {}
        if self.poster:
            art['poster'] = self.poster
            art['thumb'] = self.poster
            art['icon'] = self.poster
            art['tvshow.poster'] = self.poster
            art['season.poster'] = self.poster
        if self.fanart:
            art['fanart'] = self.fanart
            art['clearart'] = self.fanart
        if art:
            li.setArt(art)

        if self.poster:
            try:
                li.setIconImage(self.poster)
                li.setThumbnailImage(self.poster)
            except Exception:
                pass
            
        item_playback_data = {
            'tmdb_id': str(self.tmdb_id or ''),
            'media_type': self.media_type,
            'title': self.title,
            'display_title': display_title,
            'poster': self.poster,
            'fanart': self.fanart,
            'plot': self.plot,
            'year': str(self.year or ''),
            'rating': str(self.rating or '7.0'),
            'genre': str(self.genre or ''),
            'magnet': magnet,
            'file_name': item.getProperty('file_name') if item else '',
            'file_index': item.getProperty('file_index') if item else '',
            'season': item.getProperty('season') if item else '',
            'episode': item.getProperty('episode') if item else '',
        }
        history.set_current_playback(item_playback_data)

        # Limpiar la playlist interna de Kodi antes de reproducir para evitar
        # que aparezca el dialogo "Lista de reproduccion" al iniciar
        try:
            pl = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            pl.clear()
        except Exception:
            pass

        xbmc.Player().play(play_url, li)

    def _wait_for_player_and_close(self):
        monitor = xbmc.Monitor()
        player = xbmc.Player()
        started = False
        
        # Esperar hasta 20 minutos (4000 x 0.3s) para torrents con pocas semillas.
        # En cuanto isPlayingVideo() sea True (sin importar cuanto tarde el buffer),
        # se cierra la ventana y se activa pantalla completa de inmediato.
        for _ in range(4000):
            if monitor.abortRequested():
                break
            if player.isPlayingVideo():
                started = True
                break
            monitor.waitForAbort(0.3)

        if started:
            self.played = True
            self.close()
            xbmc.executebuiltin("Dialog.Close(all,true)")
            xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")
        else:
            self.played = False
