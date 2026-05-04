#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import json, os, subprocess

WM_CLASS = 'waybar-network'

def get_wal_colors():
    path = os.path.expanduser('~/.cache/wal/colors.json')
    defaults = {'background': '#000000', 'foreground': '#ffffff', 'accent': '#d6002f', 'dim': '#2a2a2a'}
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

class NetworkPopup(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.c = get_wal_colors()
        self.set_wmclass(WM_CLASS, WM_CLASS)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.set_decorated(False)
        self.set_keep_above(True)

        # Main Layout
        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        # We remove fixed height so it sizes to content
        self.root.set_size_request(320, -1)
        self.root.set_property("margin", 15)
        self.add(self.root)

        # Control Buttons
        self.controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.root.pack_start(self.controls, False, False, 0)

        self.btn_wifi = Gtk.Button(name="toggle-btn")
        self.btn_wifi.connect("clicked", self._toggle_wifi)
        self.controls.pack_start(self.btn_wifi, True, True, 0)

        self.btn_eth = Gtk.Button(name="toggle-btn")
        self.btn_eth.connect("clicked", self._show_eth_name)
        self.controls.pack_start(self.btn_eth, True, True, 0)

        # The Wi-Fi List Container
        self.list_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.root.pack_start(self.list_container, True, True, 0)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.connect("row-activated", self._on_wifi_select)

        # Add scroll only for the list
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_min_content_height(0)
        self.scroll.add(self.listbox)
        self.list_container.pack_start(self.scroll, True, True, 0)

        self._apply_style()
        self._refresh_status()
        self.show_all()

    def _apply_style(self):
        css = f"""
        #network-window {{
            background-color: {self.c['background']};
            border: 1px solid {self.c['accent']};
            border-radius: 10px 10px 0 0;
            border-bottom: 0px;
        }}
        #toggle-btn {{
            background-color: {self.c['dim']};
            color: {self.c['foreground']};
            border: 1px solid {self.c['accent']};
            border-radius: 8px;
            padding: 10px;
        }}
        #toggle-btn:hover {{
            background-color: {self.c['accent']};
            color: {self.c['background']};
        }}
        listbox row {{
            padding: 8px;
            color: {self.c['foreground']};
        }}
        listbox row:hover {{
            background-color: {self.c['accent']};
            color: {self.c['background']};
        }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _refresh_status(self):
        try:
            # Check Wi-Fi state
            wifi_on = subprocess.check_output(['nmcli', '-t', '-f', 'WIFI', 'radio']).decode().strip() == 'enabled'
            self.btn_wifi.set_label("  WiFi On" if wifi_on else "󰤮  WiFi Off")

            # Check Ethernet state[cite: 16]
            eth_out = subprocess.check_output(['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE', 'dev']).decode()
            self.eth_active = any('ethernet:connected' in line for line in eth_out.splitlines())
            self.btn_eth.set_label("  Ethernet" if self.eth_active else "󰈀  No Eth")

            # Show/Hide list and adjust window height[cite: 16]
            if wifi_on:
                self._populate_wifi()
                self.scroll.set_min_content_height(250)
                self.list_container.show_all()
            else:
                self.scroll.set_min_content_height(0)
                self.list_container.hide()

            # Force Hyprland to re-apply the "move" rule for the new height
            GLib.timeout_add(50, self._reposition)
        except: pass

    def _populate_wifi(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)
        try:
            scan = subprocess.check_output(['nmcli', '-t', '-f', 'SSID,BARS', 'dev', 'wifi']).decode()
            for line in scan.splitlines():
                if line.strip() and ":" in line:
                    ssid, bars = line.split(':')
                    if ssid:
                        row = Gtk.ListBoxRow()
                        row.ssid = ssid
                        row.add(Gtk.Label(label=f"{bars}  {ssid}", xalign=0))
                        self.listbox.add(row)
            self.listbox.show_all()
        except: pass

    def _show_eth_name(self, btn):
        if self.eth_active:
            try:
                # Fetches the name of the active wired connection[cite: 16]
                name = subprocess.check_output("nmcli -t -f TYPE,NAME con show --active | grep ethernet | cut -d: -f2", shell=True).decode().strip()
                btn.set_label(f"  {name}" if name else "  Connected")
            except:
                btn.set_label("  Connected")
        else:
            btn.set_label("󰈀  Disconnected")

    def _toggle_wifi(self, _):
        state = "off" if "On" in self.btn_wifi.get_label() else "on"
        subprocess.run(['nmcli', 'radio', 'wifi', state])
        # Give NM a moment to toggle before refreshing UI
        GLib.timeout_add(600, self._refresh_status)

    def _reposition(self):
        # Manually trigger the Hyprland move dispatch to ensure it stays pinned to the bottom bar[cite: 14]
        subprocess.run(["hyprctl", "dispatch", "forcerendererreload"], capture_output=True)
        return False

    def _on_wifi_select(self, lb, row):
        subprocess.Popen(['nmcli', 'dev', 'wifi', 'connect', row.ssid])
        Gtk.main_quit()

if __name__ == '__main__':
    GLib.set_prgname(WM_CLASS)
    win = NetworkPopup()
    win.set_name("network-window")
    win.connect('focus-out-event', lambda *_: Gtk.main_quit())
    Gtk.main()
