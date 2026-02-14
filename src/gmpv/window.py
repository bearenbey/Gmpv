import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, GLib, Gio, Gtk

try:
    gi.require_version("GdkX11", "4.0")
    from gi.repository import GdkX11

    HAS_GDKX11 = True
except (ValueError, ImportError):
    GdkX11 = None
    HAS_GDKX11 = False

from gmpv.player import Player, _get_display_backend
from gmpv.controls import ControlsBar

_WINDOW_CSS = """
.gmpv-window {
    background: black;
}
.gmpv-headerbar {
    background: transparent;
    box-shadow: none;
    border: none;
    color: alpha(white, 0.9);
}
"""


class GmpvWindow(Adw.ApplicationWindow):
    __gtype_name__ = "GmpvWindow"

    def __init__(self, **kwargs):
        super().__init__(
            default_width=960,
            default_height=540,
            title="Gmpv",
            **kwargs,
        )
        self._player = Player()
        self._fullscreened = False
        self._cursor_hide_id = None
        self._controls_visible = False
        self._has_file = False
        self._load_css()
        self._setup_ui()
        self._setup_keyboard()
        self._setup_drag_drop()
        self._setup_track_actions()

    def _load_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_string(_WINDOW_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _setup_ui(self):
        self.add_css_class("gmpv-window")

        # Main vertical box: headerbar + video
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Minimal transparent headerbar with just window controls
        self._headerbar = Adw.HeaderBar()
        self._headerbar.add_css_class("gmpv-headerbar")
        self._headerbar.add_css_class("flat")
        self._headerbar.set_show_title(False)
        main_box.append(self._headerbar)

        # Video area
        backend = _get_display_backend()
        if backend == "wayland":
            self._video_widget = Gtk.GLArea()
            self._video_widget.set_auto_render(False)
            self._video_widget.connect("realize", self._on_gl_realize)
            self._video_widget.connect("render", self._on_gl_render)
        else:
            self._video_widget = Gtk.DrawingArea()
            self._video_widget.connect("realize", self._on_x11_realize)

        self._video_widget.set_hexpand(True)
        self._video_widget.set_vexpand(True)

        # Overlay for video + controls
        self._overlay = Gtk.Overlay()
        self._overlay.set_child(self._video_widget)
        self._overlay.set_vexpand(True)
        main_box.append(self._overlay)

        # Controls overlay (hidden initially)
        self._controls = ControlsBar(self._player)
        self._controls.set_visible(False)
        self._overlay.add_overlay(self._controls)

        # Toast overlay wraps everything
        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(main_box)

        # Set content once
        self.set_content(self._toast_overlay)

        # Player signals
        self._player.connect("file-loaded", self._on_file_loaded)

        # Mouse motion for auto-hide controls
        motion_ctrl = Gtk.EventControllerMotion()
        motion_ctrl.connect("motion", self._on_mouse_motion)
        self._overlay.add_controller(motion_ctrl)

        # Double-click to toggle fullscreen
        gesture = Gtk.GestureClick(button=1)
        gesture.connect("released", self._on_click_released)
        self._video_widget.add_controller(gesture)

        # Right-click context menu
        right_click = Gtk.GestureClick(button=3)
        right_click.connect("released", self._on_right_click)
        self.add_controller(right_click)

        self._context_menu = Gtk.PopoverMenu()
        self._context_menu.set_parent(self._video_widget)
        self._context_menu.set_has_arrow(False)
        menu = Gio.Menu()
        menu.append("Open File", "app.open")
        menu.append("About Gmpv", "app.about")
        menu.append("Quit", "app.quit")
        self._context_menu.set_menu_model(menu)

    def _on_right_click(self, gesture, n_press, x, y):
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        self._context_menu.set_pointing_to(rect)
        self._context_menu.popup()

    def _on_x11_realize(self, widget):
        GLib.idle_add(self._init_x11_player, widget)

    def _init_x11_player(self, widget):
        if not HAS_GDKX11:
            return False
        surface = widget.get_native().get_surface()
        if isinstance(surface, GdkX11.X11Surface):
            xid = surface.get_xid()
            self._player.setup_x11(xid)
        return False

    def _on_gl_realize(self, gl_area):
        gl_area.make_current()
        self._player.setup_wayland(gl_area)

    def _on_gl_render(self, gl_area, gl_context):
        import ctypes
        fbo_buf = ctypes.c_int(0)
        ctypes.cdll.LoadLibrary("libGL.so.1")
        GL = ctypes.CDLL("libGL.so.1")
        GL.glGetIntegerv(0x8CA6, ctypes.byref(fbo_buf))  # GL_FRAMEBUFFER_BINDING
        allocation = gl_area.get_allocation()
        self._player.render_gl(fbo_buf.value, allocation.width, allocation.height)
        return True

    def _setup_keyboard(self):
        ctrl = Gtk.EventControllerKey()
        ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(ctrl)

    def _on_key_pressed(self, ctrl, keyval, keycode, state):
        match keyval:
            case Gdk.KEY_space:
                self._player.play_pause()
                return True
            case Gdk.KEY_Left:
                self._player.seek(-5)
                return True
            case Gdk.KEY_Right:
                self._player.seek(5)
                return True
            case Gdk.KEY_Up:
                self._player.set_volume(min(self._player.volume + 5, 150))
                return True
            case Gdk.KEY_Down:
                self._player.set_volume(max(self._player.volume - 5, 0))
                return True
            case Gdk.KEY_f | Gdk.KEY_F:
                self.toggle_fullscreen()
                return True
            case Gdk.KEY_m | Gdk.KEY_M:
                self._player.toggle_mute()
                return True
            case Gdk.KEY_Escape:
                if self._fullscreened:
                    self.toggle_fullscreen()
                return True
        return False

    def _setup_drag_drop(self):
        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        self.add_controller(drop_target)

    def _on_drop(self, target, value, x, y):
        if isinstance(value, Gio.File):
            self.open_file(value.get_path())
            return True
        return False

    def _setup_track_actions(self):
        for prop in ("sid", "aid"):
            action = Gio.SimpleAction.new(f"set-track-{prop}", GLib.VariantType.new("s"))
            action.connect("activate", self._on_set_track, prop)
            self.add_action(action)

    def _on_set_track(self, action, param, prop):
        value = param.get_string()
        if value == "no":
            self._player.set_track(prop, "no")
        else:
            self._player.set_track(prop, int(value))

    def toggle_fullscreen(self):
        if self._fullscreened:
            self.unfullscreen()
            self._headerbar.set_visible(True)
            self._fullscreened = False
        else:
            self.fullscreen()
            self._headerbar.set_visible(False)
            self._fullscreened = True
        self._show_controls()

    def _on_file_loaded(self, player):
        self._has_file = True
        self._show_controls()

    def _on_click_released(self, gesture, n_press, x, y):
        if n_press == 2:
            self.toggle_fullscreen()
        elif n_press == 1 and not self._has_file:
            self.show_open_dialog()

    def _on_mouse_motion(self, ctrl, x, y):
        self._show_controls()

    def _show_controls(self):
        if self._has_file:
            self._controls.set_visible(True)
            self._controls_visible = True
            self._schedule_hide_controls()

    def _schedule_hide_controls(self):
        if self._cursor_hide_id:
            GLib.source_remove(self._cursor_hide_id)
        self._cursor_hide_id = GLib.timeout_add(2000, self._hide_controls)

    def _hide_controls(self):
        self._controls.set_visible(False)
        self._controls_visible = False
        self._cursor_hide_id = None
        return False

    def show_open_dialog(self):
        dialog = Gtk.FileDialog()
        video_filter = Gtk.FileFilter()
        video_filter.set_name("Video Files")
        for mime in (
            "video/mp4", "video/x-matroska", "video/webm", "video/avi",
            "video/x-msvideo", "video/quicktime", "video/x-flv",
            "video/ogg", "video/mpeg",
        ):
            video_filter.add_mime_type(mime)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(video_filter)
        all_filter = Gtk.FileFilter()
        all_filter.set_name("All Files")
        all_filter.add_pattern("*")
        filters.append(all_filter)
        dialog.set_filters(filters)
        dialog.open(self, None, self._on_file_dialog_response)

    def _on_file_dialog_response(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                self.open_file(file.get_path())
        except GLib.Error:
            pass

    def open_file(self, path):
        if path:
            self._player.loadfile(path)
            filename = path.split("/")[-1]
            self.set_title(filename + " — Gmpv")
            toast = Adw.Toast(title=filename, timeout=2)
            self._toast_overlay.add_toast(toast)

    def do_close_request(self):
        self._player.shutdown()
        return False
