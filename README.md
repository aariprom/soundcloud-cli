# 🎵 SoundCloud CLI (`sc-cli`)

> **Cyberpunk aesthetics. Infinite vibes. Terminal-based mastery.**

A powerful, keyboard-centric music player for SoundCloud that lives in your terminal. Featuring high-fidelity RGB block art, infinite station mode, and a robust REPL interface.

## ✨ Features

*   **🎧 Infinite Station Mode**: Type `station <genre/artist>` and let the vibes flow forever.
*   **🖼️ RGB Block Art**: View album covers in your terminal as stunning TrueColor block art.
*   **⌨️ REPL Interface**: Smooth, auto-completing command line with `prompt_toolkit`.
*   **🚀 Fast Startup**: Caches authentication for instant load times.
*   **📜 Playlist Management**: Save your queue, load favorites, and manage your library locally.
*   **⚙️ Configurable**: Customize your experience via `config` commands.

## 🛠️ Prerequisites

*   **Python**: 3.10 or higher.
*   **MPV**: The underlying audio engine.
    *   *Linux (Ubuntu/Debian)*: `sudo apt install mpv`
    *   *MacOS*: `brew install mpv`
    *   *Windows*: `scoop install mpv` (or standard installer)
*   **UV**: The blazing fast Python package manager (Recommended).

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/aariprom/soundcloud-cli.git
cd soundcloud-cli

# Install dependencies and sync environment
uv sync

# Run the application
uv run sc-cli
```

## 🎮 Usage

Once inside the `sc-cli` shell, use these commands:

### Basic Controls
*   `search <query>`: Find tracks (e.g., `search lo-fi`).
*   `play <#>` or `play id:<ID>`: Play result number `#` or specific ID.
*   `pause`: Toggle playback.
*   `next` / `prev`: Skip tracks.
*   `queue <#>`: Add a track to the queue.

### Station Mode
*   `station <query>`: Clear queue and start an infinite radio based on the query.
    *   *Example*: `station synthwave`

### Visuals & Info
*   `info`: Show track metadata and **RGB Album Art**.
*   `status`: Show current playback status.
*   `clear`: Wipe the terminal screen.

### Playlists & Favorites
*   `fave <#>`: Add to favorites.
*   `save <name>`: Save current queue as a playlist.
*   `load <name>`: Load a playlist.
*   `playlists`: List all saved playlists.

### Configuration
*   `config list`: View all settings.
*   `config set ascii_art_width <40-100>`: Adjust art size (default: 60).
*   `config set ascii_enabled <true/false>`: Toggle art.
*   `config set client_id <ID>`: Manually update API key.

## ⌨️ Shortcuts
*   `Ctrl+D`: Exit.
*   `Ctrl+C`: Clear line / Cancel current input.

## 🤝 Contributing
Built with `rich`, `python-mpv`, and `prompt_toolkit`. PRs welcome!

---
*Built with ❤️ by User & Antigravity*
