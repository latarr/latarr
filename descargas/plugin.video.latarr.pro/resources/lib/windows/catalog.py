import math
import xbmc
import xbmcgui
import xbmcaddon
from .. import api

addon = xbmcaddon.Addon()
POSTER_BASE = "https://image.tmdb.org/t/p/w342"
FANART_BASE = "https://image.tmdb.org/t/p/w1280"

class LatarrCatalogDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.media_type = kwargs.pop('media_type', 'movies')
        self.addon_path = kwargs.pop('addon_path', '')
        self.current_year = kwargs.pop('initial_year', 'Todos')
        self.current_genre = kwargs.pop('initial_genre', 'Todos')
        self.offset = kwargs.pop('initial_offset', 0)
        self.initial_pos = kwargs.pop('initial_pos', 0)
        super().__init__(*args, **kwargs)
        self.initialized = False
        self.batch_size = 40
        self.total = 0
        self.played = False
        self.resume_data = None
        self.is_loading = False
        self.years_cache = []
        self.genres_cache = []

    def onInit(self):
        if self.initialized:
            return
        self.initialized = True

        if self.media_type == 'movies':
            title_text = "[B]CATÁLOGO[/B] [COLOR FF8E95A5]PELÍCULAS[/COLOR]"
        elif self.media_type == 'series':
            title_text = "[B]CATÁLOGO[/B] [COLOR FF8E95A5]SERIES DE TV[/COLOR]"
        else:
            title_text = "[B]CATÁLOGO[/B] [COLOR FF8E95A5]ANIME[/COLOR]"

        self.setProperty('catalog_title', title_text)
        self._load_catalog(reset=True)

        if self.initial_pos > 0:
            try:
                ctrl = self.getControl(8100)
                ctrl.selectItem(self.initial_pos)
                self._update_selected_info()
            except Exception:
                pass

    def _create_list_items(self, items, start_index=0):
        list_items = []
        for i, item in enumerate(items):
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

            r = item.get('rating')
            rating_str = f"{float(r):.1f}" if r else "7.0"

            li.setProperty('title', title)
            li.setProperty('plot', item.get('overview') or '')
            li.setProperty('year', str(item.get('year') or ''))
            li.setProperty('genre', str(item.get('genre') or 'Cine'))
            li.setProperty('rating', rating_str)
            li.setProperty('tmdb_id', str(item.get('tmdb_id') or ''))
            li.setProperty('media_type', self.media_type)
            li.setProperty('abs_index', str(start_index + i))
            list_items.append(li)
        return list_items

    def _load_catalog(self, reset=True):
        ctrl = self.getControl(8100)
        if reset:
            ctrl.reset()
            self.offset = 0

        fetch_limit = max(self.batch_size, self.initial_pos + 14) if reset and self.initial_pos > 0 else self.batch_size
        data = api.get_catalog_items(
            media_type=self.media_type,
            year=self.current_year,
            genre=self.current_genre,
            offset=self.offset,
            limit=fetch_limit
        )

        items = data.get('results', [])
        self.total = data.get('total', len(items))

        list_items = self._create_list_items(items, start_index=0)
        ctrl.addItems(list_items)

        # Actualizar propiedades de la interfaz
        self.setProperty('filter_year', self.current_year)
        self.setProperty('filter_genre', self.current_genre)
        self.setProperty('total_count', str(self.total))

        if reset:
            self.setFocusId(8100)
            self._update_selected_info()

    def _load_more(self):
        if self.is_loading:
            return
        ctrl = self.getControl(8100)
        current_loaded = ctrl.size()
        if current_loaded >= self.total:
            return

        self.is_loading = True
        try:
            cur_item = ctrl.getSelectedItem()
            cur_abs = None
            if cur_item:
                idx_prop = cur_item.getProperty('abs_index')
                if idx_prop and idx_prop.isdigit():
                    cur_abs = int(idx_prop)

            data = api.get_catalog_items(
                media_type=self.media_type,
                year=self.current_year,
                genre=self.current_genre,
                offset=current_loaded,
                limit=self.batch_size
            )
            items = data.get('results', []) if data else []
            if items:
                list_items = self._create_list_items(items, start_index=current_loaded)
                ctrl.addItems(list_items)
                if cur_abs is not None:
                    try:
                        ctrl.selectItem(cur_abs)
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            self.is_loading = False

    def _update_selected_info(self):
        try:
            ctrl = self.getControl(8100)
            item = ctrl.getSelectedItem()
            if item:
                self.setProperty('selected_title', item.getProperty('title') or item.getLabel())
                self.setProperty('selected_year', item.getProperty('year') or '')
                self.setProperty('selected_rating', item.getProperty('rating') or '7.0')
                self.setProperty('selected_genre', item.getProperty('genre') or '')
        except Exception:
            pass

    def onAction(self, action):
        action_id = action.getId()
        if action_id in (xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK):
            self.close()
            return

        try:
            super().onAction(action)
        except Exception:
            pass

        if self.getFocusId() == 8100:
            self._update_selected_info()

            # Al navegar hacia abajo, pre-cargar el siguiente bloque sin interrumpir la navegación
            if action_id == xbmcgui.ACTION_MOVE_DOWN:
                ctrl = self.getControl(8100)
                cur_item = ctrl.getSelectedItem()
                if cur_item:
                    idx_prop = cur_item.getProperty('abs_index')
                    if idx_prop and idx_prop.isdigit():
                        cur_abs = int(idx_prop)
                        total_loaded = ctrl.size()
                        # Si quedan 14 o menos ítems (2 filas de 7), pedir el siguiente bloque
                        if cur_abs >= (total_loaded - 14):
                            self._load_more()

    def onClick(self, control_id):
        if control_id == 8100: # Clic en un póster
            ctrl = self.getControl(8100)
            item = ctrl.getSelectedItem()
            if item:
                self._open_sources(item)

        elif control_id == 8001: # Filtro Año
            self._select_year()

        elif control_id == 8002: # Filtro Género
            self._select_genre()

        elif control_id == 8005: # Volver a Inicio
            self.close()

    def _select_year(self):
        raw_years = api.get_catalog_years(self.media_type)
        years_list = ['Todos'] + [str(y.get('year')) for y in raw_years if y.get('year')]
        idx = xbmcgui.Dialog().select('Seleccionar Año', years_list)
        if idx >= 0:
            self.current_year = years_list[idx]
            self.offset = 0
            self._load_catalog(reset=True)

    def _select_genre(self):
        raw_genres = api.get_catalog_genres(self.media_type, year=self.current_year)
        genres_list = ['Todos'] + [str(g.get('genre')) for g in raw_genres if g.get('genre')]
        idx = xbmcgui.Dialog().select('Seleccionar Género', genres_list)
        if idx >= 0:
            self.current_genre = genres_list[idx]
            self.offset = 0
            self._load_catalog(reset=True)

    def _open_sources(self, item):
        tmdb_id = item.getProperty('tmdb_id')
        media_type = item.getProperty('media_type') or self.media_type
        title = item.getProperty('title')

        if not tmdb_id:
            return

        ctrl = self.getControl(8100)
        idx_prop = item.getProperty('abs_index')
        current_pos = int(idx_prop) if idx_prop and idx_prop.isdigit() else 0

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
            fanart=item.getArt('fanart') or item.getArt('poster'),
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
                # Para series o anime, regresar directo a la pantalla de fuentes (episodios)
                self.resume_data = {
                    'section': 'sources',
                    'tmdb_id': tmdb_id,
                    'media_type': media_type,
                    'title': title,
                    'poster': item.getArt('poster'),
                    'fanart': item.getArt('fanart') or item.getArt('poster'),
                    'plot': item.getProperty('plot'),
                    'year': item.getProperty('year'),
                    'rating': item.getProperty('rating'),
                    'genre': item.getProperty('genre'),
                    'parent': {
                        'section': 'catalog',
                        'media_type': self.media_type,
                        'offset': self.offset,
                        'year': self.current_year,
                        'genre': self.current_genre,
                        'pos': current_pos
                    }
                }
            else:
                # Para películas, volver al catálogo sobre la misma película
                self.resume_data = {
                    'section': 'catalog',
                    'media_type': self.media_type,
                    'offset': self.offset,
                    'year': self.current_year,
                    'genre': self.current_genre,
                    'pos': current_pos
                }
            self.close()
