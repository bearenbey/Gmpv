import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk


class GmpvApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.github.bearenbey.Gmpv",
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            from gmpv.window import GmpvWindow

            win = GmpvWindow(application=self)
        win.present()

    def do_open(self, files, n_files, hint):
        self.do_activate()
        win = self.props.active_window
        if files:
            win.open_file(files[0].get_path())

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._setup_actions()

    def _setup_actions(self):
        open_action = Gio.SimpleAction.new("open", None)
        open_action.connect("activate", self._on_open)
        self.add_action(open_action)
        self.set_accels_for_action("app.open", ["<Control>o"])

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit)
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["q"])

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

    def _on_open(self, action, param):
        win = self.props.active_window
        if win:
            win.show_open_dialog()

    def _on_quit(self, action, param):
        self.quit()

    def _on_about(self, action, param):
        about = Adw.AboutDialog(
            application_name="Gmpv",
            application_icon="com.github.bearenbey.Gmpv",
            comments="A minimal, clean video player for the GNOME desktop powered by mpv.",
            version="0.1.0",
            developer_name="Eren Öğrül",
            website="https://unruled.one",
            copyright="Copyright © 2026 Eren Öğrül",
            license_type=Gtk.License.GPL_2_0_ONLY,
        )
        about.present(self.props.active_window)


def main():
    app = GmpvApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
