import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, GObject, Gtk


def _format_time(seconds):
    if seconds is None or seconds < 0:
        return "0:00"
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


_CONTROLS_CSS = """
.gmpv-controls {
    background: alpha(black, 0.7);
    border-radius: 12px;
    padding: 4px 8px;
}
.gmpv-controls label {
    font-size: 11px;
    font-variant-numeric: tabular-nums;
    color: alpha(white, 0.85);
}
.gmpv-controls button {
    min-height: 28px;
    min-width: 28px;
    padding: 0;
    color: white;
}
.gmpv-controls scale trough {
    min-height: 4px;
    border-radius: 2px;
    background: alpha(white, 0.2);
}
.gmpv-controls scale trough highlight {
    background: white;
    border-radius: 2px;
}
.gmpv-controls scale slider {
    min-width: 12px;
    min-height: 12px;
    background: white;
    border-radius: 50%;
    margin: -4px;
}
"""


class ControlsBar(Gtk.Box):
    __gtype_name__ = "ControlsBar"

    def __init__(self, player):
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.END,
            margin_start=24,
            margin_end=24,
            margin_bottom=16,
            spacing=6,
        )
        self._player = player
        self._seeking = False
        self._load_css()
        self._setup_ui()
        self._connect_signals()

    def _load_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_string(_CONTROLS_CSS)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display() if self.get_display() else __import__("gi").repository.Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _setup_ui(self):
        self.add_css_class("gmpv-controls")

        # Play/pause
        self._play_button = Gtk.Button(icon_name="media-playback-start-symbolic")
        self._play_button.add_css_class("flat")
        self._play_button.add_css_class("circular")
        self.append(self._play_button)

        # Position label
        self._position_label = Gtk.Label(label="0:00")
        self.append(self._position_label)

        # Seek bar
        self._seek_scale = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL,
            hexpand=True,
            draw_value=False,
        )
        self._seek_scale.set_range(0, 100)
        self.append(self._seek_scale)

        # Duration label
        self._duration_label = Gtk.Label(label="0:00")
        self.append(self._duration_label)

        # Volume
        self._volume_button = Gtk.VolumeButton()
        self._volume_button.set_value(1.0)
        self._volume_button.add_css_class("flat")
        self.append(self._volume_button)

        # Subtitle track
        self._sub_button = Gtk.MenuButton(icon_name="media-view-subtitles-symbolic")
        self._sub_button.add_css_class("flat")
        self._sub_button.add_css_class("circular")
        self._sub_menu = Gio.Menu()
        self._sub_button.set_menu_model(self._sub_menu)
        self.append(self._sub_button)

        # Audio track
        self._audio_button = Gtk.MenuButton(icon_name="audio-speakers-symbolic")
        self._audio_button.add_css_class("flat")
        self._audio_button.add_css_class("circular")
        self._audio_menu = Gio.Menu()
        self._audio_button.set_menu_model(self._audio_menu)
        self.append(self._audio_button)

        # Fullscreen
        self._fullscreen_button = Gtk.Button(icon_name="view-fullscreen-symbolic")
        self._fullscreen_button.add_css_class("flat")
        self._fullscreen_button.add_css_class("circular")
        self.append(self._fullscreen_button)

    def _connect_signals(self):
        self._play_button.connect("clicked", self._on_play_pause)
        self._fullscreen_button.connect("clicked", self._on_fullscreen)
        self._volume_button.connect("value-changed", self._on_volume_changed)
        self._seek_scale.connect("change-value", self._on_seek_change)

        self._player.connect("position-changed", self._on_position_changed)
        self._player.connect("duration-changed", self._on_duration_changed)
        self._player.connect("pause-changed", self._on_pause_changed)
        self._player.connect("volume-changed", self._on_player_volume_changed)
        self._player.connect("track-list-changed", self._on_track_list_changed)

    def _on_play_pause(self, button):
        self._player.play_pause()

    def _on_fullscreen(self, button):
        win = self.get_root()
        if win:
            win.toggle_fullscreen()

    def _on_volume_changed(self, button, value):
        self._player.set_volume(value * 100)

    def _on_seek_change(self, scale, scroll_type, value):
        self._player.seek_absolute(value)
        return False

    def _on_position_changed(self, player, position):
        if not self._seeking:
            self._seek_scale.set_value(position)
        self._position_label.set_label(_format_time(position))

    def _on_duration_changed(self, player, duration):
        self._seek_scale.set_range(0, max(duration, 1))
        self._duration_label.set_label(_format_time(duration))

    def _on_pause_changed(self, player, paused):
        icon = "media-playback-start-symbolic" if paused else "media-playback-pause-symbolic"
        self._play_button.set_icon_name(icon)

    def _on_player_volume_changed(self, player, volume):
        self._volume_button.set_value(volume / 100.0)

    def _on_track_list_changed(self, player):
        self._update_track_menu("sub", self._sub_menu)
        self._update_track_menu("audio", self._audio_menu)

    def _update_track_menu(self, track_type, menu):
        menu.remove_all()
        tracks = self._player.get_tracks_by_type(track_type)
        prop = "sid" if track_type == "sub" else "aid"

        if track_type == "sub":
            menu.append("None", f"win.set-track-{prop}::no")

        for track in tracks:
            tid = track.get("id", 0)
            title = track.get("title") or track.get("lang") or f"Track {tid}"
            menu.append(title, f"win.set-track-{prop}::{tid}")
