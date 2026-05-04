#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Playerctl', '2.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Playerctl
import json, os, subprocess, threading, urllib.request, tempfile

WM_CLASS = 'waybar-mediaplayer'
BAR_H    = 28
PAD      = 0

GLib.set_prgname(WM_CLASS)

class MediaPopup(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)

        # Identity & Basic Properties
        self.set_name("popup-window")
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)

        # Create Layout
        self.root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        self.root.set_size_request(350, -1)
        self.root.set_name("main-root")
        self.root.set_property("margin", 15)
        self.add(self.root)

        self.art_image = Gtk.Image()
        self.art_image.set_size_request(80, 80)
        self.root.pack_start(self.art_image, False, False, 0)

        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.vbox.set_valign(Gtk.Align.CENTER)
        self.root.pack_start(self.vbox, True, True, 0)

        self.title_label = Gtk.Label(label="Initializing...", name="title")
        self.artist_label = Gtk.Label(label="Connecting to system...", name="artist")
        for lbl in [self.title_label, self.artist_label]:
            lbl.set_halign(Gtk.Align.START)
            lbl.set_ellipsize(3)
            # FIX: Force a minimum width in characters so text doesn't cut off
            lbl.set_width_chars(25)
            self.vbox.pack_start(lbl, False, False, 0)

        self.btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        self.vbox.pack_start(self.btn_box, True, True, 5)

        self.btn_prev = Gtk.Button(label="󰒮", name="btn")
        self.btn_play = Gtk.Button(label="󰐊", name="btn")
        self.btn_next = Gtk.Button(label="󰒭", name="btn")
        for b in [self.btn_prev, self.btn_play, self.btn_next]:
            self.btn_box.pack_start(b, True, False, 0)

        self.show_all()

        # Start the background data fetching
        self.player = None
        GLib.timeout_add(100, self._async_init)

    def _async_init(self):
        threading.Thread(target=self._load_data_thread, daemon=True).start()
        return False

    def _load_data_thread(self):
        import re
        colors = {'background': '#1a1b26', 'foreground': '#a9b1d6', 'accent': '#7aa2f7'}
        try:
            path = os.path.expanduser('~/.cache/wal/colors.json')
            if os.path.exists(path):
                with open(path) as f:
                    data = json.load(f)

                # Load standard Pywal colors
                colors = {
                    'background': data['special'].get('background', colors['background']),
                    'foreground': data['special'].get('foreground', colors['foreground']),
                    'accent':     data['colors'].get('color2',     colors['accent']),
                }

                # Precision Override: Match the Waybar @accent exactly
                try:
                    css_path = os.path.expanduser('~/.config/waybar/colors.css')
                    with open(css_path) as f:
                        content = f.read()
                        match = re.search(r'@define-color\s+accent\s+([^;]+);', content)
                        if match:
                            val = match.group(1).strip()
                            if val.startswith('#'):
                                colors['accent'] = val
                            elif val.startswith('@'):
                                colors['accent'] = data['colors'].get(val.replace('@', ''), colors['accent'])
                except:
                    pass
        except:
            pass

        try:
            player = Playerctl.Player.new()
        except:
            player = None

        GLib.idle_add(self._finalize_init, colors, player)

    def _finalize_init(self, colors, player):
        self.c = colors
        self.player = player

        # FIX: We apply the background to the WINDOW widget (#popup-window)
        # to eliminate the default grey GTK background.
        # --- Clean Multi-line CSS ---
        css = f"""
        #popup-window {{
            background-color: {self.c['background']};
            border: 1px solid {self.c['accent']};
            border-top: 0px solid {self.c['accent']};
            margin-top: -2px;           /* Overlap the bar */
            border-radius: 0 0 10px 10px; /* Round only the bottom */
        }}
        label#title {{
            color: {self.c['accent']};
            font-weight: bold;
            font-size: 14px;
            font-family: "0xProto Nerd Font";
        }}
        label#artist {{
            color: {self.c['foreground']};
            font-size: 12px;
            opacity: 0.8;
            font-family: "0xProto Nerd Font";
        }}
        button#btn {{
            background: transparent;
            border: none;
            color: {self.c['foreground']};
            font-size: 20px;
            box-shadow: none;
        }}
        button#btn:hover {{
            color: {self.c['accent']};
        }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        if self.player:
            self.btn_prev.connect("clicked", lambda _: self.player.previous())
            self.btn_play.connect("clicked", lambda _: self.player.play_pause())
            self.btn_next.connect("clicked", lambda _: self.player.next())
            self._update_loop()
        else:
            self.title_label.set_text("No Player Found")
            self.artist_label.set_text("Start music first")

        self._do_pos()
        return False

    def _update_loop(self):
        if not self.player: return False
        try:
            self.title_label.set_text(self.player.get_title() or "Unknown")
            self.artist_label.set_text(self.player.get_artist() or "Unknown")
            status = self.player.get_property("playback-status")
            self.btn_play.set_label("󰏤" if status == Playerctl.PlaybackStatus.PLAYING else "󰐊")

            metadata = self.player.get_property("metadata")
            if metadata and 'mpris:artUrl' in metadata.keys():
                art = metadata['mpris:artUrl']
                threading.Thread(target=self._load_art, args=(art,), daemon=True).start()
        except: pass
        GLib.timeout_add(2000, self._update_loop)

    def _load_art(self, url):
        try:
            path = url
            if url.startswith('http'):
                with urllib.request.urlopen(url, timeout=2) as r:
                    with tempfile.NamedTemporaryFile(delete=False) as f:
                        f.write(r.read()); path = f.name
            elif url.startswith('file://'): path = url[7:]
            pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 80, 80, True)
            GLib.idle_add(self.art_image.set_from_pixbuf, pix)
        except: pass

    # --- Precise Positioning Logic ---
    def _do_pos(self):
        try:
            # 1. Get Monitor Data
            mon_data = json.loads(subprocess.check_output(['hyprctl', 'monitors', '-j']))
            active_mon = next(m for m in mon_data if m['focused'])
            mon_y = active_mon['y']

            # 2. Get actual Waybar height from layers (kills the gap)
            layers = json.loads(subprocess.check_output(['hyprctl', 'layers', '-j']))
            # Find the waybar layer on the current monitor
            waybar_layer = None
            mon_name = active_mon['name']
            if mon_name in layers:
                for layer in layers[mon_name]['levels']['0']:
                    if layer['namespace'] == 'waybar':
                        waybar_layer = layer
                        break

            # Use the actual reserved top margin, or fallback to your BAR_H if not found
            actual_bar_h = waybar_layer['margin'][0] if waybar_layer else BAR_H

            # 3. Calculate Coordinates
            out = subprocess.check_output(['hyprctl', 'cursorpos']).decode().strip()
            cur_x = int(out.split(',')[0])
            req = self.get_preferred_size()[1]
            x = cur_x - (req.width // 2)

            # Move exactly to the edge of the bar
            target_y = mon_y + actual_bar_h

            subprocess.Popen(['hyprctl', 'dispatch', 'movewindowpixel', f'exact {x} {target_y},class:{WM_CLASS}'])
        except Exception as e:
            print(f"Positioning failed: {e}")

    def _on_leave(self, widget, event):
        if event.detail != Gdk.NotifyType.INFERIOR:
            Gtk.main_quit()

if __name__ == '__main__':
    win = MediaPopup()
    win.connect('focus-out-event', lambda *_: Gtk.main_quit())
    win.connect('leave-notify-event', win._on_leave)
    Gtk.main()
