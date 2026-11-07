"""
actors_win.py — Cuadrícula de Actores para Latarr (Colecciones).

Muestra la cuadrícula de actores con más películas disponibles en nuestras bases
de datos. Al hacer Enter en un actor abre actors_movies_win con sus películas.
Reutiliza el mismo XML y lógica de LatarrCatalogDialog.
"""

import xbmc
import xbmcgui
import xbmcaddon

from .. import api

addon = xbmcaddon.Addon()
PROFILE_BASE = "https://image.tmdb.org/t/p/w342"   # foto de perfil del actor
PROFILE_WIDE = "https://image.tmdb.org/t/p/w780"   # para fanart/fondo


class LatarrActorsDialog(xbmcgui.WindowXMLDialog):
    """Ventana de cuadrícula de actores. Idéntica en diseño al catálogo."""

    def __init__(self, *args, **kwargs):
        self.addon_path = kwargs.pop('addon_path', '')
        self.initial_pos = kwargs.pop('initial_pos', 0)
        super().__init__(*args, **kwargs)
        self.initialized = False
        self.played = False
        self.resume_data = None
        self._actors = []

    def onInit(self):
        if self.initialized:
            return
        self.initialized = True
        self.setProperty('catalog_title', '[B]COLECCIONES[/B] [COLOR FF8E95A5]POR ACTOR[/COLOR]')
        self._load_actors()

    # ------------------------------------------------------------------ carga
    def _load_actors(self):
        ctrl = self.getControl(8100)
        ctrl.reset()

        actors = api.get_actors(min_movies=5)
        if not actors:
            self.setProperty('total_count', '0')
            self.setProperty('selected_title', 'Sin actores disponibles aún')
            self.setFocusId(8005)
            return

        self._actors = actors
        self.setProperty('total_count', str(len(actors)))

        items = []
        for a in actors:
            profile_url = f"{PROFILE_BASE}{a['profile_path']}" if a.get('profile_path') else ''
            li = xbmcgui.ListItem(label=a['name'])
            li.setArt({
                'poster': profile_url,
                'thumb':  profile_url,
                'fanart': f"{PROFILE_WIDE}{a['profile_path']}" if a.get('profile_path') else '',
            })
            li.setProperty('actor_id',   str(a['id']))
            li.setProperty('actor_name', a['name'])
            li.setProperty('count',      str(a['count']))
            li.setProperty('abs_index',  str(actors.index(a)))
            items.append(li)

        ctrl.addItems(items)
        self.setFocusId(8100)
        self._update_info()

        if self.initial_pos > 0:
            try:
                ctrl.selectItem(min(self.initial_pos, len(actors) - 1))
            except Exception:
                pass

    # ----------------------------------------------------------------- acciones
    def _update_info(self):
        try:
            ctrl = self.getControl(8100)
            item = ctrl.getSelectedItem()
            if item:
                name  = item.getProperty('actor_name') or item.getLabel()
                count = item.getProperty('count') or '?'
                self.setProperty('selected_title',  name)
                self.setProperty('selected_year',   '')
                self.setProperty('selected_rating', '')
                self.setProperty('selected_genre',  f'{count} películas disponibles')
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
                self._open_actor(item)
        elif control_id == 8005:   # Volver a Inicio
            self.close()

    def _open_actor(self, item):
        actor_id   = item.getProperty('actor_id')
        actor_name = item.getProperty('actor_name') or item.getLabel()
        pos = self.getControl(8100).getSelectedPosition()

        if not actor_id:
            return

        from .actors_movies_win import LatarrActorMoviesDialog
        dlg = LatarrActorMoviesDialog(
            'script-latarr-actor-movies.xml',
            self.addon_path,
            defaultSkin='Default',
            defaultRes='1080i',
            actor_id=int(actor_id),
            actor_name=actor_name,
            addon_path=self.addon_path,
        )
        dlg.doModal()
        was_played = getattr(dlg, 'played', False)
        resume     = getattr(dlg, 'resume_data', None)
        del dlg

        if was_played:
            self.played = True
            # Agregar posicion del actor para volver a ella al salir de actor_movies
            rd = resume or {'section': 'actors', 'pos': pos}
            if rd.get('section') == 'actor_movies':
                rd.setdefault('actors_pos', pos)
            self.resume_data = rd
            self.close()
