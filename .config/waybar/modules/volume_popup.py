#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango
import json, os, subprocess, argparse

WM_CLASS = 'waybar-volume'
BAR_H    = 36
PAD      = 8

GLib.set_prgname(WM_CLASS)

def get_wal_colors():
    path = os.path.expanduser('~/.cache/wal/colors.json')
    defaults = {
        'background': '#000000', 'foreground': '#ffffff', 'accent': '#d6002f',
        'dim': '#2a2a2a'
    }
    try:
        with open(path) as f:
            data = json.load(f)
        return {
            'background': data['special'].get('background', defaults['background']),
            'foreground': data['special'].get('foreground', defaults['foreground']),
            'accent':     data['colors'].get('color4', defaults['accent']),
            'dim':        data['colors'].get('color0', defaults['dim']),
        }
    except: return defaults

def get_monitor_geometry():
    try:
        out = subprocess.check_output(['hyprctl', 'cursorpos'], text=True).strip()
        cx, cy = map(int, out.split(','))
        raw = subprocess.run(['hyprctl', 'monitors', '-j'], capture_output=True, text=True)
        monitors = json.loads(raw.stdout)
        for m in monitors:
            if m['x'] <= cx <= m['x'] + m['width'] and m['y'] <= cy <= m['y'] + m['height']:
                return m['x'], m['y'], m['width'], m['height'], cx, cy
    except: pass
    return 0, 0, 1920, 1080, 0, 0

class VolumePopup(Gtk.Window):
    def __init__(self, cx, cy):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.c = get_wal_colors()
        self.cx, self.cy = cx, cy
        self.set_name("volume-window")
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_keep_above(True)
        self.set_wmclass(WM_CLASS, WM_CLASS)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)

        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.root.set_size_request(320, -1)
        self.root.set_property("margin", 15)
        self.add(self.root)

        # Volume Slider
        self.adj = Gtk.Adjustment(value=0, lower=0, upper=100, step_increment=1)
        self.scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.adj)
        self.scale.set_draw_value(False)
        self.scale.connect("value-changed", self._on_volume_change)
        self.root.pack_start(self.scale, False, False, 0)

        # Device Lists
        self.sinks_list = self._add_list("Outputs")
        self.sources_list = self._add_list("Inputs")

        # Pavucontrol Button
        btn = Gtk.Button(label="  Advanced Audio Settings", name="pavu-btn")
        btn.connect("clicked", lambda _: subprocess.Popen(["pavucontrol"]))
        self.root.pack_end(btn, False, False, 0)

        self._apply_style()
        self._refresh_data()
        self.show_all()
        GLib.timeout_add(50, self._do_position)

    def _add_list(self, title):
        self.root.pack_start(Gtk.Label(label=title, xalign=0), False, False, 0)
        lb = Gtk.ListBox()
        lb.connect("row-activated", self._on_row_ui)
        self.root.pack_start(lb, False, False, 0)
        return lb

    def _on_row_ui(self, lb, row):
        cmd = "set-default-sink" if lb == self.sinks_list else "set-default-source"
        subprocess.run(["pactl", cmd, row.dev_name])
        Gtk.main_quit()

    def _refresh_data(self):
        try:
            v = subprocess.check_output("pactl get-sink-volume @DEFAULT_SINK@ | grep -Po '\\d+(?=%)' | head -n1", shell=True, text=True)
            self.adj.set_value(int(v))
            for dev, lb in [("sinks", self.sinks_list), ("sources", self.sources_list)]:
                raw = subprocess.check_output(f"pactl list short {dev}", shell=True, text=True)
                for line in raw.strip().split('\n'):
                    name = line.split('\t')[1]
                    r = Gtk.ListBoxRow(); r.dev_name = name
                    l = Gtk.Label(label=name.split('.')[-1], xalign=0)
                    l.set_ellipsize(Pango.EllipsizeMode.END)
                    r.add(l); lb.add(r)
        except: pass

    def _on_volume_change(self, s):
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{int(s.get_value())}%"])

    def _apply_style(self):
        css = f"""
        #volume-window {{
            background-color: {self.c['background']};
            border: 2px solid {self.c['accent']};
            border-radius: 12px;
        }}

        /* 1. VOLUME BAR - Kill background images and focus rings */
        scale trough {{
            background-color: {self.c['dim']};
            background-image: none;
            min-height: 12px;
            border-radius: 8px;
        }}
        scale highlight {{
            background-color: {self.c['accent']};
            background-image: none;
            border-radius: 8px;
        }}
        scale slider {{
            background-color: {self.c['foreground']};
            background-image: none;
            border-radius: 100%;
            min-width: 18px;
            min-height: 18px;
        }}
        scale:focus, scale trough:focus, scale slider:focus {{
            outline-color: transparent;
            box-shadow: none;
        }}

        /* 2. DEVICE LISTS - Kill the red hover gradient */
        listbox row {{
            padding: 8px;
            border-radius: 6px;
            background-color: transparent;
            background-image: none;
        }}
        listbox row:hover, listbox row:selected, listbox row:focus {{
            background-color: {self.c['accent']};
            background-image: none;
            color: {self.c['background']};
            outline-color: transparent;
            box-shadow: none;
        }}

        /* 3. PAVUCONTROL BUTTON */
        #pavu-btn {{
            background-color: {self.c['dim']};
            background-image: none;
            color: {self.c['accent']};
            border: 1px solid {self.c['accent']};
            border-radius: 8px;
            margin-top: 10px;
            padding: 6px;
        }}
        #pavu-btn:hover, #pavu-btn:focus {{
            background-color: {self.c['accent']};
            background-image: none;
            color: {self.c['background']};
            outline-color: transparent;
        }}
        """
        provider = Gtk.CssProvider()
        try:
            provider.load_from_data(css.encode())
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except Exception as e:
            print(f"CSS Load Error: {e}")

    def _do_position(self):
        mx, my, mw, mh, cx, cy = get_monitor_geometry()
        rw = self.get_allocated_width()
        rh = self.get_allocated_height()
        x = max(mx + PAD, min(self.cx - rw // 2, mx + mw - rw - PAD))
        y = my + mh - rh - BAR_H - PAD
        subprocess.Popen(['hyprctl', 'dispatch', 'movewindowpixel', f'exact {int(x)} {int(y)},class:{WM_CLASS}'])
        return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cx', type=int, default=0)
    parser.add_argument('--cy', type=int, default=0)
    args = parser.parse_args()
    win = VolumePopup(args.cx, args.cy)
    win.connect('focus-out-event', lambda *_: Gtk.main_quit())
    Gtk.main()
