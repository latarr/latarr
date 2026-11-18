"""
keymap.py - Configuración automática de control remoto estilo Netflix para LATARR.

Garantiza que al presionar el botón 'Atrás' en el control remoto o en el teclado
(Backspace / Esc) durante la reproducción de un video o canal de TV, se detenga
inmediatamente (Stop) en lugar de quedar reproduciéndose en segundo plano.
"""

import os
import xbmc
import xbmcvfs

KEYMAP_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<keymap>
    <FullScreenVideo>
        <keyboard>
            <backspace>Stop</backspace>
            <escape>Stop</escape>
            <browser_back>Stop</browser_back>
        </keyboard>
        <remote>
            <back>Stop</back>
            <exit>Stop</exit>
        </remote>
    </FullScreenVideo>
    <FullScreenLiveTV>
        <keyboard>
            <backspace>Stop</backspace>
            <escape>Stop</escape>
            <browser_back>Stop</browser_back>
        </keyboard>
        <remote>
            <back>Stop</back>
            <exit>Stop</exit>
        </remote>
    </FullScreenLiveTV>
    <VideoOSD>
        <keyboard>
            <backspace>Stop</backspace>
            <escape>Stop</escape>
            <browser_back>Stop</browser_back>
        </keyboard>
        <remote>
            <back>Stop</back>
            <exit>Stop</exit>
        </remote>
    </VideoOSD>
    <Visualisation>
        <keyboard>
            <backspace>Stop</backspace>
            <escape>Stop</escape>
            <browser_back>Stop</browser_back>
        </keyboard>
        <remote>
            <back>Stop</back>
            <exit>Stop</exit>
        </remote>
    </Visualisation>
</keymap>
"""


def ensure_netflix_keymap():
    """Verifica e instala el keymap de salida rápida en Kodi."""
    try:
        keymaps_dir = xbmcvfs.translatePath("special://userdata/keymaps/")
        if not xbmcvfs.exists(keymaps_dir):
            xbmcvfs.mkdirs(keymaps_dir)

        target_path = os.path.join(keymaps_dir, "latarr_netflix_back.xml")
        needs_write = True

        if xbmcvfs.exists(target_path):
            try:
                f = xbmcvfs.File(target_path, 'r')
                content = f.read()
                f.close()
                if content.strip() == KEYMAP_CONTENT.strip():
                    needs_write = False
            except Exception:
                needs_write = True

        if needs_write:
            f = xbmcvfs.File(target_path, 'w')
            f.write(KEYMAP_CONTENT)
            f.close()
            xbmc.log("[LATARR-PRO] Keymap Netflix Back instalado correctamente", xbmc.LOGINFO)
            xbmc.executebuiltin("Action(reloadkeymaps)")
    except Exception as e:
        xbmc.log(f"[LATARR-PRO] Error configurando keymap: {e}", xbmc.LOGWARNING)
