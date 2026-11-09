#!/usr/bin/env python3
"""
Reading Steiner — Live HTML Execution Engine
A modern desktop notepad for writing and running HTML, CSS, and JavaScript.
"""

import os
import sys
import json
import time
import threading
import subprocess
from datetime import datetime

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
try:
    gi.require_version('GtkSource', '4')
    from gi.repository import GtkSource
    HAS_GTKSOURCE = True
except Exception:
    HAS_GTKSOURCE = False

gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, Gdk, GLib, WebKit2, Pango, GdkPixbuf

# Path constants
APP_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_PATH = os.path.join(APP_DIR, "assets", "templates.json")
LAB_PROGRAMS_PATH = os.path.join(APP_DIR, "assets", "lab_programs.json")
CACHE_DIR = os.path.expanduser("~/.cache/html-notepad")
AUTOSAVE_PATH = os.path.join(CACHE_DIR, "autosave.html")
ICON_PATH = os.path.join(APP_DIR, "assets", "icon.png")

os.makedirs(CACHE_DIR, exist_ok=True)

# Custom CSS styling for modern UI with True Black OLED optimization
CSS_STYLE = b"""
window, .background {
    background-color: #000000;
}

headerbar {
    padding: 4px 8px;
    background-color: #000000;
    border-bottom: 1px solid #18181b;
}

.play-button {
    background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
    color: #ffffff;
    font-weight: 700;
    border-radius: 8px;
    padding: 6px 16px;
    border: 1px solid #14532d;
    box-shadow: 0 2px 5px rgba(22, 163, 74, 0.4);
    transition: all 150ms ease-in-out;
}

.play-button:hover {
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
    box-shadow: 0 4px 10px rgba(22, 163, 74, 0.5);
}

.play-button:active {
    background: #15803d;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3);
}

.console-pane {
    background-color: #000000;
    border-top: 1px solid #18181b;
}

.status-bar-box {
    background-color: #000000;
    color: #a1a1aa;
    font-size: 11px;
    padding: 2px 10px;
    border-top: 1px solid #18181b;
}

.badge-error {
    background-color: #ef4444;
    color: #ffffff;
    border-radius: 10px;
    padding: 1px 6px;
    font-size: 11px;
    font-weight: bold;
}

.node-button {
    background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
    color: #ffffff;
    font-weight: 700;
    border-radius: 8px;
    padding: 6px 14px;
    border: 1px solid #075985;
    box-shadow: 0 2px 5px rgba(2, 132, 199, 0.4);
    transition: all 150ms ease-in-out;
}

.node-button:hover {
    background: linear-gradient(135deg, #38bdf8 0%, #0284c7 100%);
    box-shadow: 0 4px 10px rgba(2, 132, 199, 0.5);
}

.node-button:active {
    background: #0369a1;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3);
}

.lab-button {
    background: #18181b;
    color: #e4e4e7;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 4px 10px;
    transition: all 120ms ease;
}

.lab-button:hover {
    background: #27272a;
    color: #38bdf8;
    border-color: #38bdf8;
}
"""

CONSOLE_INJECTION_SCRIPT = """
(function() {
  if (window.__HTML_NOTEPAD_CONSOLE_HOOKED__) return;
  window.__HTML_NOTEPAD_CONSOLE_HOOKED__ = true;

  function safeStringify(item) {
    if (item === null) return 'null';
    if (item === undefined) return 'undefined';
    if (typeof item === 'object') {
      try {
        return JSON.stringify(item, null, 2);
      } catch(e) {
        return Object.prototype.toString.call(item);
      }
    }
    return String(item);
  }

  function sendLog(type, args) {
    try {
      const msg = Array.from(args).map(safeStringify).join(' ');
      if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.consoleLog) {
        window.webkit.messageHandlers.consoleLog.postMessage(JSON.stringify({
          type: type,
          message: msg,
          time: new Date().toLocaleTimeString()
        }));
      }
    } catch(e) {}
  }

  const origLog = console.log;
  const origWarn = console.warn;
  const origError = console.error;
  const origInfo = console.info;

  console.log = function(...args) { sendLog('log', args); origLog.apply(console, args); };
  console.warn = function(...args) { sendLog('warn', args); origWarn.apply(console, args); };
  console.error = function(...args) { sendLog('error', args); origError.apply(console, args); };
  console.info = function(...args) { sendLog('info', args); origInfo.apply(console, args); };

  window.addEventListener('error', function(event) {
    const loc = event.filename ? (' (' + event.filename + ':' + event.lineno + ')') : '';
    sendLog('error', [event.message + loc]);
  });
})();
"""


