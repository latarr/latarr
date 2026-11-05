import os
import xbmc
import xbmcgui
import xbmcaddon
from .. import api

addon = xbmcaddon.Addon()

# Colores por plataforma para las etiquetas
PLATFORM_COLORS = {
    'Arcade':   'FFFF6B00',  # Naranja fichines
    'Neo-Geo':  'FFCC0000',  # Rojo SNK
    'SNES':     'FF7B2D8B',  # Violeta Nintendo
    'Genesis':  'FF0055AA',  # Azul Sega
    'NES':      'FFE40000',  # Rojo Nintendo
    'Todos':    'FFAAAAAA',
}

PLATFORMS = ['Todos', 'Arcade', 'Neo-Geo']


class LatarrRetroDialog(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        self.addon_path    = kwargs.pop('addon_path', addon.getAddonInfo('path'))
        self.plataforma    = 'Todos'
        self._juegos_all   = []
        self._juegos_vista = []
        self._closed       = False
        super().__init__(*args, **kwargs)

    def onInit(self):
        self._juegos_all = api.get_retro_games()
        self.setProperty('retro_total', str(len(self._juegos_all)))
        self._render_platform_tabs()
        self._render_games(self._juegos_all)
        try:
            self.setFocusId(6001)  # Foco en la lista de juegos al entrar
        except Exception:
            pass

    # ── Pestaña de plataformas (IDs 7001, 7002, 7003) ──────────────
    def _render_platform_tabs(self):
        """Actualiza los botones de filtro marcando el activo."""
        for i, plat in enumerate(PLATFORMS):
            ctrl_id = 7001 + i
            try:
                btn = self.getControl(ctrl_id)
                btn.setLabel(plat)
                # Resaltar activo
                if plat == self.plataforma:
                    btn.setLabel(f'[B]{plat}[/B]')
            except Exception:
                pass

    # ── Lista de juegos (Container 6001) ───────────────────────────
    def _render_games(self, juegos):
        self._juegos_vista = juegos
        try:
            ctrl = self.getControl(6001)
            ctrl.reset()
            list_items = []

            for j in juegos:
                titulo    = j.get('titulo', '')
                plat      = j.get('plataforma', 'Arcade')
                anio      = str(j.get('anio', ''))
                jugadores = j.get('jugadores', 1)
                desc      = j.get('descripcion', '')
                color     = PLATFORM_COLORS.get(plat, 'FFAAAAAA')
                poster    = self._get_poster(j)

                li = xbmcgui.ListItem(label=titulo)
                li.setArt({
                    'poster': poster,
                    'thumb':  poster,
                    'icon':   poster,
                })
                li.setProperty('titulo',    titulo)
                li.setProperty('plataforma', plat)
                li.setProperty('anio',      anio)
                li.setProperty('jugadores', str(jugadores))
                li.setProperty('descripcion', desc)
                li.setProperty('color',     color)
                li.setProperty('juego_id',  j.get('id', ''))
                li.setProperty('plat_label', f'[COLOR {color}]{plat} · {anio}[/COLOR]')

                jugs_txt = f'[COLOR FFAAAAAA]{jugadores} Jugador{"es" if jugadores > 1 else ""}[/COLOR]'
                li.setProperty('jugadores_label', jugs_txt)

                list_items.append(li)

            ctrl.addItems(list_items)
            self._update_hero(0)
        except Exception as e:
            xbmc.log(f'[LATARR-RETRO] Error renderizando juegos: {e}', xbmc.LOGERROR)

    def _get_poster(self, juego):
        """Busca el poster local; si no existe usa icono genérico del addon."""
        juego_id  = juego.get('id', '')
        plataforma = juego.get('plataforma', 'Arcade').lower().replace('-', '')
        
        # Buscar poster en la carpeta local del addon
        poster_path = os.path.normpath(os.path.join(
            self.addon_path, 'catalogo', 'retro', 'posters', f'{juego_id}.png'
        ))
        if os.path.exists(poster_path):
            return poster_path

        # Fallback: icono genérico por plataforma
        generic = os.path.normpath(os.path.join(
            self.addon_path, 'resources', 'skins', 'Default', 'media',
            'retro', f'{plataforma}.png'
        ))
        if os.path.exists(generic):
            return generic

        # Último recurso: icono del addon
        return os.path.normpath(os.path.join(self.addon_path, 'icon.png'))

    def _update_hero(self, pos):
        """Actualiza el panel de info lateral con el juego seleccionado."""
        try:
            if not self._juegos_vista or pos >= len(self._juegos_vista):
                return
            j     = self._juegos_vista[pos]
            color = PLATFORM_COLORS.get(j.get('plataforma', ''), 'FFAAAAAA')
            self.setProperty('retro_titulo',    j.get('titulo', ''))
            self.setProperty('retro_desc',      j.get('descripcion', ''))
            self.setProperty('retro_plat',      j.get('plataforma', ''))
            self.setProperty('retro_anio',      str(j.get('anio', '')))
            self.setProperty('retro_jugadores', str(j.get('jugadores', 1)))
            self.setProperty('retro_color',     color)
            self.setProperty('retro_poster',    self._get_poster(j))
        except Exception as e:
            xbmc.log(f'[LATARR-RETRO] Error actualizando hero: {e}', xbmc.LOGERROR)

    # ── Eventos ─────────────────────────────────────────────────────
    def onAction(self, action):
        action_id = action.getId()

        if action_id in (xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK):
            self._closed = True
            self.close()
            return

        # Actualizar hero al navegar verticalmente en la lista
        if action_id in (xbmcgui.ACTION_MOVE_UP, xbmcgui.ACTION_MOVE_DOWN):
            try:
                super().onAction(action)
                ctrl = self.getControl(6001)
                self._update_hero(ctrl.getSelectedPosition())
                return
            except Exception:
                pass

        try:
            super().onAction(action)
        except Exception:
            pass

    def onClick(self, control_id):
        # ── Filtros de plataforma ──
        if control_id in (7001, 7002, 7003):
            idx = control_id - 7001
            self.plataforma = PLATFORMS[idx]
            juegos = api.get_retro_games_by_platform(self.plataforma)
            self._render_platform_tabs()
            self._render_games(juegos)
            try:
                self.setFocusId(6001)
            except Exception:
                pass
            return

        # ── Clic en un juego ──
        if control_id == 6001:
            try:
                ctrl = self.getControl(6001)
                pos  = ctrl.getSelectedPosition()
                if pos < 0 or pos >= len(self._juegos_vista):
                    return
                juego = self._juegos_vista[pos]
                self._launch_game(juego)
            except Exception as e:
                xbmc.log(f'[LATARR-RETRO] Error onClick juego: {e}', xbmc.LOGERROR)
            return

        # ── Botón Volver ──
        if control_id == 6099:
            self._closed = True
            self.close()

    def _launch_game(self, juego):
        """Muestra confirmación y lanza el juego."""
        titulo = juego.get('titulo', 'Juego')

        # Confirmación antes de descargar
        plat = juego.get('plataforma', '')
        desc = juego.get('descripcion', '')
        jugs = juego.get('jugadores', 1)

        ok = xbmcgui.Dialog().yesno(
            f'🕹  {titulo}',
            f'[B]{plat}[/B] · {juego.get("anio", "")}\n\n'
            f'{desc}\n\n'
            f'[COLOR FFAAAAAA]{jugs} Jugador{"es" if jugs > 1 else ""}[/COLOR]\n\n'
            '¿Iniciar juego?',
            nolabel='Cancelar',
            yeslabel='¡Jugar!'
        )

        if not ok:
            return

        # Lanzar vía api
        api.launch_retro_game(juego)
