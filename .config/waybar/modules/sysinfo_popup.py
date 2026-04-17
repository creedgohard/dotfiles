#!/usr/bin/env python3
"""
Waybar System-Info Popup
─────────────────────────
Live-updating CPU / RAM / GPU panel.
Wayland-safe positioning via hyprctl dispatch movewindowpixel.

Usage:  python3 sysinfo_popup.py --cx CURSOR_X --cy CURSOR_Y
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib

import json, os, subprocess, glob, argparse

REFRESH_MS = 1200
WM_CLASS   = 'waybar-sysinfo'
BAR_H      = 32   # approximate top bar height
PAD        = 8

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

# ── System data collectors ────────────────────────────────────────────────────

def _read_proc_stat():
    stats = {}
    with open('/proc/stat') as f:
        for line in f:
            if not line.startswith('cpu'):
                break
            parts = line.split()
            vals = list(map(int, parts[1:8]))
            idle  = vals[3] + vals[4]
            total = sum(vals)
            stats[parts[0]] = (total, idle)
    return stats

_last_stat = {}
def get_cpu_usage():
    global _last_stat
    cur = _read_proc_stat()
    result = {}
    for key, (tot2, idl2) in cur.items():
        if key in _last_stat:
            tot1, idl1 = _last_stat[key]
            dt = tot2 - tot1
            di = idl2 - idl1
            result[key] = max(0.0, 100.0 * (1 - di / dt)) if dt else 0.0
        else:
            result[key] = 0.0
    _last_stat = cur
    return result

def get_cpu_freqs():
    freqs = []
    i = 0
    while True:
        p = f'/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_cur_freq'
        if not os.path.exists(p):
            break
        try:
            with open(p) as f:
                freqs.append(int(f.read()) // 1000)
        except Exception:
            freqs.append(0)
        i += 1
    return freqs

def get_sensors():
    result = {'cpu_temps': [], 'gpu_temp': None}
    try:
        raw = subprocess.run(['sensors', '-j'], capture_output=True, text=True, timeout=2)
        data = json.loads(raw.stdout)
        for chip, chip_data in data.items():
            cl = chip.lower()
            is_cpu = any(x in cl for x in ('k10temp', 'coretemp', 'zenpower', 'nct', 'it8'))
            is_gpu = any(x in cl for x in ('amdgpu', 'radeon', 'nvidia'))
            for feat_name, feat in chip_data.items():
                if not isinstance(feat, dict):
                    continue
                for k, v in feat.items():
                    if 'input' in k and isinstance(v, (int, float)):
                        if is_cpu and len(result['cpu_temps']) < 6:
                            result['cpu_temps'].append((feat_name, v))
                        if is_gpu and result['gpu_temp'] is None:
                            result['gpu_temp'] = v
    except Exception:
        pass
    return result

def get_ram():
    mem = {}
    with open('/proc/meminfo') as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                mem[parts[0].rstrip(':')] = int(parts[1])
    tot   = mem.get('MemTotal',    1)
    avail = mem.get('MemAvailable', 0)
    used  = tot - avail
    stot  = mem.get('SwapTotal',   0)
    sfree = mem.get('SwapFree',    0)
    sused = stot - sfree
    return {
        'total':      tot   / 1048576,
        'used':       used  / 1048576,
        'available':  avail / 1048576,
        'pct':        used / tot * 100,
        'swap_total': stot  / 1048576,
        'swap_used':  sused / 1048576,
        'swap_pct':  (sused / stot * 100) if stot else 0,
    }

def get_gpu():
    gpu = {'usage': 0, 'vram_used': 0.0, 'vram_total': 0.0, 'vram_pct': 0}
    for p in glob.glob('/sys/class/drm/card*/device/gpu_busy_percent'):
        try:
            with open(p) as f:
                gpu['usage'] = int(f.read().strip())
            break
        except Exception:
            pass
    for p in glob.glob('/sys/class/drm/card*/device/mem_info_vram_used'):
        try:
            with open(p) as f:
                gpu['vram_used'] = int(f.read().strip()) / 1073741824
            break
        except Exception:
            pass
    for p in glob.glob('/sys/class/drm/card*/device/mem_info_vram_total'):
        try:
            with open(p) as f:
                gpu['vram_total'] = int(f.read().strip()) / 1073741824
            break
        except Exception:
            pass
    if gpu['vram_total'] > 0:
        gpu['vram_pct'] = gpu['vram_used'] / gpu['vram_total'] * 100
    return gpu

# ── Widget helpers ────────────────────────────────────────────────────────────

def make_label(text='', markup=None, align=Gtk.Align.START, name=None):
    lbl = Gtk.Label(label=text)
    if markup:
        lbl.set_markup(markup)
        lbl.set_use_markup(True)
    lbl.set_halign(align)
    if name:
        lbl.set_name(name)
    return lbl

def make_bar(pct, width=140):
    bar = Gtk.ProgressBar()
    bar.set_fraction(min(1.0, max(0.0, pct / 100.0)))
    bar.set_size_request(width, -1)
    return bar

# ── Main window ───────────────────────────────────────────────────────────────

class SysInfoPopup(Gtk.Window):
    def __init__(self, cursor_x=0, cursor_y=0):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
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
        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        self._apply_css()

        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.root.set_margin_start(16)
        self.root.set_margin_end(16)
        self.root.set_margin_top(14)
        self.root.set_margin_bottom(14)
        self.add(self.root)

        self.cpu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.ram_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.gpu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)

        self._build_skeleton()

        # Warm up CPU diff
        get_cpu_usage()

        self.connect('realize',         self._on_realize)
        self.connect('key-press-event', self._on_key)
        self.connect('focus-out-event', self._on_focus_out)
        self.connect('destroy',         Gtk.main_quit)

        GLib.timeout_add(REFRESH_MS, self._refresh)

    # ── CSS ──────────────────────────────────────────────────────────────────

    def _apply_css(self):
        c = self.c
        css = f"""
        window {{
            background-color: {c['background']};
            border: 1px solid {c['accent']};
            border-radius: 10px;
        }}
        label {{
            color:       {c['foreground']};
            font-family: "0xProto Nerd Font", monospace;
            font-size:   12px;
        }}
        label#section-title {{
            color:       {c['accent']};
            font-size:   13px;
            font-weight: bold;
        }}
        label#dim {{
            color:     {c['text_dim']};
            font-size: 11px;
        }}
        separator {{
            background-color: {c['accent']};
            min-height:       1px;
            opacity:          0.2;
            margin:           6px 0;
        }}
        progressbar trough {{
            background-color: {c['dim']};
            border-radius:    4px;
            min-height:       5px;
        }}
        progressbar progress {{
            background-color: {c['accent']};
            border-radius:    4px;
        }}
        progressbar.warn progress {{
            background-color: {c['warn']};
        }}
        progressbar.crit progress {{
            background-color: {c['crit']};
        }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # ── Skeleton ─────────────────────────────────────────────────────────────

    def _build_skeleton(self):
        def section(icon, text, box):
            title = make_label(markup=f'<b>{icon}  {text}</b>', name='section-title')
            self.root.pack_start(title, False, False, 0)
            self.root.pack_start(box,   True,  True,  4)

        section('', 'CPU', self.cpu_box)
        self.root.pack_start(Gtk.Separator(), False, False, 0)
        section('', 'Memory', self.ram_box)
        self.root.pack_start(Gtk.Separator(), False, False, 0)
        section('󰾲', 'GPU', self.gpu_box)

    # ── Data rows ─────────────────────────────────────────────────────────────

    def _stat_row(self, parent_box, label, value_str, pct=None):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        lbl = make_label(label, name='dim')
        lbl.set_size_request(110, -1)
        row.pack_start(lbl, False, False, 0)

        val = make_label(value_str)
        val.set_size_request(140, -1)
        row.pack_start(val, False, False, 0)

        if pct is not None:
            bar = make_bar(pct)
            if pct >= 90:
                bar.get_style_context().add_class('crit')
            elif pct >= 70:
                bar.get_style_context().add_class('warn')
            row.pack_start(bar, True, True, 0)

        parent_box.pack_start(row, False, False, 0)

    def _clear_box(self, box):
        for child in box.get_children():
            box.remove(child)
            child.destroy()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def _refresh(self):
        try:
            self._do_refresh()
        except Exception:
            pass
        return True

    def _do_refresh(self):
        c = self.c

        # CPU
        cpu_usage = get_cpu_usage()
        cpu_freqs = get_cpu_freqs()
        sens      = get_sensors()

        self._clear_box(self.cpu_box)
        overall = cpu_usage.get('cpu', 0)
        self._stat_row(self.cpu_box, 'Overall', f'{overall:.1f}%', overall)

        cores = sorted(
            [k for k in cpu_usage if k != 'cpu'],
            key=lambda x: int(x[3:])
        )
        for k in cores[:16]:
            n     = int(k[3:])
            usage = cpu_usage[k]
            freq  = f'  {cpu_freqs[n]} MHz' if n < len(cpu_freqs) else ''
            self._stat_row(self.cpu_box, f'Core {n}', f'{usage:.1f}%{freq}', usage)

        for name, temp in sens['cpu_temps'][:4]:
            color = c['crit'] if temp > 90 else (c['warn'] if temp > 75 else c['foreground'])
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            lbl = make_label(name, name='dim')
            lbl.set_size_request(110, -1)
            row.pack_start(lbl, False, False, 0)
            val = make_label()
            val.set_markup(f'<span foreground="{color}">{temp:.1f}°C</span>')
            row.pack_start(val, False, False, 0)
            self.cpu_box.pack_start(row, False, False, 0)

        # RAM
        ram = get_ram()
        self._clear_box(self.ram_box)
        self._stat_row(self.ram_box, 'Used',
                       f'{ram["used"]:.2f} / {ram["total"]:.2f} GB', ram['pct'])
        self._stat_row(self.ram_box, 'Available', f'{ram["available"]:.2f} GB')
        if ram['swap_total'] > 0:
            self._stat_row(self.ram_box, 'Swap',
                           f'{ram["swap_used"]:.2f} / {ram["swap_total"]:.2f} GB',
                           ram['swap_pct'])

        # GPU
        gpu = get_gpu()
        self._clear_box(self.gpu_box)
        self._stat_row(self.gpu_box, 'Usage', f'{gpu["usage"]}%', gpu['usage'])
        if gpu['vram_total'] > 0:
            self._stat_row(self.gpu_box, 'VRAM',
                           f'{gpu["vram_used"]:.2f} / {gpu["vram_total"]:.2f} GB',
                           gpu['vram_pct'])
        if sens['gpu_temp'] is not None:
            color = c['crit'] if sens['gpu_temp'] > 90 else (
                    c['warn'] if sens['gpu_temp'] > 75 else c['foreground'])
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            lbl = make_label('Temperature', name='dim')
            lbl.set_size_request(110, -1)
            row.pack_start(lbl, False, False, 0)
            val = make_label()
            val.set_markup(f'<span foreground="{color}">{sens["gpu_temp"]:.1f}°C</span>')
            row.pack_start(val, False, False, 0)
            self.gpu_box.pack_start(row, False, False, 0)

        self.show_all()

    # ── Positioning ───────────────────────────────────────────────────────────

    def _on_realize(self, *_):
        self._refresh()
        self.show_all()
        GLib.timeout_add(50, self._do_position)
        self.present()
        self.grab_focus()

    def _do_position(self):
        """
        Position popup just below the top bar, horizontally centred
        on the click X — done via hyprctl so it works on Wayland.
        """
        req    = self.get_preferred_size()[1]
        pw, ph = req.width, req.height

        mon_x, mon_y, mon_w, mon_h = get_monitor_geometry()

        # Horizontally: centre on cursor, clamped to monitor
        x = self.cursor_x - pw // 2
        x = max(mon_x + PAD, min(x, mon_x + mon_w - pw - PAD))

        # Vertically: just below the top bar
        y = mon_y + BAR_H + PAD

        hypr_move(WM_CLASS, x, y)
        return False

    # ── Events ────────────────────────────────────────────────────────────────

    def _on_key(self, _w, event):
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()

    def _on_focus_out(self, *_):
        GLib.timeout_add(200, Gtk.main_quit)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cx', type=int, default=0)
    parser.add_argument('--cy', type=int, default=0)
    args = parser.parse_args()

    win = SysInfoPopup(cursor_x=args.cx, cursor_y=args.cy)
    win.show_all()
    Gtk.main()
