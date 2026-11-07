import time
import xbmc
import xbmcgui
import xbmcaddon

from .. import history

addon = xbmcaddon.Addon()

_ACTION_CONTEXT = getattr(xbmcgui, 'ACTION_CONTEXT_MENU', 117)
_ACTION_DELETE = getattr(xbmcgui, 'ACTION_DELETE_ITEM', 80)


def _hace(ts):
    """'hace 5 min', 'hace 3 h', 'ayer', 'hace 4 días'..."""
    try:
        d = max(0.0, time.time() - float(ts))
    except (ValueError, TypeError):
        return ''
    if d < 3600:
        m = int(d // 60)
        return 'hace un momento' if m < 1 else f'hace {m} min'
    if d < 86400:
        return f'hace {int(d // 3600)} h'
    days = int(d // 86400)
    if days == 1:
        return 'ayer'
    if days < 30:
        return f'hace {days} días'
    if days < 365:
        mo = days // 30
        return f'hace {mo} mes' if mo == 1 else f'hace {mo} meses'
    return 'hace más de un año'


def _type_label(media_type):
    if media_type == 'anime':
        return 'ANIME'
    if media_type == 'series':
        return 'SERIE'
    return 'PELÍCULA'


class LatarrHistoryDialog(xbmcgui.WindowXMLDialog):
    """Historial informativo: qué series/anime/películas has empezado y hasta dónde llegaste.
    No reproduce nada: al elegir un título se abre su pantalla de fuentes para escoger el enlace."""

    def __init__(self, *args, **kwargs):
        self.addon_path = kwargs.pop('addon_path', '')
        self.initial_pos = kwargs.pop('initial_pos', 0)
        super().__init__(*args, **kwargs)
        self.initialized = False
        self.played = False
        self.resume_data = None
        self.entries = []

    def onInit(self):
        if self.initialized:
            return
        self.initialized = True
        self.setProperty('dialog_title', 'Historial')
        self._load(select=self.initial_pos)

    # ------------------------------------------------------------------ datos
    def _details_line(self, e):
        media_type = e.get('media_type', 'movies')
        hace = _hace(e.get('updated_at'))
        if media_type in ('series', 'anime'):
            label = e.get('episode_label') or history.episode_label(e.get('season'), e.get('episode'))
            base = f"Viste hasta {label}" if label else "Capítulo sin identificar"
            if e.get('finished'):
                estado = "completado"
            else:
                estado = f"{e.get('resume_time', '00:00')} ({int(e.get('percent', 0))}%)"
            partes = [base, estado, hace]
        else:
            tot = history._format_seconds(e.get('total_time', 0))
            partes = [f"Lo dejaste en {e.get('resume_time', '00:00')} de {tot} ({int(e.get('percent', 0))}%)", hace]
        return "  •  ".join(p for p in partes if p)

    def _load(self, select=0):
        self.entries = history.get_history()
        ctrl = self.getControl(7001)
        ctrl.reset()

        n = len(self.entries)
        if n == 0:
            self.setProperty('dialog_subtitle', 'Aún no hay nada en el historial. Lo que empieces a ver aparecerá aquí.')
            self.setFocusId(7002)
            return

        self.setProperty(
            'dialog_subtitle',
            f"{n} título{'s' if n != 1 else ''}  •  Enter: opciones del título  •  Abajo: opciones generales"
        )

        items = []
        for e in self.entries:
            title = e.get('title') or e.get('display_title') or 'Sin Título'
            poster = e.get('poster') or ''
            fanart = e.get('fanart') or poster
            try:
                rating = f"{float(e.get('rating')):.1f}"
            except (ValueError, TypeError):
                rating = '7.0'
            media_type = e.get('media_type', 'movies')

            li = xbmcgui.ListItem(label=title)
            li.setArt({'thumb': poster, 'poster': poster, 'fanart': fanart})
            li.setProperty('details', self._details_line(e))
            li.setProperty('badge', f"★ {rating}  {_type_label(media_type)}")
            li.setProperty('tmdb_id', str(e.get('tmdb_id') or ''))
            li.setProperty('media_type', media_type)
            li.setProperty('title', title)
            li.setProperty('plot', e.get('plot') or '')
            li.setProperty('year', str(e.get('year') or ''))
            li.setProperty('genre', str(e.get('genre') or ''))
            li.setProperty('rating', rating)
            li.setProperty('entry_id', str(e.get('id') or ''))
            items.append(li)

        ctrl.addItems(items)
        self.setFocusId(7001)
        if select > 0:
            try:
                ctrl.selectItem(min(select, n - 1))
            except Exception:
                pass

    # --------------------------------------------------------------- acciones
    def onClick(self, control_id):
        if control_id == 7001:
            ctrl = self.getControl(7001)
            item = ctrl.getSelectedItem()
            if not item:
                return

            media_type = item.getProperty('media_type') or 'movies'
            opcion_fuentes = "Ver detalles, capítulos y fuentes" if media_type in ('series', 'anime') else "Ver detalles y fuentes"
            opciones = [opcion_fuentes, "Quitar de la lista"]

            sel = xbmcgui.Dialog().contextmenu(opciones)
            if sel == 0:
                self._open_sources(item)
            elif sel == 1:
                self._remove_selected()

        elif control_id == 7002:
            self.close()

        elif control_id == 7003:
            if self.entries and xbmcgui.Dialog().yesno('Latarr', '¿Vaciar todo el historial?'):
                history.clear_all()
                self._load()

    def onAction(self, action):
        action_id = action.getId()
        if action_id in (xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK):
            self.close()
            return
        if action_id in (_ACTION_CONTEXT, _ACTION_DELETE) and self.getFocusId() == 7001:
            self._remove_selected()

    def _remove_selected(self):
        """Quita del historial el título seleccionado en la lista."""
        ctrl = self.getControl(7001)
        item = ctrl.getSelectedItem()
        if not item:
            return
        pos = ctrl.getSelectedPosition()
        title = item.getProperty('title') or item.getLabel()

        history.delete_item(item.getProperty('entry_id'))
        xbmcgui.Dialog().notification('Latarr', f'Quitado de la lista: {title}', xbmcgui.NOTIFICATION_INFO, 1500)
        # Se queda en la misma posición (el siguiente título sube) para seguir navegando cómodo
        self._load(select=pos)

    def _open_sources(self, item):
        tmdb_id = item.getProperty('tmdb_id')
        media_type = item.getProperty('media_type') or 'movies'
        title = item.getProperty('title')

        if not tmdb_id:
            xbmcgui.Dialog().notification('Latarr', 'Este título no tiene datos para abrir sus fuentes', xbmcgui.NOTIFICATION_WARNING, 2500)
            return

        pos = self.getControl(7001).getSelectedPosition()
        poster = item.getArt('poster')
        fanart = item.getArt('fanart') or poster

        from .sources import LatarrSourcesDialog
        dlg = LatarrSourcesDialog(
            'script-latarr-sources.xml',
            self.addon_path,
            defaultSkin='Default',
            defaultRes='1080i',
            tmdb_id=tmdb_id,
            media_type=media_type,
            title=title,
            poster=poster,
            fanart=fanart,
            plot=item.getProperty('plot'),
            year=item.getProperty('year'),
            rating=item.getProperty('rating'),
            genre=item.getProperty('genre')
        )
        dlg.doModal()
        was_played = getattr(dlg, 'played', False)
        del dlg

        if not was_played:
            return

        self.played = True
        parent = {'section': 'history', 'pos': pos}
        if media_type in ('series', 'anime'):
            # Series/anime: al terminar, volver a la lista de capítulos; Atrás → Historial
            self.resume_data = {
                'section': 'sources',
                'tmdb_id': tmdb_id,
                'media_type': media_type,
                'title': title,
                'poster': poster,
                'fanart': fanart,
                'plot': item.getProperty('plot'),
                'year': item.getProperty('year'),
                'rating': item.getProperty('rating'),
                'genre': item.getProperty('genre'),
                'parent': parent
            }
        else:
            self.resume_data = parent
        self.close()
