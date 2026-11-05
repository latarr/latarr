import xbmc
import xbmcgui
import xbmcaddon

addon = xbmcaddon.Addon()
POSTER_BASE = "https://image.tmdb.org/t/p/w300"

class LatarrSearchDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.query = kwargs.pop('query', '')
        self.items = kwargs.pop('items', [])
        self.addon_path = kwargs.pop('addon_path', '')
        self.initial_pos = kwargs.pop('initial_pos', 0)
        super().__init__(*args, **kwargs)
        self.initialized = False
        self.played = False
        self.resume_data = None

    def onInit(self):
        if self.initialized:
            return
        self.initialized = True

        self.setProperty('dialog_title', 'Resultados de Búsqueda')
        subtitle = f"{len(self.items)} resultado{'s' if len(self.items) != 1 else ''} para '{self.query}' • Pulsa Enter para ver fuentes"
        self.setProperty('dialog_subtitle', subtitle)

        self._load_results()

        if self.initial_pos > 0:
            try:
                ctrl = self.getControl(7001)
                ctrl.selectItem(self.initial_pos)
            except Exception:
                pass

    def _load_results(self):
        ctrl = self.getControl(7001)
        ctrl.reset()

        list_items = []
        for item in self.items:
            title = item.get('clean_title') or item.get('title') or 'Sin Título'
            year = str(item.get('year') or '')
            genre = str(item.get('genre') or 'Cine')
            r = item.get('rating')
            rating_str = f"{float(r):.1f}" if r else "7.0"
            m_type = item.get('media_type', 'movies')
            is_anime = item.get('is_anime', False) or m_type == 'anime'

            if is_anime:
                type_label = "ANIME"
            elif m_type == 'series':
                type_label = "SERIE"
            else:
                type_label = "PELÍCULA"
            
            p_path = item.get('poster_path')
            thumb_url = f"{POSTER_BASE}{p_path}" if p_path else ''

            overview = item.get('overview') or ''
            overview_short = (overview[:90] + '...') if len(overview) > 90 else overview
            details = f"{year}  •  {genre}  •  {overview_short}" if overview_short else f"{year}  •  {genre}"

            li = xbmcgui.ListItem(label=title)
            li.setArt({'thumb': thumb_url, 'poster': thumb_url})
            li.setProperty('details', details)
            li.setProperty('badge', f"★ {rating_str}  {type_label}")
            li.setProperty('tmdb_id', str(item.get('tmdb_id') or ''))
            li.setProperty('media_type', m_type)
            li.setProperty('title', title)
            li.setProperty('plot', overview)
            li.setProperty('year', year)
            li.setProperty('genre', genre)
            li.setProperty('rating', rating_str)

            list_items.append(li)

        ctrl.addItems(list_items)
        self.setFocusId(7001)

    def onClick(self, control_id):
        if control_id == 7001:
            ctrl = self.getControl(7001)
            item = ctrl.getSelectedItem()
            if item:
                self._open_sources(item)
        elif control_id == 7002: # Volver
            self.close()

    def onAction(self, action):
        action_id = action.getId()
        if action_id in (xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK):
            self.close()

    def _open_sources(self, item):
        tmdb_id = item.getProperty('tmdb_id')
        media_type = item.getProperty('media_type') or 'movies'
        title = item.getProperty('title')

        if not tmdb_id:
            return

        ctrl = self.getControl(7001)
        current_pos = ctrl.getSelectedPosition()

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
                # Para series o anime desde búsqueda: regresar directo a fuentes (episodios)
                # y al pulsar Atrás en fuentes, regresar a la búsqueda sobre este ítem
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
                        'section': 'search',
                        'query': self.query,
                        'items': self.items,
                        'pos': current_pos
                    }
                }
            else:
                # Para películas desde búsqueda: volver a los resultados sobre la misma película
                self.resume_data = {
                    'section': 'search',
                    'query': self.query,
                    'items': self.items,
                    'pos': current_pos
                }
            self.close()