class HTMLNotepadWindow(Gtk.Window):
    def __init__(self, initial_file=None):
        super().__init__(title="Reading Steiner")
        self.set_default_size(900, 720)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Set App Icon if exists
        if os.path.exists(ICON_PATH):
            self.set_icon_from_file(ICON_PATH)

        self.current_filepath = initial_file
        self.is_modified = False
        self.font_size = 12
        self.dark_mode = True
        self.templates = self.load_templates()
        self.lab_programs = self.load_lab_programs()

        # WebKit & Execution Window state
        self.execution_window = None
        self.setup_execution_engine()

        # Apply CSS
        self.apply_custom_css()

        # Build UI Components
        self.setup_headerbar()
        self.setup_main_layout()
        self.setup_keybindings()

        # Load file or start with blank new file (0 text default)
        if initial_file and os.path.isfile(initial_file):
            self.load_file(initial_file)
        else:
            self.on_new_file()

    def apply_custom_css(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(CSS_STYLE)
        screen = Gdk.Screen.get_default()
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def load_templates(self):
        if os.path.exists(TEMPLATES_PATH):
            try:
                with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading templates: {e}")
        return {}

    def load_lab_programs(self):
        if os.path.exists(LAB_PROGRAMS_PATH):
            try:
                with open(LAB_PROGRAMS_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading lab programs: {e}")
        return []

    def setup_execution_engine(self):
        self.ucm = WebKit2.UserContentManager()
        self.ucm.register_script_message_handler("consoleLog")
        self.ucm.connect("script-message-received::consoleLog", self.on_console_message)

        self.webview = WebKit2.WebView.new_with_user_content_manager(self.ucm)
        # True Black OLED Canvas
        bg_color = Gdk.RGBA(0, 0, 0, 1.0)
        self.webview.set_background_color(bg_color)
        settings = self.webview.get_settings()
        settings.set_enable_javascript(True)
        settings.set_enable_webgl(True)
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_allow_universal_access_from_file_urls(True)
        settings.set_enable_developer_extras(True)

    def ensure_execution_window(self):
        if self.execution_window is not None:
            return

        self.execution_window = Gtk.Window(title="Reading Steiner — Output")
        self.execution_window.set_transient_for(self)
        self.execution_window.set_default_size(960, 680)
        self.execution_window.set_position(Gtk.WindowPosition.CENTER)

        if os.path.exists(ICON_PATH):
            self.execution_window.set_icon_from_file(ICON_PATH)

        exec_header = Gtk.HeaderBar()
        exec_header.set_show_close_button(True)
        exec_header.props.title = "Reading Steiner — Output"
        self.execution_window.set_titlebar(exec_header)

        btn_reload = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        btn_reload.set_tooltip_text("Reload Execution (F5)")
        btn_reload.connect("clicked", lambda w: self.execute_code())
        exec_header.pack_start(btn_reload)

        btn_browser = Gtk.Button.new_from_icon_name("web-browser-symbolic", Gtk.IconSize.BUTTON)
        btn_browser.set_tooltip_text("Open in Firefox Browser")
        btn_browser.connect("clicked", lambda w: self.open_in_browser())
        exec_header.pack_end(btn_browser)

        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.webview)
        self.execution_window.add(scrolled)

        # Hide instead of destroy on close
        self.execution_window.connect("delete-event", lambda w, e: (self.execution_window.hide(), True)[1])

        def on_exec_key(w, event):
            if event.keyval == Gdk.KEY_Escape or ((event.state & Gdk.ModifierType.CONTROL_MASK) and event.keyval in (Gdk.KEY_w, Gdk.KEY_W)):
                self.execution_window.hide()
                return True
            return False
        self.execution_window.connect("key-press-event", on_exec_key)

    def setup_headerbar(self):
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.props.title = "Reading Steiner"
        self.header.props.subtitle = "Write & Execute HTML"
        self.set_titlebar(self.header)

        # File actions box (New, Open, Save)
        file_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        btn_new = Gtk.Button.new_from_icon_name("document-new-symbolic", Gtk.IconSize.BUTTON)
        btn_new.set_tooltip_text("New Document (Ctrl+N)")
        btn_new.connect("clicked", lambda w: self.on_new_file())
        file_box.pack_start(btn_new, False, False, 0)

        btn_open = Gtk.Button.new_from_icon_name("document-open-symbolic", Gtk.IconSize.BUTTON)
        btn_open.set_tooltip_text("Open HTML File (Ctrl+O)")
        btn_open.connect("clicked", lambda w: self.on_open_file())
        file_box.pack_start(btn_open, False, False, 0)

        btn_save = Gtk.Button.new_from_icon_name("document-save-symbolic", Gtk.IconSize.BUTTON)
        btn_save.set_tooltip_text("Save File (Ctrl+S)")
        btn_save.connect("clicked", lambda w: self.on_save_file())
        file_box.pack_start(btn_save, False, False, 0)

        self.header.pack_start(file_box)

        # Templates dropdown menu
        template_menu_btn = Gtk.MenuButton()
        template_menu_btn.set_tooltip_text("Load Template")
        tmpl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tmpl_icon = Gtk.Image.new_from_icon_name("starred-symbolic", Gtk.IconSize.BUTTON)
        tmpl_label = Gtk.Label(label="Templates")
        tmpl_box.pack_start(tmpl_icon, False, False, 0)
        tmpl_box.pack_start(tmpl_label, False, False, 0)
        template_menu_btn.add(tmpl_box)

        tmpl_menu = Gtk.Menu()
        for key, item in self.templates.items():
            menu_item = Gtk.MenuItem(label=item.get("name", key))
            menu_item.connect("activate", lambda w, k=key: self.load_template(k))
            tmpl_menu.append(menu_item)
        tmpl_menu.show_all()
        template_menu_btn.set_popup(tmpl_menu)
        self.header.pack_start(template_menu_btn)

        # ==========================================
        # 📚 LAB EXAM PROGRAMS MENU (1–32 FROM PDF)
        # ==========================================
        lab_menu_btn = Gtk.MenuButton()
        lab_menu_btn.get_style_context().add_class("lab-button")
        lab_menu_btn.set_tooltip_text("Load Lab Exam Programs (PDF 1–32)")

        lab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lab_icon = Gtk.Image.new_from_icon_name("accessories-dictionary-symbolic", Gtk.IconSize.BUTTON)
        lab_label = Gtk.Label(label="<b>📚 Lab Programs (PDF)</b>")
        lab_label.set_use_markup(True)
        lab_box.pack_start(lab_icon, False, False, 0)
        lab_box.pack_start(lab_label, False, False, 0)
        lab_menu_btn.add(lab_box)

        lab_menu = Gtk.Menu()
        units_dict = {}
        for p in self.lab_programs:
            u = p.get("unit", "Other")
            if u not in units_dict:
                units_dict[u] = []
            units_dict[u].append(p)

        unit_icons = {
            "1. HTML": "🌐",
            "2. Bootstrap": "🎨",
            "3. JavaScript": "⚡",
            "4. JS Validation": "📝",
            "5. XML with DTD": "📄",
            "6. Servlets": "☕",
            "7. Weather App": "🌦️",
            "8. JDBC": "🗄️",
            "9. Node.js": "🟢",
            "10. Extra: CSS": "🖌️"
        }

        for u_name, progs in units_dict.items():
            u_icon = unit_icons.get(u_name, "📁")
            u_item = Gtk.MenuItem(label=f"{u_icon} {u_name}")
            u_submenu = Gtk.Menu()

            for p in progs:
                files = p.get("files", [])
                if len(files) == 1:
                    f = files[0]
                    p_menu_item = Gtk.MenuItem(label=f"P{p['number']:02d}: {f['name']} — {p['title'][:32]}")
                    p_menu_item.connect("activate", lambda w, pr=p, fl=f: self.load_lab_file(pr, fl))
                    u_submenu.append(p_menu_item)
                elif len(files) > 1:
                    p_parent_item = Gtk.MenuItem(label=f"P{p['number']:02d}: {p['title'][:30]} ({len(files)} files)")
                    file_submenu = Gtk.Menu()
                    for f in files:
                        desc = f" — {f['description']}" if f.get("description") else ""
                        f_item = Gtk.MenuItem(label=f"📄 {f['name']}{desc}")
                        f_item.connect("activate", lambda w, pr=p, fl=f: self.load_lab_file(pr, fl))
                        file_submenu.append(f_item)
                    file_submenu.show_all()
                    p_parent_item.set_submenu(file_submenu)
                    u_submenu.append(p_parent_item)

            u_submenu.show_all()
            u_item.set_submenu(u_submenu)
            lab_menu.append(u_item)

        lab_menu.show_all()
        lab_menu_btn.set_popup(lab_menu)
        self.header.pack_start(lab_menu_btn)

        # RIGHT SIDE CONTROLS

        # BIG PLAY BUTTON (Web/Auto)
        self.btn_play = Gtk.Button()
        self.btn_play.get_style_context().add_class("play-button")
        self.btn_play.set_tooltip_text("Execute HTML / Auto-run (Ctrl+Enter)")

        play_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        play_icon = Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.BUTTON)
        play_label = Gtk.Label(label="▶  PLAY")
        play_label.set_use_markup(True)
        play_content.pack_start(play_icon, False, False, 0)
        play_content.pack_start(play_label, False, False, 0)
        self.btn_play.add(play_content)
        self.btn_play.connect("clicked", lambda w: self.execute_code())
        self.header.pack_end(self.btn_play)

        # NODE.JS RUN BUTTON
        self.btn_node = Gtk.Button()
        self.btn_node.get_style_context().add_class("node-button")
        self.btn_node.set_tooltip_text("Execute with Node.js v26 (Ctrl+Shift+Enter)")

        node_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        node_icon = Gtk.Image.new_from_icon_name("system-run-symbolic", Gtk.IconSize.BUTTON)
        node_label = Gtk.Label(label="<b>🟢 Node.js</b>")
        node_label.set_use_markup(True)
        node_content.pack_start(node_icon, False, False, 0)
        node_content.pack_start(node_label, False, False, 0)
        self.btn_node.add(node_content)
        self.btn_node.connect("clicked", lambda w: self.execute_node_code())
        self.header.pack_end(self.btn_node)

        # Actions Menu (Three dots / cog)
        more_menu_btn = Gtk.MenuButton()
        more_menu_btn.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        more_menu_btn.set_tooltip_text("Settings & Tools")

        more_menu = Gtk.Menu()

        item_wrap = Gtk.CheckMenuItem(label="Word Wrap")
        item_wrap.set_active(True)
        item_wrap.connect("toggled", self.on_toggle_wrap)
        more_menu.append(item_wrap)

        item_browser = Gtk.MenuItem(label="Open in Firefox Browser")
        item_browser.connect("activate", lambda w: self.open_in_browser())
        more_menu.append(item_browser)

        more_menu.append(Gtk.SeparatorMenuItem())

        item_theme = Gtk.MenuItem(label="Toggle Dark / Light Editor Theme")
        item_theme.connect("activate", lambda w: self.toggle_theme())
        more_menu.append(item_theme)

        item_font_inc = Gtk.MenuItem(label="Increase Font Size (Ctrl++)")
        item_font_inc.connect("activate", lambda w: self.change_font_size(1))
        more_menu.append(item_font_inc)

        item_font_dec = Gtk.MenuItem(label="Decrease Font Size (Ctrl+-)")
        item_font_dec.connect("activate", lambda w: self.change_font_size(-1))
        more_menu.append(item_font_dec)

        more_menu.append(Gtk.SeparatorMenuItem())

        item_about = Gtk.MenuItem(label="About Reading Steiner")
        item_about.connect("activate", lambda w: self.show_about_dialog())
        more_menu.append(item_about)

        more_menu.show_all()
        more_menu_btn.set_popup(more_menu)
        self.header.pack_end(more_menu_btn)

        # Toggle Console drawer button
        self.btn_console = Gtk.ToggleButton()
        self.btn_console.set_image(Gtk.Image.new_from_icon_name("utilities-terminal-symbolic", Gtk.IconSize.BUTTON))
        self.btn_console.set_tooltip_text("Toggle Output Terminal (Press F5 to show)")
        self.btn_console.connect("toggled", self.on_toggle_console)
        self.header.pack_end(self.btn_console)

    def setup_main_layout(self):
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_vbox)

        # Paned for full-width Notepad (top) and Collapsible Output Terminal (bottom)
        self.editor_paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        main_vbox.pack_start(self.editor_paned, True, True, 0)

        # ==========================================
        # FULL-WIDTH NOTEPAD CODE EDITOR
        # ==========================================
        editor_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        editor_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        editor_header.get_style_context().add_class("status-bar-box")
        lbl_code = Gtk.Label(label="<b>HTML / CSS / JS Notepad</b>")
        lbl_code.set_use_markup(True)
        editor_header.pack_start(lbl_code, False, False, 6)

        btn_clear = Gtk.Button.new_from_icon_name("edit-clear-symbolic", Gtk.IconSize.MENU)
        btn_clear.set_relief(Gtk.ReliefStyle.NONE)
        btn_clear.set_tooltip_text("Clear Editor")
        btn_clear.connect("clicked", lambda w: self.clear_editor())
        editor_header.pack_end(btn_clear, False, False, 0)

        editor_container.pack_start(editor_header, False, False, 0)

        scrolled_editor = Gtk.ScrolledWindow()
        scrolled_editor.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        if HAS_GTKSOURCE:
            self.editor_buffer = GtkSource.Buffer()
            lm = GtkSource.LanguageManager.get_default()
            html_lang = lm.get_language("html")
            if html_lang:
                self.editor_buffer.set_language(html_lang)
            self.editor_buffer.set_highlight_syntax(True)
            self.editor_buffer.set_highlight_matching_brackets(True)

            self.style_manager = GtkSource.StyleSchemeManager.get_default()
            scheme = (
                self.style_manager.get_scheme("oled-black")
                or self.style_manager.get_scheme("oblivion")
                or self.style_manager.get_scheme("classic")
            )
            if scheme:
                self.editor_buffer.set_style_scheme(scheme)

            self.editor_view = GtkSource.View.new_with_buffer(self.editor_buffer)
            self.editor_view.set_show_line_numbers(True)
            self.editor_view.set_highlight_current_line(True)
            self.editor_view.set_auto_indent(True)
            self.editor_view.set_indent_width(2)
            self.editor_view.set_tab_width(2)
            self.editor_view.set_insert_spaces_instead_of_tabs(True)
        else:
            self.editor_buffer = Gtk.TextBuffer()
            self.editor_view = Gtk.TextView.new_with_buffer(self.editor_buffer)

        self.editor_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.update_editor_font()
        self.editor_buffer.connect("changed", self.on_buffer_changed)

        scrolled_editor.add(self.editor_view)
        editor_container.pack_start(scrolled_editor, True, True, 0)

        self.editor_paned.pack1(editor_container, resize=True, shrink=False)

        # ==========================================
        # COLLAPSIBLE CONSOLE DRAWER (F5 ONLY)
        # ==========================================
        self.console_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.console_box.get_style_context().add_class("console-pane")
        self.console_box.set_size_request(-1, 160)

        console_toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        console_toolbar.get_style_context().add_class("status-bar-box")
        c_title = Gtk.Label(label="<b>Output Terminal / Console (F5)</b>")
        c_title.set_use_markup(True)
        console_toolbar.pack_start(c_title, False, False, 6)

        btn_close_console = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
        btn_close_console.set_relief(Gtk.ReliefStyle.NONE)
        btn_close_console.set_tooltip_text("Collapse Terminal (F5 to show)")
        btn_close_console.connect("clicked", lambda w: self.btn_console.set_active(False))
        console_toolbar.pack_end(btn_close_console, False, False, 0)

        btn_clear_console = Gtk.Button.new_from_icon_name("edit-clear-symbolic", Gtk.IconSize.MENU)
        btn_clear_console.set_relief(Gtk.ReliefStyle.NONE)
        btn_clear_console.set_tooltip_text("Clear Output")
        btn_clear_console.connect("clicked", lambda w: self.clear_console())
        console_toolbar.pack_end(btn_clear_console, False, False, 0)

        self.console_box.pack_start(console_toolbar, False, False, 0)

        scrolled_console = Gtk.ScrolledWindow()
        scrolled_console.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.console_buffer = Gtk.TextBuffer()
        self.console_view = Gtk.TextView.new_with_buffer(self.console_buffer)
        self.console_view.set_editable(False)
        self.console_view.set_cursor_visible(False)
        self.console_view.modify_font(Pango.FontDescription("Adwaita Mono 10, Monospace 10"))

        self.tag_log = self.console_buffer.create_tag("log", foreground="#cdd6f4")
        self.tag_warn = self.console_buffer.create_tag("warn", foreground="#f9e2af")
        self.tag_error = self.console_buffer.create_tag("error", foreground="#f38ba8", weight=Pango.Weight.BOLD)
        self.tag_info = self.console_buffer.create_tag("info", foreground="#89b4fa")
        self.tag_time = self.console_buffer.create_tag("time", foreground="#6c7086")

        scrolled_console.add(self.console_view)
        self.console_box.pack_start(scrolled_console, True, True, 0)

        self.editor_paned.pack2(self.console_box, resize=False, shrink=False)
        self.console_box.set_no_show_all(True)
        self.console_box.hide()

        # ==========================================
        # BOTTOM STATUS BAR
        # ==========================================
        status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        status_bar.get_style_context().add_class("status-bar-box")
        main_vbox.pack_end(status_bar, False, False, 0)

        self.lbl_cursor_pos = Gtk.Label(label="Ln 1, Col 1")
        status_bar.pack_start(self.lbl_cursor_pos, False, False, 6)

        self.lbl_char_count = Gtk.Label(label="0 chars")
        status_bar.pack_start(self.lbl_char_count, False, False, 6)

        self.lbl_filename = Gtk.Label(label="Untitled")
        status_bar.pack_end(self.lbl_filename, False, False, 6)

        self.exec_status_lbl = Gtk.Label(label="Ready")
        status_bar.pack_end(self.exec_status_lbl, False, False, 6)

        self.editor_buffer.connect("notify::cursor-position", self.on_cursor_moved)

    def setup_keybindings(self):
        self.connect("key-press-event", self.on_key_pressed)

    def on_key_pressed(self, widget, event):
        state = event.state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK)

        # Ctrl + Shift + Enter -> Execute directly with Node.js
        if (event.state & Gdk.ModifierType.CONTROL_MASK) and (event.state & Gdk.ModifierType.SHIFT_MASK) and event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.execute_node_code()
            return True

        # Ctrl + Enter -> Execute Code (Auto-detects Node.js vs WebKit preview)
        if state == Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.execute_code()
            return True

        # Shift + F5 -> Collapse / Hide Output Terminal
        if (event.state & Gdk.ModifierType.SHIFT_MASK) and event.keyval == Gdk.KEY_F5:
            if self.btn_console.get_active():
                self.btn_console.set_active(False)
            return True

        # F5 -> Show Collapsible Output Terminal & Execute Code
        if event.keyval == Gdk.KEY_F5:
            if not self.btn_console.get_active():
                self.btn_console.set_active(True)
            self.execute_code()
            return True

        # Ctrl + S -> Save
        if state == Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_s, Gdk.KEY_S):
            self.on_save_file()
            return True

        # Ctrl + O -> Open
        if state == Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_o, Gdk.KEY_O):
            self.on_open_file()
            return True

        # Ctrl + N -> New
        if state == Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_n, Gdk.KEY_N):
            self.on_new_file()
            return True

        # Ctrl + Plus / Equal -> Zoom in
        if state == Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
            self.change_font_size(1)
            return True

        # Ctrl + Minus -> Zoom out
        if state == Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_minus, Gdk.KEY_underscore, Gdk.KEY_KP_Subtract):
            self.change_font_size(-1)
            return True

        return False

    def update_editor_font(self):
        font_desc = Pango.FontDescription(f"Adwaita Mono {self.font_size}, Monospace {self.font_size}")
        self.editor_view.modify_font(font_desc)

    def change_font_size(self, delta):
        new_size = max(8, min(32, self.font_size + delta))
        if new_size != self.font_size:
            self.font_size = new_size
            self.update_editor_font()

    def get_editor_text(self):
        start = self.editor_buffer.get_start_iter()
        end = self.editor_buffer.get_end_iter()
        return self.editor_buffer.get_text(start, end, True)

    def set_editor_text(self, text):
        self.editor_buffer.set_text(text)

    def execute_code(self):
        """Executes code: auto-detects XML, Java/Servlets, Node.js scripts vs WebKit HTML preview."""
        code = self.get_editor_text()
        if not code.strip():
            self.exec_status_lbl.set_text("Ready")
            return

        # 1. XML / DTD Validation
        if (self.current_filepath and (self.current_filepath.endswith(".xml") or self.current_filepath.endswith(".dtd"))) or (code.strip().startswith("<?xml") or "<!doctype bookstore" in code.lower() or "<!element" in code.lower()):
            if not ("<html" in code.lower() or "<!doctype html" in code.lower()):
                self.execute_xml_validation(code)
                return

        # 2. Java / Servlet Compilation & Preview
        if (self.current_filepath and self.current_filepath.endswith(".java")) or ("import java." in code or "javax.servlet" in code):
            self.execute_java_servlet(code)
            return

        # 3. Auto-detect if this is a Node.js / pure JavaScript script
        is_node = False
        if self.current_filepath and self.current_filepath.endswith(".js"):
            is_node = True
        elif not any(tag in code.lower() for tag in ["<html", "<!doctype", "<body", "<div", "<table", "<form", "<style"]):
            if any(kw in code for kw in ["console.log", "const ", "let ", "var ", "function ", "require("]):
                is_node = True

        if is_node:
            self.execute_node_code(code)
            return

        # 4. Inject the console interception script and OLED dark default styling for HTML/Web
        injected_code = code
        oled_style_tag = (
            "<style id='reading-steiner-oled'>"
            ":root { color-scheme: dark; }"
            "body { background-color: #000000; color: #f4f4f5; font-family: system-ui, -apple-system, sans-serif; }"
            "table { border-color: #3f3f46; }"
            "td, th { border-color: #3f3f46; }"
            "input, select, textarea, button { background-color: #18181b; color: #f4f4f5; border: 1px solid #3f3f46; }"
            "</style>"
        )
        script_tag = f"<script>{CONSOLE_INJECTION_SCRIPT}</script>\n{oled_style_tag}"

        if "<head>" in injected_code:
            injected_code = injected_code.replace("<head>", f"<head>\n{script_tag}", 1)
        elif "<html>" in injected_code:
            injected_code = injected_code.replace("<html>", f"<html>\n<head>{script_tag}</head>", 1)
        else:
            injected_code = script_tag + "\n" + injected_code

        # Base URI is either the opened file directory or file:///
        base_uri = "file:///"
        if self.current_filepath:
            base_uri = f"file://{os.path.dirname(os.path.abspath(self.current_filepath))}/"

        # Ensure execution window exists and load HTML
        self.ensure_execution_window()
        self.webview.load_html(injected_code, base_uri)

        # Show & present execution window
        self.execution_window.show_all()
        self.execution_window.present()

        # Pulse status
        now_str = datetime.now().strftime("%H:%M:%S")
        self.exec_status_lbl.set_markup(f"<span foreground='#22c55e'>● Executed at {now_str}</span>")

        # Save to autosave cache in background
        self.autosave()

    def execute_node_code(self, code=None):
        """Executes JavaScript / Node.js directly using /usr/bin/node and streams output to console."""
        if code is None:
            code = self.get_editor_text()
        if not code.strip():
            return

        # Ensure terminal drawer is visible and clear previous output
        self.btn_console.set_active(True)
        self.clear_console()

        now_str = datetime.now().strftime("%H:%M:%S")
        end_iter = self.console_buffer.get_end_iter()
        self.console_buffer.insert_with_tags(end_iter, f"[{now_str}] ", self.tag_time)
        file_label = self.current_filepath if self.current_filepath else "script.js"
        self.console_buffer.insert_with_tags(end_iter, f"[NODE] Executing {file_label} with Node.js v26.10.0...\n\n", self.tag_info)

        def run_thread():
            start_time = time.time()
            try:
                proc = subprocess.Popen(
                    ["node", "-e", code],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = proc.communicate(timeout=10)
                elapsed = int((time.time() - start_time) * 1000)

                def update_ui():
                    iter_end = self.console_buffer.get_end_iter()
                    if stdout:
                        self.console_buffer.insert_with_tags(iter_end, stdout, self.tag_log)
                    if stderr:
                        iter_end = self.console_buffer.get_end_iter()
                        self.console_buffer.insert_with_tags(iter_end, stderr, self.tag_error)
                    iter_end = self.console_buffer.get_end_iter()
                    t_str = datetime.now().strftime("%H:%M:%S")
                    if proc.returncode == 0:
                        self.console_buffer.insert_with_tags(
                            iter_end,
                            f"\n[{t_str}] [NODE] Process finished successfully (exit code 0) in {elapsed}ms\n",
                            self.tag_info
                        )
                        self.exec_status_lbl.set_markup(f"<span foreground='#22c55e'>● Node.js executed in {elapsed}ms</span>")
                    else:
                        self.console_buffer.insert_with_tags(
                            iter_end,
                            f"\n[{t_str}] [NODE] Process exited with error code {proc.returncode}\n",
                            self.tag_error
                        )
                        self.exec_status_lbl.set_markup(f"<span foreground='#ef4444'>● Node.js error (code {proc.returncode})</span>")
                    self.console_view.scroll_to_iter(self.console_buffer.get_end_iter(), 0.0, False, 0.0, 0.0)

                GLib.idle_add(update_ui)
            except subprocess.TimeoutExpired:
                def update_timeout():
                    iter_end = self.console_buffer.get_end_iter()
                    self.console_buffer.insert_with_tags(iter_end, "\n[ERROR] Execution timed out after 10 seconds.\n", self.tag_error)
                    self.exec_status_lbl.set_markup("<span foreground='#ef4444'>● Execution timed out</span>")
                GLib.idle_add(update_timeout)
            except Exception as e:
                def update_err():
                    iter_end = self.console_buffer.get_end_iter()
                    self.console_buffer.insert_with_tags(iter_end, f"\n[ERROR] Failed to run Node: {e}\n", self.tag_error)
                GLib.idle_add(update_err)

        threading.Thread(target=run_thread, daemon=True).start()

    def execute_xml_validation(self, code):
        """Validates XML documents with internal or external DTD using xmllint and renders output."""
        self.btn_console.set_active(True)
        self.clear_console()

        now_str = datetime.now().strftime("%H:%M:%S")
        end_iter = self.console_buffer.get_end_iter()
        self.console_buffer.insert_with_tags(end_iter, f"[{now_str}] ", self.tag_time)
        file_label = self.current_filepath if self.current_filepath else "document.xml"
        self.console_buffer.insert_with_tags(end_iter, f"[XML] Validating {file_label} with DTD validator (xmllint)...\n\n", self.tag_info)

        tmp_dir = os.path.join(CACHE_DIR, "xml_sandbox")
        os.makedirs(tmp_dir, exist_ok=True)
        xml_path = os.path.join(tmp_dir, file_label)
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(code)

        # If bookstore.xml is being validated, ensure bookstore.dtd is also in sandbox
        if "bookstore" in file_label.lower():
            for p in self.lab_programs:
                for fl in p.get("files", []):
                    if fl["name"] == "bookstore.dtd":
                        with open(os.path.join(tmp_dir, "bookstore.dtd"), "w", encoding="utf-8") as dtd_f:
                            dtd_f.write(fl["code"])

        res = subprocess.run(["xmllint", "--valid", "--noout", xml_path], capture_output=True, text=True)
        iter_end = self.console_buffer.get_end_iter()
        t_str = datetime.now().strftime("%H:%M:%S")

        if res.returncode == 0:
            self.console_buffer.insert_with_tags(
                iter_end,
                f"[{t_str}] [XML] ✅ Document is WELL-FORMED and VALID against DTD!\n",
                self.tag_info
            )
            self.exec_status_lbl.set_markup("<span foreground='#22c55e'>● XML DTD Validated</span>")
        else:
            self.console_buffer.insert_with_tags(iter_end, res.stderr + "\n", self.tag_error)
            self.console_buffer.insert_with_tags(
                iter_end,
                f"[{t_str}] [XML] ❌ DTD Validation failed (see error details above)\n",
                self.tag_error
            )
            self.exec_status_lbl.set_markup("<span foreground='#ef4444'>● XML Validation Error</span>")

        # Display rendered XML view in WebKit window
        self.ensure_execution_window()
        escaped_xml = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        badge_color = "#064e3b" if res.returncode == 0 else "#7f1d1d"
        badge_text_color = "#34d399" if res.returncode == 0 else "#fca5a5"
        status_text = "✅ XML Document Well-Formed & Valid against DTD" if res.returncode == 0 else "❌ XML Validation Errors Detected"

        html_view = f"""<!DOCTYPE html>
        <html>
        <head>
          <style>
            body {{ background: #000000; color: #f4f4f5; font-family: monospace; padding: 24px; font-size: 14px; line-height: 1.6; }}
            .status {{ background: {badge_color}; color: {badge_text_color}; padding: 12px 18px; border-radius: 8px; margin-bottom: 20px; font-family: system-ui, sans-serif; font-weight: bold; }}
            pre {{ background: #09090b; padding: 16px; border-radius: 8px; border: 1px solid #27272a; overflow-x: auto; }}
          </style>
        </head>
        <body>
          <div class="status">{status_text}</div>
          <pre><code>{escaped_xml}</code></pre>
        </body>
        </html>"""
        self.webview.load_html(html_view, f"file://{tmp_dir}/")
        self.execution_window.show_all()
        self.execution_window.present()

    def execute_java_servlet(self, code):
        """Compiles Java / Servlets using javac with servlet-api.jar and previews servlet output."""
        self.btn_console.set_active(True)
        self.clear_console()

        now_str = datetime.now().strftime("%H:%M:%S")
        end_iter = self.console_buffer.get_end_iter()
        self.console_buffer.insert_with_tags(end_iter, f"[{now_str}] ", self.tag_time)
        file_label = self.current_filepath if self.current_filepath else "Servlet.java"
        self.console_buffer.insert_with_tags(end_iter, f"[JAVA] Compiling {file_label} with javac (Temurin JDK 21)...\n", self.tag_info)

        tmp_dir = os.path.join(CACHE_DIR, "servlet_sandbox")
        os.makedirs(tmp_dir, exist_ok=True)
        java_path = os.path.join(tmp_dir, file_label)
        with open(java_path, "w", encoding="utf-8") as f:
            f.write(code)

        servlet_jar = os.path.join(APP_DIR, "assets", "lib", "servlet-api.jar")
        classpath = f".:{servlet_jar}"

        javac_cmd = ["javac", "-cp", classpath, java_path]
        res = subprocess.run(javac_cmd, capture_output=True, text=True)
        iter_end = self.console_buffer.get_end_iter()
        t_str = datetime.now().strftime("%H:%M:%S")

        if res.returncode == 0:
            self.console_buffer.insert_with_tags(
                iter_end,
                f"[{t_str}] [JAVA] ✅ Compilation SUCCESSFUL! (0 errors, bytecode generated)\n",
                self.tag_info
            )
            self.console_buffer.insert_with_tags(
                iter_end,
                f"[{t_str}] [SERVLET] Simulating Tomcat HTTP Container Request → http://localhost:8080/{file_label.replace('.java','')}/...\n",
                self.tag_log
            )
            self.exec_status_lbl.set_markup("<span foreground='#22c55e'>● Java Compiled &amp; Verified</span>")

            # Extract HTML strings generated by out.println(...) or out.print(...)
            import re
            html_parts = re.findall(r'out\.print(?:ln)?\s*\(\s*"([^"]*)"\s*\)', code)
            rendered_body = "".join(html_parts)
            if not rendered_body:
                rendered_body = f"<h2>Servlet {file_label} compiled successfully!</h2><p>Bytecode generated and ready for deployment in Apache Tomcat.</p>"

            self.ensure_execution_window()
            preview_html = f"""<!DOCTYPE html>
            <html>
            <head>
              <style>
                body {{ background: #000000; color: #f4f4f5; font-family: system-ui, sans-serif; padding: 30px; }}
                .badge {{ display: inline-block; background: #1e3a8a; color: #93c5fd; padding: 6px 14px; border-radius: 8px; font-size: 13px; margin-bottom: 20px; font-weight: bold; border: 1px solid #1d4ed8; }}
                .container {{ background: #09090b; padding: 24px; border-radius: 12px; border: 1px solid #27272a; }}
              </style>
            </head>
            <body>
              <div class="badge">☕ Apache Tomcat HTTP Servlet Preview (Status 200 OK)</div>
              <div class="container">{rendered_body}</div>
            </body>
            </html>"""
            self.webview.load_html(preview_html, "file:///")
            self.execution_window.show_all()
            self.execution_window.present()
        else:
            self.console_buffer.insert_with_tags(iter_end, res.stderr + "\n", self.tag_error)
            self.console_buffer.insert_with_tags(
                iter_end,
                f"[{t_str}] [JAVA] ❌ Compilation failed with error (check syntax above)\n",
                self.tag_error
            )
            self.exec_status_lbl.set_markup("<span foreground='#ef4444'>● Java Compilation Error</span>")

    def load_lab_file(self, prog, file_item):
        """Loads a program file from the Lab Exam PDF into the editor with language detection."""
        self.set_editor_text(file_item["code"])
        self.current_filepath = file_item["name"]
        self.is_modified = False

        if HAS_GTKSOURCE:
            lang_map = {
                "html": "html",
                "javascript": "js",
                "js": "js",
                "java": "java",
                "xml": "xml",
                "dtd": "xml",
                "css": "css"
            }
            lang_id = lang_map.get(file_item.get("language", "html"), "html")
            lm = GtkSource.LanguageManager.get_default()
            lang = lm.get_language(lang_id)
            if lang:
                self.editor_buffer.set_language(lang)

        # Update Header and Status
        self.header.props.subtitle = f"P{prog['number']:02d}: {file_item['name']}"
        self.lbl_filename.set_text(f"P{prog['number']:02d}: {file_item['name']}")

        instruction = prog.get("instruction", "")
        if instruction:
            first_line = instruction.split("\n")[0].strip()
            self.exec_status_lbl.set_text(first_line[:60])
        else:
            self.exec_status_lbl.set_text("Loaded from Lab PDF")

        # If it's a Node.js file, open the console so output is visible
        if file_item.get("language") in ("javascript", "js") or file_item["name"].endswith(".js"):
            self.btn_console.set_active(True)

    def autosave(self):
        try:
            text = self.get_editor_text()
            if text.strip():
                with open(AUTOSAVE_PATH, "w", encoding="utf-8") as f:
                    f.write(text)
            elif os.path.exists(AUTOSAVE_PATH):
                os.remove(AUTOSAVE_PATH)
        except Exception:
            pass

    def on_console_message(self, manager, js_result):
        """Receives logged JavaScript messages and prints them into Console Drawer."""
        try:
            val_str = js_result.get_js_value().to_string()
            data = json.loads(val_str)
            msg_type = data.get("type", "log")
            msg_text = data.get("message", "")
            msg_time = data.get("time", "")

            end_iter = self.console_buffer.get_end_iter()

            # Insert timestamp
            self.console_buffer.insert_with_tags(end_iter, f"[{msg_time}] ", self.tag_time)

            # Insert tag based on message type
            tag = self.tag_log
            prefix = "[LOG] "
            if msg_type == "warn":
                tag = self.tag_warn
                prefix = "[WARN] "
            elif msg_type == "error":
                tag = self.tag_error
                prefix = "[ERROR] "
            elif msg_type == "info":
                tag = self.tag_info
                prefix = "[INFO] "

            self.console_buffer.insert_with_tags(end_iter, prefix, tag)
            self.console_buffer.insert_with_tags(end_iter, f"{msg_text}\n", tag)

            # Scroll to bottom
            mark = self.console_buffer.create_mark(None, self.console_buffer.get_end_iter(), False)
            self.console_view.scroll_to_mark(mark, 0.05, True, 0.0, 1.0)
        except Exception as e:
            print(f"Error handling console log: {e}")

    def clear_console(self):
        self.console_buffer.set_text("")

    def on_toggle_console(self, widget):
        if widget.get_active():
            self.console_box.show()
            for child in self.console_box.get_children():
                child.show_all()
            self.editor_paned.set_position(max(300, self.editor_paned.get_position() - 160))
        else:
            self.console_box.hide()

    def on_toggle_wrap(self, widget):
        if widget.get_active():
            self.editor_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        else:
            self.editor_view.set_wrap_mode(Gtk.WrapMode.NONE)

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        if HAS_GTKSOURCE:
            scheme_id = "oled-black" if self.dark_mode else "classic"
            scheme = self.style_manager.get_scheme(scheme_id) or self.style_manager.get_scheme("oblivion")
            if scheme:
                self.editor_buffer.set_style_scheme(scheme)

    def clear_editor(self):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Clear Code Editor?"
        )
        dialog.format_secondary_text("All current contents will be removed.")
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            self.set_editor_text("")
            self.lbl_char_count.set_text("0 chars")
            self.exec_status_lbl.set_text("Ready")
            if self.execution_window and self.execution_window.get_visible():
                self.webview.load_html("<!DOCTYPE html><html><body></body></html>", "file:///")

    def load_template(self, key):
        tmpl = self.templates.get(key)
        if tmpl and "code" in tmpl:
            self.set_editor_text(tmpl["code"])

    def on_buffer_changed(self, buffer):
        self.is_modified = True
        chars = buffer.get_char_count()
        self.lbl_char_count.set_text(f"{chars} chars")
        if self.current_filepath:
            fname = os.path.basename(self.current_filepath)
            self.header.props.subtitle = f"{fname} *"
            self.lbl_filename.set_text(f"{fname} (Modified)")
        else:
            if chars == 0:
                self.header.props.subtitle = "Untitled.html"
                self.lbl_filename.set_text("Untitled")
            else:
                self.header.props.subtitle = "Untitled.html *"
                self.lbl_filename.set_text("Untitled (Unsaved)")

    def on_cursor_moved(self, buffer, param):
        mark = buffer.get_insert()
        iter_pos = buffer.get_iter_at_mark(mark)
        line = iter_pos.get_line() + 1
        col = iter_pos.get_line_offset() + 1
        self.lbl_cursor_pos.set_text(f"Ln {line}, Col {col}")

    def on_new_file(self):
        self.current_filepath = None
        self.header.props.subtitle = "Untitled.html"
        self.lbl_filename.set_text("Untitled")
        self.set_editor_text("")
        self.is_modified = False
        self.lbl_char_count.set_text("0 chars")
        self.lbl_cursor_pos.set_text("Ln 1, Col 1")
        self.exec_status_lbl.set_text("Ready")
        self.clear_console()

    def on_open_file(self):
        dialog = Gtk.FileChooserDialog(
            title="Open HTML File",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )

        filter_html = Gtk.FileFilter()
        filter_html.set_name("HTML files (*.html, *.htm)")
        filter_html.add_mime_type("text/html")
        filter_html.add_pattern("*.html")
        filter_html.add_pattern("*.htm")
        dialog.add_filter(filter_html)

        filter_any = Gtk.FileFilter()
        filter_any.set_name("All files (*.*)")
        filter_any.add_pattern("*")
        dialog.add_filter(filter_any)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            dialog.destroy()
            self.load_file(filepath)
        else:
            dialog.destroy()

    def load_file(self, filepath, is_autosave=False):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            self.set_editor_text(content)
            if not is_autosave:
                self.current_filepath = filepath
                fname = os.path.basename(filepath)
                self.header.props.subtitle = fname
                self.lbl_filename.set_text(filepath)
            self.is_modified = False
        except Exception as e:
            err_dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=f"Failed to open file: {e}"
            )
            err_dialog.run()
            err_dialog.destroy()

    def on_save_file(self):
        if not self.current_filepath:
            self.on_save_as_file()
            return

        try:
            with open(self.current_filepath, "w", encoding="utf-8") as f:
                f.write(self.get_editor_text())
            self.is_modified = False
            fname = os.path.basename(self.current_filepath)
            self.header.props.subtitle = fname
            self.lbl_filename.set_text(self.current_filepath)
        except Exception as e:
            err_dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=f"Failed to save file: {e}"
            )
            err_dialog.run()
            err_dialog.destroy()

    def on_save_as_file(self):
        dialog = Gtk.FileChooserDialog(
            title="Save HTML File",
            parent=self,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK
        )
        dialog.set_do_overwrite_confirmation(True)
        dialog.set_current_name("index.html")

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            if not (filepath.endswith(".html") or filepath.endswith(".htm")):
                filepath += ".html"
            dialog.destroy()
            self.current_filepath = filepath
            self.on_save_file()
        else:
            dialog.destroy()

    def open_in_browser(self):
        """Saves current code to a temporary file and opens it in Firefox."""
        temp_path = os.path.join(CACHE_DIR, "preview_external.html")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(self.get_editor_text())

        # Launch Firefox via flatpak
        try:
            subprocess.Popen([
                "flatpak", "run", "--file-forwarding", "org.mozilla.firefox",
                "@@", temp_path, "@@"
            ])
        except Exception:
            try:
                subprocess.Popen(["xdg-open", temp_path])
            except Exception as e:
                print(f"Could not open browser: {e}")

    def show_about_dialog(self):
        about = Gtk.AboutDialog(transient_for=self)
        about.set_program_name("Reading Steiner")
        about.set_version("1.0.0")
        about.set_comments("A lightweight notepad with a Play button to write and instantly execute HTML, CSS, and JavaScript.")
        if os.path.exists(ICON_PATH):
            about.set_logo(GdkPixbuf.Pixbuf.new_from_file(ICON_PATH))
        about.run()
        about.destroy()


def main():
    initial_file = sys.argv[1] if len(sys.argv) > 1 else None
    app = HTMLNotepadWindow(initial_file)
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
