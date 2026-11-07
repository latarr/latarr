"""
actors_movies_win.py — Cuadrícula de películas de un actor específico.

Abre el mismo diseño que LatarrCatalogDialog pero poblado con las películas
disponibles de un actor concreto. Al hacer Enter en una película abre sources.py.
"""

import xbmc
import xbmcgui
import xbmcaddon

from .. import api

addon = xbmcaddon.Addon()
POSTER_BASE = "https://image.tmdb.org/t/p/w342"
FANART_BASE = "https://image.tmdb.org/t/p/w1280"


class LatarrActorMoviesDialog(xbmcgui.WindowXMLDialog):
    """Cuadrícula de películas de un actor. Mismo diseño que el catálogo."""

    def __init__(self, *args, **kwargs):
        self.actor_id   = kwargs.pop('actor_id', 0)
        self.actor_name = kwargs.pop('actor_name', 'Actor')
        self.addon_path = kwargs.pop('addon_path', '')
        self.initial_pos = kwargs.pop('initial_pos', 0)
        super().__init__(*args, **kwargs)
        self.initialized = False
        self.played      = False
        self.resume_data = None

    def onInit(self):
        if self.initialized:
            return
        self.initialized = True

        label = f'[B]{self.actor_name.upper()}[/B]'
        self.setProperty('catalog_title', label)

        self._load_movies()

    # ------------------------------------------------------------------ carga
    def _load_movies(self):
        ctrl = self.getControl(8100)
        ctrl.reset()

        data    = api.get_actor_movies(self.actor_id)
        movies  = data.get('results', []) if isinstance(data, dict) else []

        self.setProperty('total_count', str(len(movies)))
        if not movies:
            self.setProperty('selected_title', 'Sin películas disponibles')
            self.setFocusId(8005)
            return

        items = []
        for idx, m in enumerate(movies):
            p_path = m.get('poster_path', '')
            poster  = f"{POSTER_BASE}{p_path}" if p_path else ''
            fanart  = f"{FANART_BASE}{p_path}" if p_path else ''

            try:
                rating = f"{float(m.get('rating', 7.0)):.1f}"
            except (ValueError, TypeError):
                rating = '7.0'

            li = xbmcgui.ListItem(label=m.get('title') or 'Sin Título')
            li.setArt({'poster': poster, 'thumb': poster, 'fanart': fanart})
            li.setProperty('title',     m.get('title') or 'Sin Título')
            li.setProperty('plot',      m.get('overview') or '')
            li.setProperty('year',      str(m.get('year') or ''))
            li.setProperty('rating',    rating)
            li.setProperty('genre',     m.get('character') or '')   # personaje que interpreta
            li.setProperty('tmdb_id',   str(m.get('tmdb_id') or ''))
            li.setProperty('media_type', 'movies')
            li.setProperty('abs_index', str(idx))
            items.append(li)

        ctrl.addItems(items)
        self.setFocusId(8100)
        if self.initial_pos > 0:
            try:
                ctrl.selectItem(min(self.initial_pos, len(items) - 1))
            except Exception:
                pass
        self._update_info()

    # ----------------------------------------------------------------- acciones
    def _update_info(self):
        try:
            ctrl = self.getControl(8100)
            item = ctrl.getSelectedItem()
            if item:
                self.setProperty('selected_title',  item.getProperty('title') or item.getLabel())
                self.setProperty('selected_year',   item.getProperty('year') or '')
                self.setProperty('selected_rating', item.getProperty('rating') or '7.0')
                # Mostrar el personaje que interpreta en lugar del género
                character = item.getProperty('genre')
                self.setProperty('selected_genre', f'Como: {character}' if character else '')
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
            self._update_info()

    def onClick(self, control_id):
        if control_id == 8100:
            ctrl = self.getControl(8100)
            item = ctrl.getSelectedItem()
            if item:
                self._open_sources(item)
        elif control_id == 8005:   # Volver
            self.close()

    def _open_sources(self, item):
        tmdb_id = item.getProperty('tmdb_id')
        if not tmdb_id:
            return

        idx_prop = item.getProperty('abs_index')
        pos = int(idx_prop) if idx_prop and idx_prop.isdigit() else 0

        from .sources import LatarrSourcesDialog
        dlg = LatarrSourcesDialog(
            'script-latarr-sources.xml',
            self.addon_path,
            defaultSkin='Default',
            defaultRes='1080i',
            tmdb_id=tmdb_id,
            media_type='movies',
            title=item.getProperty('title'),
            poster=item.getArt('poster'),
            fanart=item.getArt('fanart') or item.getArt('poster'),
            plot=item.getProperty('plot'),
            year=item.getProperty('year'),
            rating=item.getProperty('rating'),
            genre='',
        )
        dlg.doModal()
        was_played = getattr(dlg, 'played', False)
        del dlg

        if was_played:
            self.played = True
            self.resume_data = {
                'section':    'actor_movies',
                'actor_id':   self.actor_id,
                'actor_name': self.actor_name,
                'pos':        pos,
            }
            self.close()
