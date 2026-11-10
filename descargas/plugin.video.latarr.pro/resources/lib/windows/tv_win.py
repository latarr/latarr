"""
tv_win.py — LATARR PRO: Televisión en Vivo con Deportes Premium.

Pantalla única:
  - Fila 1: 7 tarjetas deportivas PRO (ESPN, Champions, Libertadores, etc.)
  - Fila 2+: Países normales (Chile, Argentina, Perú, etc.)
Reproducción con pool de 26 cuentas IPTV con anti-caídas automático.
"""

import os
import json
import xbmc
import xbmcgui
import xbmcaddon

from .. import api

addon = xbmcaddon.Addon()

# Colores y etiquetas para las tarjetas deportivas
SPORTS_COLOR = 'FFCC0000'  # Rojo premium
SPORTS_BADGE = '[COLOR FFFFAA00][B]⚡ PRO[/B][/COLOR]'


class LatarrTVDialog(xbmcgui.WindowXMLDialog):
    """Ventana de Televisión en Vivo con Deportes PRO + Países."""

    def __init__(self, *args, **kwargs):
        self.addon_path = kwargs.pop('addon_path', '')
        self.initial_country = kwargs.pop('initial_country', None)
        self.initial_category = kwargs.pop('initial_category', 'Todas')
        self.initial_pos = kwargs.pop('initial_pos', 0)
        self.is_zapping = kwargs.pop('is_zapping', False)
        super().__init__(*args, **kwargs)

        self.initialized = False
        self.played = False
        self.resume_data = None

        # view_mode: 'countries' (deportes + paises) | 'channels' | 'sports_channels'
        self.view_mode = 'countries'
        self.countries = []
        self.sports_cats = []
        self.raw_channels = []
        self.channels = []
        self.categories = ['Todas']
        self.current_country = self.initial_country
        self.current_country_name = ''
        self.current_category = self.initial_category
        self.current_sport_id = None
        self.current_sport_name = ''
        self._last_country_pos = 0

    def onInit(self):
        if self.initialized:
            return
        self.initialized = True

        self._update_header_mode()

        if self.initial_country:
            self._show_channels(self.initial_country, category=self.initial_category, select_pos=self.initial_pos)
        else:
            self._show_countries(select_pos=self.initial_pos)

    def _update_header_mode(self):
        if self.is_zapping:
            self.setProperty('tv_title', '[B]ZAPPING[/B] [COLOR FFFFAA00]TV[/COLOR] [COLOR FF8E95A5]PRO[/COLOR]')
            self.setProperty('btn_mode_label', '📺 TV en Vivo')
            self.setProperty('btn_back_label', '← Volver a TV')
        else:
            self.setProperty('tv_title', '[B]LATARR[/B] [COLOR FFFFAA00]PRO[/COLOR] [COLOR FF8E95A5]EN VIVO[/COLOR]')
            self.setProperty('btn_mode_label', '📡 Zapping TV')
            self.setProperty('btn_back_label', 'Volver a Inicio')

    def _toggle_mode(self):
        self.is_zapping = not self.is_zapping
        self.countries = []
        self.sports_cats = []
        self.current_country = None
        self.current_category = 'Todas'
        self._last_country_pos = 0
        self._show_countries(select_pos=0)

    # ------------------------------------------------------------------ Vistas
    def _show_countries(self, select_pos=0):
        """Muestra PRIMERO las 7 categorías deportivas PRO, LUEGO los países."""
        self.view_mode = 'countries'
        ctrl = self.getControl(8100)
        ctrl.reset()

        self._update_header_mode()
        self.setProperty('filter_country', 'Países Zapping' if self.is_zapping else 'Deportes + Países')
        self.setProperty('filter_category', 'Todas')

        if self.is_zapping:
            if not self.countries:
                self.countries = api.get_zapping_countries()
            self.sports_cats = []
        else:
            if not self.countries:
                self.countries = api.get_tv_countries()
            if not self.sports_cats:
                self.sports_cats = api.get_sports_categories()

        flags_dir = os.path.join(self.addon_path, 'resources', 'skins', 'Default', 'media', 'flags')
        sports_dir = os.path.join(self.addon_path, 'resources', 'skins', 'Default', 'media', 'sports')

        items = []

        # En modo normal, agregar la tarjeta de acceso a Zapping TV
        if not self.is_zapping:
            zap_icon = os.path.join(flags_dir, 'flag_DEP.png')
            if not os.path.exists(zap_icon):
                zap_icon = os.path.join(sports_dir, 'deportes_premium.png')
            li = xbmcgui.ListItem(label='📡 ZAPPING TV PRO')
            li.setArt({'thumb': zap_icon, 'icon': zap_icon, 'poster': zap_icon})
            li.setProperty('item_type', 'toggle_zapping')
            li.setProperty('subtitle', '[COLOR FFFFAA00]⚡ 2.400+ Canales · Deportes LATAM[/COLOR]')
            li.setProperty('total', 'PRO')
            items.append(li)

        # ── BLOQUE 1: Categorías Deportivas PRO ──────────────────────────────
        for cat in self.sports_cats:
            cat_id = cat.get('id', '')
            nombre = cat.get('nombre', cat_id)
            emoji = cat.get('emoji', '⚽')

            # Intentar cargar logo del torneo desde media/sports/
            sport_img = os.path.join(sports_dir, cat.get('icono', ''))
            if not os.path.exists(sport_img):
                # Fallback: usar badge_bg.png con color
                sport_img = os.path.join(self.addon_path, 'resources', 'skins', 'Default', 'media', 'badge_bg.png')

            li = xbmcgui.ListItem(label=f'{emoji} {nombre}')
            li.setArt({'thumb': sport_img, 'icon': sport_img, 'poster': sport_img})
            li.setProperty('item_type', 'sport_category')
            li.setProperty('sport_id', cat_id)
            li.setProperty('sport_name', nombre)
            li.setProperty('subtitle', SPORTS_BADGE)
            li.setProperty('total', 'PRO')
            items.append(li)

        # ── BLOQUE 2: Países normales ─────────────────────────────────────────
        for c in self.countries:
            code = c.get('codigo', '')
            name = c.get('nombre', code)
            total = c.get('total', 0)

            flag_file = os.path.join(flags_dir, f'flag_{code}.png')
            thumb = flag_file if os.path.exists(flag_file) else 'button_normal.png'

            li = xbmcgui.ListItem(label=name)
            li.setArt({'thumb': thumb, 'icon': thumb, 'poster': thumb})
            li.setProperty('item_type', 'country')
            li.setProperty('country_code', code)
            li.setProperty('country_name', name)
            li.setProperty('subtitle', f'{total} canales')
            li.setProperty('total', str(total))
            items.append(li)

        total_items = len(self.sports_cats) + len(self.countries)
        if self.is_zapping:
            total_canales = sum(c.get('total', 0) for c in self.countries)
            self.setProperty('total_count_label', f'{len(self.countries)} secciones · {total_canales} canales')
        else:
            self.setProperty('total_count_label',
                             f'{len(self.sports_cats)} deportes · {len(self.countries)} países')

        ctrl.addItems(items)
        self.setFocusId(8100)

        target_pos = select_pos if select_pos > 0 else self._last_country_pos
        if 0 <= target_pos < len(items):
            try:
                ctrl.selectItem(target_pos)
            except Exception:
                pass

        self._update_selected_info()

    def _show_sports_channels(self, sport_id, sport_name, select_pos=0):
        """Muestra los canales de una categoría deportiva PRO."""
        self.view_mode = 'sports_channels'
        self.current_sport_id = sport_id
        self.current_sport_name = sport_name

        self.setProperty('btn_back_label', '← Países' if self.is_zapping else '← Deportes + Países')
        self.setProperty('filter_country', f'⚽ {sport_name}')
        self.setProperty('filter_category', SPORTS_BADGE)

        ctrl = self.getControl(8100)
        ctrl.reset()

        canales = api.get_sports_channels(sport_id)

        if not canales:
            self.setProperty('selected_name', 'Sin canales disponibles')
            self.setProperty('selected_extra', 'Categoría vacía')
            self.setProperty('total_count_label', '0 canales')
            self.setFocusId(8005)
            return

        self.setProperty('total_count_label', f'{len(canales)} canales PRO')

        items = []
        for canal in canales:
            nombre = canal.get('nombre', 'Canal')
            stream_id = canal.get('stream_id', 0)
            logo = canal.get('logo', '')

            # Generar URLs del pool
            url_principal, alternativas = api.get_pool_stream_url(stream_id)

            if not logo:
                logo = os.path.join(self.addon_path, 'resources', 'skins', 'Default', 'media', 'badge_bg.png')

            li = xbmcgui.ListItem(label=nombre)
            li.setArt({'thumb': logo, 'icon': logo, 'poster': logo})
            li.setProperty('item_type', 'sport_channel')
            li.setProperty('stream_id', str(stream_id))
            li.setProperty('stream_url', url_principal or '')
            li.setProperty('alternativas', json.dumps(alternativas))
            li.setProperty('channel_name', nombre)
            li.setProperty('subtitle', f'[COLOR FFFFAA00]{sport_name}[/COLOR]')
            items.append(li)

        ctrl.addItems(items)
        self.setFocusId(8100)

        if 0 <= select_pos < len(items):
            try:
                ctrl.selectItem(select_pos)
            except Exception:
                pass

        self._update_selected_info()

    def _show_channels(self, country_code, category='Todas', select_pos=0):
        """Carga y muestra la cuadrícula de canales del país indicado."""
        self.view_mode = 'channels'
        self.current_country = country_code

        c_name = country_code
        for c in self.countries:
            if c.get('codigo') == country_code:
                c_name = c.get('nombre', country_code)
                break
        self.current_country_name = c_name

        self.setProperty('btn_back_label', '← Países' if self.is_zapping else '← Deportes + Países')
        self.setProperty('filter_country', c_name if country_code == 'DEP' else f'País: {c_name}')

        ctrl = self.getControl(8100)
        ctrl.reset()

        data = api.get_zapping_channels(country_code) if self.is_zapping else api.get_tv_channels(country_code)
        self.raw_channels = data.get('canales', [])
        cats = data.get('categorias', [])

        self.categories = ['Todas'] + cats
        cat_display = ' | '.join(self.categories[:5])
        self.setProperty('filter_category', category)

        if category and category != 'Todas':
            self.current_category = category
            filtered = [ch for ch in self.raw_channels
                        if ch.get('categoria', '') == category]
        else:
            self.current_category = 'Todas'
            filtered = self.raw_channels

        self.channels = filtered
        self.setProperty('total_count_label', f'{len(filtered)} canales')

        if not filtered:
            self.setProperty('selected_name', 'Sin canales disponibles')
            self.setProperty('selected_extra', 'Verifica tu conexión')
            self.setFocusId(8005)
            return

        items = []
        for ch in filtered:
            nombre = ch.get('nombre', 'Canal')
            logo = ch.get('logo', '')
            url = ch.get('url', '')
            alts = ch.get('alternativas', [])
            cat = ch.get('categoria', '')

            if not logo:
                logo = os.path.join(self.addon_path, 'resources', 'skins', 'Default', 'media', 'badge_bg.png')

            li = xbmcgui.ListItem(label=nombre)
            li.setArt({'thumb': logo, 'icon': logo, 'poster': logo})
            li.setProperty('item_type', 'channel')
            li.setProperty('stream_url', url)
            li.setProperty('alternativas', json.dumps(alts))
            li.setProperty('channel_name', nombre)
            sub = ch.get('subtitulo') or cat
            li.setProperty('subtitle', sub)
            items.append(li)

        ctrl.addItems(items)
        self.setFocusId(8100)

        if 0 <= select_pos < len(items):
            try:
                ctrl.selectItem(select_pos)
            except Exception:
                pass

        self._update_selected_info()

    # ------------------------------------------------------------------ Info Panel
    def _update_selected_info(self):
        """Actualiza el panel de info con el ítem seleccionado actualmente."""
        try:
            ctrl = self.getControl(8100)
            item = ctrl.getSelectedItem()
            if not item:
                return
            self.setProperty('selected_name', item.getLabel())
            self.setProperty('selected_extra', item.getProperty('subtitle') or '')
        except Exception:
            pass

    # ------------------------------------------------------------------ Eventos
    def onAction(self, action):
        action_id = action.getId()
        # Back / Escape
        if action_id in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_STOP):
            if self.view_mode in ('channels', 'sports_channels'):
                self._show_countries(select_pos=self._last_country_pos)
            elif self.is_zapping:
                self._toggle_mode()
            else:
                self.close()
        # Actualizar info al navegar
        elif action_id in (xbmcgui.ACTION_MOVE_UP, xbmcgui.ACTION_MOVE_DOWN,
                           xbmcgui.ACTION_MOVE_LEFT, xbmcgui.ACTION_MOVE_RIGHT):
            self._update_selected_info()

    def onClick(self, control_id):
        if control_id == 8003:  # Toggle Modo TV / Zapping
            self._toggle_mode()
            return

        if control_id == 8100:
            ctrl = self.getControl(8100)
            item = ctrl.getSelectedItem()
            if not item:
                return

            item_type = item.getProperty('item_type')

            if item_type == 'toggle_zapping':
                self._toggle_mode()
                return

            if self.view_mode == 'countries':
                self._last_country_pos = ctrl.getSelectedPosition()
                if item_type == 'sport_category':
                    sport_id = item.getProperty('sport_id')
                    sport_name = item.getProperty('sport_name')
                    self._show_sports_channels(sport_id, sport_name)
                else:
                    code = item.getProperty('country_code')
                    self._show_channels(code, category='Todas')

            elif self.view_mode == 'sports_channels':
                pos = ctrl.getSelectedPosition()
                self._on_sport_channel_selected(item, pos)

            else:  # channels (países)
                pos = ctrl.getSelectedPosition()
                self._on_channel_selected(item, pos)

        elif control_id == 8005:  # Botón Volver
            if self.view_mode in ('channels', 'sports_channels'):
                self._show_countries(select_pos=self._last_country_pos)
            elif self.is_zapping:
                self._toggle_mode()
            else:
                self.close()

        elif control_id == 8001:  # Selector de País
            self._select_country_dialog()

        elif control_id == 8002:  # Selector de Categoría
            if self.view_mode == 'channels':
                self._select_category_dialog()
            else:
                xbmcgui.Dialog().notification('LATARR PRO', 'Selecciona primero un país', xbmcgui.NOTIFICATION_INFO, 2000)

    # ------------------------------------------------------------------ Diálogos Filtros
    def _select_country_dialog(self):
        if not self.countries:
            return
        country_names = [f"{c.get('nombre', '')} ({c.get('total', 0)} canales)" for c in self.countries]
        idx = xbmcgui.Dialog().select('Seleccionar País', country_names)
        if idx >= 0:
            self._last_country_pos = idx + len(self.sports_cats)  # offset por deportes
            code = self.countries[idx].get('codigo')
            self._show_channels(code, category='Todas')

    def _select_category_dialog(self):
        if not self.categories:
            return
        idx = xbmcgui.Dialog().select('Filtrar Categoría', self.categories)
        if idx >= 0:
            cat = self.categories[idx]
            self._show_channels(self.current_country, category=cat)

    # ------------------------------------------------------------------ Reproducción
    def _on_sport_channel_selected(self, item, pos):
        """Reproduce un canal deportivo PRO con pool de cuentas."""
        url = item.getProperty('stream_url')
        if not url:
            xbmcgui.Dialog().notification('LATARR PRO', 'Enlace no disponible', xbmcgui.NOTIFICATION_WARNING, 2000)
            return

        alts_raw = item.getProperty('alternativas')
        alternativas = []
        if alts_raw:
            try:
                alternativas = json.loads(alts_raw)
            except Exception:
                alternativas = []

        nombre = item.getProperty('channel_name') or item.getLabel()
        logo = item.getArt('thumb') or ''

        self._play_stream(url, alternativas, nombre, logo, pos, is_sport=True)

    def _on_channel_selected(self, item, pos):
        """Reproduce un canal de país con URLs directas."""
        url = item.getProperty('stream_url')
        if not url:
            xbmcgui.Dialog().notification('LATARR PRO', 'Enlace no disponible', xbmcgui.NOTIFICATION_WARNING, 2000)
            return

        alts_raw = item.getProperty('alternativas')
        alternativas = []
        if alts_raw:
            try:
                alternativas = json.loads(alts_raw)
            except Exception:
                alternativas = []

        nombre = item.getProperty('channel_name') or item.getLabel()
        logo = item.getArt('thumb') or ''

        self._play_stream(url, alternativas, nombre, logo, pos, is_sport=False)

    def _play_stream(self, url, alternativas, nombre, logo, pos, is_sport=False):
        """Reproduce el stream con fallback automático a alternativas."""
        li = xbmcgui.ListItem(label=nombre)
        li.setArt({'thumb': logo, 'icon': logo, 'poster': logo})
        li.setInfo('video', {
            'title': nombre,
            'mediatype': 'video',
        })
        li.setProperty('IsPlayable', 'true')

        player = xbmc.Player()
        player.play(url, li)

        monitor = xbmc.Monitor()
        started = False
        for _ in range(14):  # ~4.2 segundos
            if monitor.abortRequested():
                return
            if player.isPlayingVideo() or player.isPlaying():
                started = True
                break
            monitor.waitForAbort(0.3)

        if not started and alternativas:
            for alt_url in alternativas:
                if monitor.abortRequested():
                    return
                xbmc.log(f"[LATARR-PRO] Señal principal caída ({url}), probando: {alt_url}", xbmc.LOGWARNING)
                xbmcgui.Dialog().notification('LATARR PRO', f'Probando señal alternativa de {nombre}...', xbmcgui.NOTIFICATION_INFO, 2000)
                player.play(alt_url, li)
                for _ in range(12):
                    if monitor.abortRequested():
                        return
                    if player.isPlayingVideo() or player.isPlaying():
                        started = True
                        break
                    monitor.waitForAbort(0.3)
                if started:
                    break

        if started:
            self.played = True
            if is_sport:
                self.resume_data = {
                    'section': 'tv',
                    'sport_id': self.current_sport_id,
                    'sport_name': self.current_sport_name,
                    'pos': pos,
                }
            else:
                self.resume_data = {
                    'section': 'zapping' if self.is_zapping else 'tv',
                    'country': self.current_country,
                    'category': self.current_category,
                    'pos': pos,
                }
            self.close()
        else:
            if is_sport:
                # Rotar cuenta del pool para el próximo intento
                api.rotate_pool_account()
            xbmcgui.Dialog().notification('LATARR PRO', f'No se pudo conectar a {nombre}', xbmcgui.NOTIFICATION_WARNING, 3000)
