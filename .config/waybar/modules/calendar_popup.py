#!/usr/bin/env python3
"""
Waybar Interactive Calendar Popup
──────────────────────────────────
Wayland-safe positioning via hyprctl dispatch movewindowpixel.
Reads pywal colours from ~/.cache/wal/colors.json.

Usage:  python3 calendar_popup.py --cx CURSOR_X --cy CURSOR_Y
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib

import json, os, subprocess, datetime, argparse, sys

WM_CLASS = 'waybar-calendar'
BAR_H    = 36   # approximate bottom bar height in pixels
PAD      = 8

GLib.set_prgname(WM_CLASS)

# ── Colours ───────────────────────────────────────────────────────────────────

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

# ── Wayland positioning via hyprctl ──────────────────────────────────────────

def hypr_move(wm_class, x, y):
    """Ask Hyprland to move the floating window to pixel coords x,y."""
    subprocess.Popen(
        ['hyprctl', 'dispatch', 'movewindowpixel',
         f'exact {x} {y},class:{wm_class}'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

def get_monitor_geometry():
    """Return (x, y, w, h) of the monitor currently containing the cursor."""
    cx, cy = get_cursor_pos()
    try:
        raw = subprocess.run(['hyprctl', 'monitors', '-j'], capture_output=True, text=True, timeout=2)
        monitors = json.loads(raw.stdout)
        for m in monitors:
            x, y = m.get('x', 0), m.get('y', 0)
            w, h = m.get('width', 1920), m.get('height', 1080)
            # Check if the cursor coordinates fall inside this monitor's area
            if x <= cx <= x + w and y <= cy <= y + h:
                return x, y, w, h
    except Exception:
        pass
    return 0, 0, 1920, 1080

def get_cursor_pos():
    """Ask Hyprland exactly where the mouse is right now."""
    try:
        raw = subprocess.run(['hyprctl', 'cursorpos', '-j'], capture_output=True, text=True)
        pos = json.loads(raw.stdout)
        return pos.get('x', 0), pos.get('y', 0)
    except Exception:
        return 0, 0

# ── Main window ───────────────────────────────────────────────────────────────

class CalendarPopup(Gtk.Window):
    def __init__(self, cursor_x=0, cursor_y=0):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_opacity(0)
        if cursor_x == 0 and cursor_y == 0:
            cursor_x, cursor_y = get_cursor_pos()
        self.cursor_x = cursor_x
        self.cursor_y = cursor_y
        self.c = get_wal_colors()

        self.set_title(WM_CLASS)
        self.set_wmclass(WM_CLASS, WM_CLASS)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        self._apply_css()
        self._build_ui()

        self.connect('realize',         self._on_realize)
        self.connect('key-press-event', self._on_key)
        self.connect('focus-out-event', self._on_focus_out)
        self.connect('destroy',         Gtk.main_quit)

    # ── CSS ──────────────────────────────────────────────────────────────────

    def _apply_css(self):
        c = self.c
        css = f"""
        window {{
            background-color: {c['background']};
            border: 1px solid {c['accent']};
            border-radius: 10px;
        }}
        calendar {{
            background-color: {c['background']};
            color:            {c['foreground']};
            font-family:      "0xProto Nerd Font", monospace;
            font-size:        13px;
            padding:          6px;
        }}
        calendar.header {{
            color:       {c['accent']};
            font-weight: bold;
            font-size:   14px;
        }}
        calendar.button {{
            color:            {c['accent']};
            background-color: transparent;
            border:           none;
        }}
        calendar.button:hover {{
            color: {c['foreground']};
        }}
        calendar.highlight {{
            color:     {c['text_dim']};
            font-size: 11px;
        }}
        calendar:selected {{
            background-color: transparent;
            color:            {c['accent']};
            font-weight:      bold;
            /* This removes the background circle and just colors the text */
            border-radius:    0;
        }}
        calendar.dimmed {{
            color: {c['dim']};
        }}
        #today-btn {{
            background-color: transparent;
            color:            {c['accent']};
            border:           1px solid {c['accent']};
            border-radius:    5px;
            padding:          4px 12px;
            font-family:      "0xProto Nerd Font", monospace;
            font-size:        12px;
            font-weight:      bold;
        }}
        #today-btn:hover {{
            background-color: {c['accent']};
            color:            #ffffff;
        }}
        #date-label {{
            color:       {c['text_dim']};
            font-family: "0xProto Nerd Font", monospace;
            font-size:   11px;
        }}
        separator {{
            background-color: {c['accent']};
            min-height:       1px;
            opacity:          0.25;
            margin:           2px 0;
        }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        outer.set_margin_top(10)
        outer.set_margin_bottom(10)

        self.cal = Gtk.Calendar()
        self.cal.set_property('show-heading',      True)
        self.cal.set_property('show-day-names',    True)
        self.cal.set_property('show-week-numbers', False)
        self.cal.connect('day-selected', self._on_day_selected)
        outer.pack_start(self.cal, True, True, 0)

        outer.pack_start(Gtk.Separator(), False, False, 6)

        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.date_label = Gtk.Label(label='')
        self.date_label.set_name('date-label')
        self.date_label.set_halign(Gtk.Align.START)
        self._refresh_date_label()
        bottom.pack_start(self.date_label, True, True, 0)

        today_btn = Gtk.Button(label='  Today')
        today_btn.set_name('today-btn')
        today_btn.connect('clicked', self._go_today)
        bottom.pack_end(today_btn, False, False, 0)

        outer.pack_start(bottom, False, False, 0)
        self.add(outer)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _refresh_date_label(self):
        y, m, d = self.cal.get_date()
        try:
            dt = datetime.date(y, m + 1, max(1, d))
            self.date_label.set_text(dt.strftime('%A, %d %B %Y'))
        except ValueError:
            pass

    def _on_day_selected(self, _):
        self._refresh_date_label()

    def _go_today(self, *_):
        t = datetime.date.today()
        self.cal.select_month(t.month - 1, t.year)
        self.cal.select_day(t.day)
        self._refresh_date_label()

    # ── Positioning ───────────────────────────────────────────────────────────

    def _on_realize(self, *_):
        self.show_all()
        # Delay positioning slightly so the window has a real size allocated
        GLib.timeout_add(25, self._do_position)
        self.present()
        self.grab_focus()

    def _do_position(self):
        """
        Position popup just above the bottom bar, horizontally centred
        on the click X position — all done via hyprctl so it works on Wayland.
        """
        req      = self.get_preferred_size()[1]
        pw, ph   = req.width, req.height

        mon_x, mon_y, mon_w, mon_h = get_monitor_geometry()

        # Horizontally: centre on cursor, clamped to monitor
        x = self.cursor_x - pw // 2
        x = max(mon_x + PAD, min(x, mon_x + mon_w - pw - PAD))

        # Vertically: float above the bottom bar
        # cursor_y is near the bottom bar, so place popup above it
        y = mon_y + mon_h - ph - BAR_H - PAD

        hypr_move(WM_CLASS, x, y)
        self.set_opacity(1)
        return False   # run once

    # ── Events ────────────────────────────────────────────────────────────────

    def _on_key(self, _w, event):
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()

    def _on_focus_out(self, *_):
        GLib.timeout_add(25, Gtk.main_quit)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cx', type=int, default=0, help='Cursor X at click')
    parser.add_argument('--cy', type=int, default=0, help='Cursor Y at click')
    args = parser.parse_args()

    win = CalendarPopup(cursor_x=args.cx, cursor_y=args.cy)
    win.show_all()
    Gtk.main()
