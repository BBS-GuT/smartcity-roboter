#!/usr/bin/env python3
# Eigenes Fenster fuer das Panel - ohne Browser (nutzt WebKit, die Technik von GNOME Web).
# Braucht:  sudo apt install python3-gi gir1.2-webkit2-4.1   (scripts/browser_installieren.sh)
# Aufruf:   python3 panel/fenster.py [URL] [--fenster]   (--fenster = nicht Vollbild)
# Tasten:   F11 = Vollbild an/aus, F5 = neu laden, Strg+Q = schliessen
import sys

import gi

for version in ('4.1', '4.0'):
    try:
        gi.require_version('WebKit2', version)
        break
    except ValueError:
        continue
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, WebKit2  # noqa: E402


def main():
    url = next((a for a in sys.argv[1:] if not a.startswith('--')), 'http://localhost:8080')
    win = Gtk.Window(title='SmartCity Panel')
    win.set_default_size(1024, 600)
    view = WebKit2.WebView()
    view.load_uri(url)
    win.add(view)
    voll = [False]

    def taste(_w, ev):
        name = Gdk.keyval_name(ev.keyval)
        if name == 'F11':
            (win.unfullscreen if voll[0] else win.fullscreen)()
            voll[0] = not voll[0]
        elif name == 'F5':
            view.reload()
        elif name in ('q', 'Q') and ev.state & Gdk.ModifierType.CONTROL_MASK:
            win.destroy()
    win.connect('key-press-event', taste)
    win.connect('destroy', Gtk.main_quit)
    win.show_all()
    if '--fenster' not in sys.argv:
        win.fullscreen()
        voll[0] = True
    Gtk.main()


if __name__ == '__main__':
    main()
