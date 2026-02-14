import mpv

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import GLib, GObject, Gdk, Gtk


def _get_display_backend():
    display = Gdk.Display.get_default()
    display_type = type(display).__name__
    if "X11" in display_type:
        return "x11"
    elif "Wayland" in display_type:
        return "wayland"
    return "unknown"


class Player(GObject.Object):
    __gsignals__ = {
        "position-changed": (GObject.SignalFlags.RUN_LAST, None, (float,)),
        "duration-changed": (GObject.SignalFlags.RUN_LAST, None, (float,)),
        "pause-changed": (GObject.SignalFlags.RUN_LAST, None, (bool,)),
        "volume-changed": (GObject.SignalFlags.RUN_LAST, None, (float,)),
        "track-list-changed": (GObject.SignalFlags.RUN_LAST, None, ()),
        "file-loaded": (GObject.SignalFlags.RUN_LAST, None, ()),
        "end-file": (GObject.SignalFlags.RUN_LAST, None, (str,)),
        "eof": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self._mpv = None
        self._render_ctx = None
        self._backend = _get_display_backend()
        self.duration = 0.0
        self.position = 0.0
        self.paused = True
        self.volume = 100.0
        self.tracks = []

    @property
    def backend(self):
        return self._backend

    def setup_x11(self, wid):
        self._mpv = mpv.MPV(
            wid=str(wid),
            input_default_bindings=False,
            input_vo_keyboard=False,
            osc=False,
            osd_level=0,
            keep_open="yes",
        )
        self._observe_properties()

    def setup_wayland(self, gl_area):
        import ctypes

        self._mpv = mpv.MPV(
            input_default_bindings=False,
            input_vo_keyboard=False,
            osc=False,
            osd_level=0,
            keep_open="yes",
            vo="libmpv",
        )
        self._gl_area = gl_area

        # Build a ctypes callback for get_proc_address — mpv needs a C function pointer
        _libEGL = ctypes.CDLL("libEGL.so.1")
        _egl_get_proc = _libEGL.eglGetProcAddress
        _egl_get_proc.restype = ctypes.c_void_p
        _egl_get_proc.argtypes = [ctypes.c_char_p]

        _GL_GET_PROC_CB = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)

        @_GL_GET_PROC_CB
        def _get_proc_address(_ctx, name):
            return _egl_get_proc(name)

        # Store reference so the callback isn't garbage collected
        self._get_proc_address_cb = _get_proc_address

        self._render_ctx = mpv.MpvRenderContext(
            self._mpv, "opengl",
            opengl_init_params={
                "get_proc_address": self._get_proc_address_cb,
            },
        )
        self._render_ctx.update_cb = self._on_mpv_render_update
        self._observe_properties()

    def _on_mpv_render_update(self):
        if hasattr(self, "_gl_area"):
            GLib.idle_add(self._gl_area.queue_render)

    def render_gl(self, fbo, width, height):
        if self._render_ctx:
            self._render_ctx.render(
                flip_y=True,
                opengl_fbo={"fbo": fbo, "w": width, "h": height},
            )

    def _observe_properties(self):
        self._mpv.observe_property("time-pos", self._on_time_pos)
        self._mpv.observe_property("duration", self._on_duration)
        self._mpv.observe_property("pause", self._on_pause)
        self._mpv.observe_property("volume", self._on_volume)
        self._mpv.observe_property("track-list", self._on_track_list)

        @self._mpv.event_callback("file-loaded")
        def on_file_loaded(event):
            GLib.idle_add(self.emit, "file-loaded")

        @self._mpv.event_callback("end-file")
        def on_end_file(event):
            reason = event.get("reason", "unknown") if isinstance(event, dict) else "unknown"
            GLib.idle_add(self.emit, "end-file", str(reason))

    def _on_time_pos(self, name, value):
        if value is not None:
            self.position = value
            GLib.idle_add(self.emit, "position-changed", value)

    def _on_duration(self, name, value):
        if value is not None:
            self.duration = value
            GLib.idle_add(self.emit, "duration-changed", value)

    def _on_pause(self, name, value):
        if value is not None:
            self.paused = value
            GLib.idle_add(self.emit, "pause-changed", value)

    def _on_volume(self, name, value):
        if value is not None:
            self.volume = value
            GLib.idle_add(self.emit, "volume-changed", value)

    def _on_track_list(self, name, value):
        if value is not None:
            self.tracks = value
            GLib.idle_add(self.emit, "track-list-changed")

    def loadfile(self, path):
        if self._mpv:
            self._mpv.loadfile(path)

    def play_pause(self):
        if self._mpv:
            self._mpv.cycle("pause")

    def seek(self, seconds, reference="relative"):
        if self._mpv:
            self._mpv.seek(seconds, reference)

    def seek_absolute(self, position):
        if self._mpv:
            self._mpv.seek(position, "absolute")

    def set_volume(self, volume):
        if self._mpv:
            self._mpv.volume = volume

    def toggle_mute(self):
        if self._mpv:
            self._mpv.cycle("mute")

    def set_track(self, track_type, track_id):
        """Set audio/subtitle track. track_type is 'aid' or 'sid'."""
        if self._mpv:
            setattr(self._mpv, track_type, track_id)

    def get_tracks_by_type(self, track_type):
        """Return tracks filtered by type ('audio', 'video', 'sub')."""
        return [t for t in self.tracks if t.get("type") == track_type]

    def shutdown(self):
        if hasattr(self, "_render_ctx") and self._render_ctx:
            self._render_ctx.free()
            self._render_ctx = None
        if self._mpv:
            self._mpv.terminate()
            self._mpv = None
