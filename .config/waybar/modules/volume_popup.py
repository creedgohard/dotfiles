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
    import json, os, re
    path = os.path.expanduser('~/.cache/wal/colors.json')

    # 1. The Safety Net: We MUST define all keys so the UI never crashes
    defaults = {
        'background': '#000000', 'foreground': '#f3a8a7', 'accent': '#d6002f',
        'dim': '#2a2a2a', 'text_dim': '#777777', 'ok': '#44aa55',
        'warn': '#ffaa00', 'crit': '#ff2222',
    }

    try:
        with open(path) as f:
            data = json.load(f)
        sp = data.get('special', {})
        co = data.get('colors', {})

        # 2. Build the full color profile
        c = {
            'background': sp.get('background', defaults['background']),
            'foreground': sp.get('foreground', defaults['foreground']),
            'accent':     co.get('color2', defaults['accent']), # Fallback accent
            'dim':        co.get('color0', defaults['dim']),
            'text_dim':   co.get('color8', defaults['text_dim']),
            'ok':         co.get('color2', defaults['ok']),
            'warn':       co.get('color3', defaults['warn']),
            'crit':       co.get('color9', defaults['crit']),
        }

        # 3. Precision Override: Scan Waybar's CSS for the true accent
        try:
            with open(os.path.expanduser('~/.config/waybar/colors.css')) as f:
                content = f.read()
                # Find exactly how your theme script defined the accent
                match = re.search(r'@define-color\s+accent\s+([^;]+);', content)
                if match:
                    val = match.group(1).strip()
                    if val.startswith('#'):
                        c['accent'] = val
                    elif val.startswith('@'):
                        c['accent'] = co.get(val.replace('@', ''), c['accent'])
        except Exception:
            pass

        return c
    except Exception:
        return defaults

def get_cursor_pos():
    try:
        out = subprocess.check_output(['hyprctl', 'cursorpos'], text=True).strip()
        return map(int, out.split(','))
    except: return 0, 0

def get_monitor_geometry():
    cx, cy = get_cursor_pos()
    try:
        raw = subprocess.run(['hyprctl', 'monitors', '-j'], capture_output=True, text=True)
        monitors = json.loads(raw.stdout)
        for m in monitors:
            x, y, w, h = m['x'], m['y'], m['width'], m['height']
            if x <= cx <= x + w and y <= cy <= y + h:
                return x, y, w, h
    except: pass
    return 0, 0, 1920, 1080

class VolumePopup(Gtk.Window):
    def __init__(self, cx, cy):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.c = get_wal_colors()
        self.cx, self.cy = cx, cy

        self.set_name("volume-window")
        self.set_decorated(False)
        self.set_resizable(False) # Add this to prevent accidental stretching
        self.set_skip_taskbar_hint(True)
        self.set_keep_above(True)
        self.set_opacity(0) # Start invisible like the calendar

        self.set_wmclass(WM_CLASS, WM_CLASS)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)

        # Main Layout
        # In __init__, force a base width for the "box" look
        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.root.set_size_request(320, -1) # Forces width to 320px, height is automatic
        self.root.set_name("main-root")
        self.root.set_property("margin", 15)
        self.add(self.root)

        # Volume Slider
        vol_label = Gtk.Label(label="Volume", name="section-title")
        vol_label.set_halign(Gtk.Align.START)
        self.root.pack_start(vol_label, False, False, 0)

        self.adj = Gtk.Adjustment(value=0, lower=0, upper=100, step_increment=1, page_increment=10)
        self.scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.adj)
        self.scale.set_draw_value(False)
        self.scale.connect("value-changed", self._on_volume_change)
        self.root.pack_start(self.scale, False, False, 0)

        # Device Lists
        self.root.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 5)

        self._add_device_section("Outputs (Sinks)", "sinks")
        self._add_device_section("Inputs (Sources)", "sources")

        self._apply_style()
        self._refresh_data()
        self.show_all()
        GLib.timeout_add(50, self._do_position)

    def _add_device_section(self, title, dev_type):
        lbl = Gtk.Label(label=title, name="section-title")
        lbl.set_halign(Gtk.Align.START)
        self.root.pack_start(lbl, False, False, 0)

        listbox = Gtk.ListBox()
        listbox.set_name("device-list")
        listbox.connect("row-activated", lambda lb, row: self._set_default_device(dev_type, row.dev_name))
        self.root.pack_start(listbox, False, False, 0)
        setattr(self, f"{dev_type}_list", listbox)

    def _refresh_data(self):
        # Set Volume Slider
        try:
            curr_vol = subprocess.check_output("pactl get-sink-volume @DEFAULT_SINK@ | grep -Po '\\d+(?=%)' | head -n1", shell=True, text=True)
            self.adj.set_value(int(curr_vol))
        except: pass

        # Populate Devices
        for dev_type in ["sinks", "sources"]:
            lb = getattr(self, f"{dev_type}_list")
            for child in lb.get_children(): lb.remove(child)

            try:
                cmd = "sink" if dev_type == "sinks" else "source"
                raw = subprocess.check_output(f"pactl list short {cmd}s", shell=True, text=True)
                for line in raw.strip().split('\n'):
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        name, desc = parts[1], parts[1]
                        row = Gtk.ListBoxRow()
                        row.dev_name = name

                        # Fix long names here
                        lbl = Gtk.Label(label=desc.split('.')[-1], xalign=0)
                        lbl.set_ellipsize(Pango.EllipsizeMode.END) # Adds the '...'
                        lbl.set_max_width_chars(30) # Keeps the box narrow

                        row.add(lbl)
                        lb.add(row)
            except: pass

    def _on_volume_change(self, scale):
        val = int(scale.get_value())
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{val}%"])

    def _set_default_device(self, dev_type, name):
        cmd = "set-default-sink" if dev_type == "sinks" else "set-default-source"
        subprocess.run(["pactl", cmd, name])
        Gtk.main_quit()

    def _apply_style(self):
        css = f"""
        #volume-window {{ background-color: {self.c['background']}; border: 2px solid {self.c['accent']}; border-radius: 12px; }}
        label#section-title {{ color: {self.c['accent']}; font-weight: bold; font-size: 13px; margin-top: 5px; }}
        scale trough {{ background-color: {self.c['background']}; border: 1px solid {self.c['accent']}; min-height: 8px; border-radius: 4px; }}
        scale highlight {{ background-color: {self.c['accent']}; border-radius: 4px; }}
        listbox {{ background: transparent; color: {self.c['foreground']}; }}
        listbox row {{ padding: 5px; border-radius: 4px; }}
        listbox row:hover {{ background-color: {self.c['accent']}; color: {self.c['background']}; }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _do_position(self):
        self.set_opacity(1) # Reveal it only after it's in place
        req = self.get_preferred_size()[1]
        mon_x, mon_y, mon_w, mon_h = get_monitor_geometry()
        x = max(mon_x + PAD, min(self.cx - req.width // 2, mon_x + mon_w - req.width - PAD))
        y = mon_y + mon_h - req.height - BAR_H - PAD
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
