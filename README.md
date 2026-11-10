# Reading Steiner (Live HTML Execution Engine)

An interactive HTML notepad with a dedicated **▶ PLAY** button to immediately execute and preview your HTML, CSS, and JavaScript across world lines.

---

## ✨ Features

- **Pure Full-Width Notepad**: No embedded side-by-side preview cluttering your workspace. The editor occupies the full window.
- **▶ Big Play Button (Execution Window)**:
  - Click **PLAY** (or press `Ctrl + Enter` / `F5`) to execute your HTML, CSS & JavaScript in a dedicated **Execution Window**.
  - If the Execution Window is already open, clicking Play updates the running page instantly.
  - Press `Escape` or `Ctrl + W` in the Execution Window to close it.
- **Collapsible Output Terminal (F5)**:
  - Hidden / collapsed by default at the bottom of the notepad.
  - **Press `F5`** to execute your code and reveal the output terminal drawer.
  - Collapse the terminal anytime with `Shift + F5` or the `✕` close button.
- **Clean Slate**: New documents start completely empty (**0 text default**), giving you a blank canvas immediately.
- **Starter Templates (Optional)**:
  - If you need boilerplate or inspiration, click **Templates** in the top bar:
    - ✨ *Welcome & Counter Demo* (Interactive state + CSS card)
    - 📄 *Blank HTML5 Skeleton*
    - 🎮 *Canvas Particle Animation* (High-performance 60fps physics)
    - 📝 *Interactive Task Manager* (Functional Todo list)
- **Editor Conveniences**:
  - Line numbers and syntax highlighting
  - Tab key support (inserts 2 spaces, does not drop focus)
  - Adjustable font size (`Ctrl + +` / `Ctrl + -`)
  - Word wrap toggle
  - Dark / Light mode toggle
  - Auto-save session restore (drafts are preserved across app restarts)
- **Desktop Integration**:
  - Desktop shortcut on your Linux Desktop: `~/Desktop/Reading-Steiner.desktop`
  - System application menu integration: `~/.local/share/applications/reading-steiner.desktop`

---

## 🚀 How to Launch

### Option 1: Double-Click the Desktop Icon
Simply double-click **Reading Steiner** on your Desktop.

### Option 2: Run from Terminal
```bash
/home/orsted/Projects/html-notepad/run.sh
```
Or via the `reading-steiner` shortcut:
```bash
/home/orsted/Projects/reading-steiner/run.sh
```
Or open a specific file directly:
```bash
/home/orsted/Projects/html-notepad/run.sh /path/to/my_page.html
```

### Option 3: Launch the Web Version in Firefox
```bash
flatpak run --file-forwarding org.mozilla.firefox @@ /home/orsted/Projects/html-notepad/web/index.html @@
```
Or open `/home/orsted/Projects/html-notepad/web/index.html` in any browser.

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| **`Ctrl + Enter`** | **▶ PLAY / Execute Code** (Preview only) |
| **`F5`** | **▶ PLAY & Show Output Terminal** |
| **`Shift + F5`** | Collapse / Hide Output Terminal |
| **`Ctrl + S`** | Save File |
| **`Ctrl + O`** | Open File |
| **`Ctrl + N`** | New Blank Document |
| **`Ctrl + +`** | Increase Code Font Size |
| **`Ctrl + -`** | Decrease Code Font Size |
| **`Tab`** | Indent with 2 Spaces |
| **`Ctrl + F`** | Search text in editor |

---

## 👥 Contributors

- **Rishi Koushik** ([@Rishi-Koushik](https://github.com/Rishi-Koushik)) - Creator & Lead Developer
- **Antigravity** ([Google DeepMind](https://deepmind.google/)) - AI Contributor
- **Claude** ([Anthropic](https://anthropic.com/)) - AI Contributor

See [CONTRIBUTORS.md](CONTRIBUTORS.md) for full contributor details.

