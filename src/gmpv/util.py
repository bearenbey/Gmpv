import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk


def get_display_backend():
    """Return 'x11', 'wayland', or 'unknown' for the default display."""
    display_type = type(Gdk.Display.get_default()).__name__
    if "X11" in display_type:
        return "x11"
    if "Wayland" in display_type:
        return "wayland"
    return "unknown"


def add_css_to_display(css):
    """Install a CSS string globally on the default display."""
    provider = Gtk.CssProvider()
    provider.load_from_string(css)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
