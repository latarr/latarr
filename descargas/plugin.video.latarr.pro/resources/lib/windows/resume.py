import xbmcgui

class LatarrResumeDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.item_data = kwargs.pop('item_data', {})
        super().__init__(*args, **kwargs)
        self.action_selected = None

    def onInit(self):
        title = self.item_data.get('display_title') or self.item_data.get('title') or 'Sin Título'
        poster = self.item_data.get('poster') or ''
        plot = self.item_data.get('plot') or 'Sin sinopsis disponible.'
        percent = int(self.item_data.get('percent') or 0)
        curr_time = self.item_data.get('current_time') or 0
        tot_time = self.item_data.get('total_time') or 0

        # Formatear tiempos legibles
        curr_str = self._format_seconds(curr_time)
        tot_str = self._format_seconds(tot_time)
        rem_sec = max(0, tot_time - curr_time)
        rem_str = self._format_seconds(rem_sec)

        subtitle = f"Te quedaste en el minuto {curr_str}  •  Restan {rem_str}"
        progress_badge = f"{curr_str} / {tot_str} ({percent}%)"

        self.setProperty('item_title', title)
        self.setProperty('item_subtitle', subtitle)
        self.setProperty('item_plot', plot)
        self.setProperty('item_poster', poster)
        self.setProperty('item_percent', str(percent))
        self.setProperty('resume_time', curr_str)
        self.setProperty('item_progress_badge', progress_badge)

        self.setFocusId(9001)

    def onClick(self, control_id):
        if control_id == 9001:
            self.action_selected = 'resume'
            self.close()
        elif control_id == 9002:
            self.action_selected = 'restart'
            self.close()
        elif control_id == 9003:
            self.action_selected = 'delete'
            self.close()

    def onAction(self, action):
        if action.getId() in (xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK):
            self.action_selected = None
            self.close()

    def _format_seconds(self, seconds):
        try:
            seconds = int(float(seconds))
        except (ValueError, TypeError):
            return "00:00"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
