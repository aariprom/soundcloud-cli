import shlex
import threading
import io
import html
import os
from typing import List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.formatted_text import HTML, ANSI

from sc_cli.core.client import SoundCloudClient
from sc_cli.core.player import Player, RepeatMode
from sc_cli.core.database import Database
from sc_cli.core.config import ConfigManager
from sc_cli.core.ascii_art import generate_ascii_from_url

console = Console(width=120)


LOGO = r"""
[bold cyan]
   _____                       _  _____ _                 _ 
  / ____|                     | |/ ____| |               | |
 | (___   ___  _   _ _ __   __| | |    | | ___  _   _  __| |
  \___ \ / _ \| | | | '_ \ / _` | |    | |/ _ \| | | |/ _` |
  ____) | (_) | |_| | | | | (_| | |____| | (_) | |_| | (_| |
 |_____/ \___/ \__,_|_| |_|\__,_|\_____|_|\___/ \__,_|\__,_|
[/bold cyan][dim]
           >_ CLI Music Player for Soundcloud
[/dim]
"""


class REPL:
    def __init__(self):
        self.config = ConfigManager()

        # Check config for client_id, allows manual override
        cid = self.config.get("client_id")
        self.client = SoundCloudClient(client_id=cid)

        # If client fetched a new ID (automatic), update config
        if self.client.client_id != cid:
            self.config.set("client_id", self.client.client_id)

        self.player = Player(on_finished_callback=self.on_track_finished)
        self.db = Database()
        self.running = True
        self.last_search_results: List[dict] = []
        self.session = PromptSession(
            bottom_toolbar=self._get_bottom_toolbar, refresh_interval=0.5
        )
        # Refresh interval enables auto-updating the toolbar (polling)

        # Station Mode State
        self.station_mode = False
        self.station_query = ""
        self.station_next_href = None
        self.seen_track_ids = set()
        self.fetching_station = False

    def print_rich(self, renderable):
        """Helper to print Rich objects using prompt_toolkit's ANSI renderer for safe async output."""
        f = io.StringIO()
        # Force terminal to ensure ANSI codes are generated
        c = Console(file=f, force_terminal=True, width=120)
        c.print(renderable)
        print_formatted_text(ANSI(f.getvalue()), end="")

    def start(self):
        self.print_rich(LOGO)
        self.print_rich("Type 'help' for commands.")

        with patch_stdout():
            # We don't need re-bind global console as print_rich handles it properly now

            while self.running:
                try:
                    # use prompt_toolkit prompt
                    # We can use HTML for coloring prompt if needed, but simple string works.
                    # sc-cli:
                    # Using list of (style, text) tuples for robustness
                    user_input = self.session.prompt(
                        [("fg:cyan bold", "sc-cli"), ("", ": ")]
                    )

                    if not user_input.strip():
                        continue

                    parts = shlex.split(user_input)
                    cmd = parts[0].lower()
                    args = parts[1:]

                    if cmd in ["exit", "quit", "q"]:
                        self.stop()
                        break
                    elif cmd == "help":
                        self.show_help()
                    elif cmd == "search":
                        self.search(" ".join(args))
                    elif cmd == "station":
                        if args:
                            self.start_station(" ".join(args))
                        else:
                            self.print_rich("Usage: station <query>")
                    elif cmd == "play":
                        if not args:
                            # If queue exists but nothing playing, start it.
                            if self.player.queue and self.player.current_index == -1:
                                self.print_rich("Starting queue...")
                                self.next_track()  # Start first track
                            else:
                                self.player.play()
                                self.print_rich("Resumed.")
                        else:
                            self.play_track(args[0])
                    elif cmd == "pause":
                        self.player.toggle_pause()
                        self.print_rich("Toggled pause.")
                    elif cmd == "stop":
                        self.player.stop()
                        self.print_rich("Stopped.")
                    elif cmd == "queue":
                        if args:
                            self.queue_track(args[0])
                        else:
                            self.show_queue()
                    elif cmd == "unqueue":
                        if args and args[0].isdigit():
                            self.unqueue_track(int(args[0]))
                        else:
                            self.print_rich("Usage: unqueue <index>")
                    elif cmd in ["next", "n"]:
                        self.next_track()
                    elif cmd in ["prev", "p"]:
                        self.prev_track()
                    elif cmd == "status":
                        self.show_status()
                    elif cmd in ["fave", "fav"]:
                        if args:
                            self.add_favorite(args[0])
                        else:
                            self.print_rich("Usage: fave <id/index>")
                    elif cmd == "unfave":
                        if args:
                            self.remove_favorite(args[0])
                        else:
                            self.print_rich("Usage: unfave <id/index>")
                    elif cmd in ["favorites", "favs"]:
                        self.show_favorites()
                    elif cmd == "save":
                        if args:
                            self.save_queue_as_playlist(args[0])
                        else:
                            self.print_rich("Usage: save <name>")
                    elif cmd == "load":
                        if args:
                            self.load_playlist(args[0])
                        else:
                            self.print_rich("Usage: load <name>")
                    elif cmd == "playlists":
                        self.show_playlists()
                        self.print_rich(
                            "[dim]You can view a playlist by typing 'view <playlist_name>'.[/dim]"
                        )
                    elif cmd == "shuffle":
                        self.player.shuffle_queue()
                        self.print_rich("Queue shuffled.")
                    elif cmd == "clear":
                        os.system("clear")
                    elif cmd == "config":
                        if not args:
                            self.print_rich(self.config.list())
                        else:
                            sub = args[0]
                            if sub == "list":
                                self.print_rich(self.config.list())
                            elif sub == "get" and len(args) > 1:
                                val = self.config.get(args[1])
                                self.print_rich(f"{args[1]} = {val}")
                            elif sub == "set" and len(args) > 2:
                                key = args[1]
                                val = args[2]
                                self.config.set(key, val)
                                self.print_rich(f"Set {key} = {val}")
                                # Special handling for client_id
                                if key == "client_id":
                                    self.client.client_id = val
                                    self.client._save_client_id(
                                        val
                                    )  # Update legacy file too
                            else:
                                self.print_rich(
                                    "Usage: config <list|get|set> [key] [value]"
                                )
                    elif cmd == "repeat":
                        if args:
                            self.set_repeat(args[0])
                        else:
                            self.print_rich(
                                f"Current Repeat Mode: {self.player.repeat_mode.name}"
                            )
                    elif cmd == "info":
                        self.show_info()
                    elif cmd == "view":
                        if args:
                            self.view_playlist(args[0])
                        else:
                            self.print_rich("Usage: view <playlist_name>")
                    elif cmd == "seek":
                        if args:
                            try:
                                val = args[0]
                                if "%" in val:
                                    self.player.seek(float(val.replace("%", "")))
                                else:
                                    self.player.seek(float(val))
                            except Exception as e:
                                self.print_rich(f"Error seeking: {e}")
                        else:
                            self.print_rich("Usage: seek <seconds>")
                    else:
                        self.print_rich(f"[red]Unknown command: {cmd}[/red]")

                except KeyboardInterrupt:
                    # In prompt_toolkit, Ctrl+C raises KeyboardInterrupt.
                    # We might just want to clear line or exit?
                    # Usually just continue.
                    self.print_rich("[dim]Type 'exit' or 'quit' to quit.[/dim]")
                    continue
                except EOFError:
                    # Ctrl+D
                    self.stop()
                    break
                except Exception as e:
                    self.print_rich(f"[red]Error: {e}[/red]")

    def stop(self):
        self.player.stop()
        self.running = False
        self.print_rich("Turning off...")

    def show_help(self):
        table = Table(title="Commands")
        table.add_column("Command", style="cyan")
        table.add_column("Description")
        table.add_row("search <query>", "Search for tracks.")
        table.add_row(
            "station <query>", "Start an infinite radio station based on query."
        )
        table.add_row(
            "play <id|num> / play id:<id>",
            "Play a track (clears queue). Num refers to search result.",
        )
        table.add_row("queue <id|num>", "Add a track to the queue.")
        table.add_row("unqueue <index>", "Remove track from queue by index #.")
        table.add_row("fave <id|num>", "Save track to favorites.")
        table.add_row("favorites", "List favorites.")
        table.add_row("save <name>", "Save current queue as a playlist.")
        table.add_row("playlists", "List saved playlists.")
        table.add_row("load <name>", "Load a playlist into the queue.")
        table.add_row("next / n", "Skip to next track.")
        table.add_row("prev / p", "Go to previous track.")
        table.add_row("pause", "Toggle pause.")
        table.add_row("repeat <one/all/off>", "Set repeat mode.")
        table.add_row("shuffle", "Shuffle the queue.")
        table.add_row("config <get/set/list>", "Manage settings.")
        table.add_row("clear", "Clear the terminal screen.")
        table.add_row("exit", "Exit the application.")
        self.print_rich(table)

    def search(self, query: str):
        self.print_rich(f"Searching for '{query}'...")
        # Ignore next_href for standard search command
        results, _ = self.client.search_tracks(query, limit=10)

        if not results:
            self.print_rich("[red]No results.[/red]")
            self.last_search_results = []
            return

        self.last_search_results = results  # Store for numeric access

        table = Table(title=f"Results for '{query}'")
        table.add_column("#", style="dim")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="magenta")
        table.add_column("Artist", style="green")
        table.add_column("Duration", style="yellow")

        for i, track in enumerate(results):
            title = track.get("title", "Unknown")
            user = track.get("user", {}).get("username", "Unknown")
            duration_ms = track.get("duration", 0)
            dur_str = f"{duration_ms // 60000}:{(duration_ms // 1000) % 60:02d}"
            tid = str(track.get("id", ""))
            table.add_row(str(i + 1), tid, title, user, dur_str)

        self.print_rich(table)

    def _resolve_track(self, id_or_url: str):
        # Support explicit 'id:' prefix to bypass index lookup
        if id_or_url.lower().startswith("id:"):
            return self.client.get_track_by_id(int(id_or_url[3:]))

        # Heuristic for numeric selection
        if id_or_url.isdigit():
            val = int(id_or_url)
            # If value fits in search results, assume Index
            if 0 < val <= len(self.last_search_results):
                return self.last_search_results[val - 1]

            # Otherwise assume ID
            return self.client.get_track_by_id(val)

        elif "soundcloud.com" in id_or_url:
            return self.client.get_track_details(id_or_url)
        else:
            raise ValueError(
                "Invalid argument. Provide a Track ID, Number (from search), or SoundCloud URL."
            )

    # --- Station Mode Logic ---

    def start_station(self, query: str):
        self.station_mode = True
        self.station_query = query
        self.seen_track_ids = set()
        self.station_next_href = None

        self.player.clear_queue()
        self.print_rich(f"[bold magenta]Starting Station: {query}[/bold magenta]")

        # Initial fetch
        self._fetch_station_tracks()

        # Start playing if we found something
        if self.player.queue:
            self.next_track()
        else:
            self.print_rich("[red]Could not start station (no results).[/red]")
            self.station_mode = False

    def _fetch_station_tracks(self):
        if self.fetching_station:
            return
        self.fetching_station = True

        try:
            self.print_rich("[dim]Fetching more tracks for station...[/dim]")
            limit = 10

            # Use next_href if available, otherwise start new search
            tracks, next_href = self.client.search_tracks(
                self.station_query, limit=limit, next_href=self.station_next_href
            )

            self.station_next_href = next_href

            # Check if we were at the end of the queue *before* adding
            was_at_end = self.player.current_index >= len(self.player.queue) - 1

            added_count = 0
            for t in tracks:
                tid = t.get("id")
                # Filter duplicates (and ensure it's playable?)
                if tid and tid not in self.seen_track_ids:
                    self.seen_track_ids.add(tid)
                    self.player.add_to_queue(t)
                    added_count += 1

            if added_count == 0:
                self.print_rich("[dim]No new unique tracks found in this batch.[/dim]")
            elif was_at_end:
                if self.player.current_index != -1:
                    # Auto-advance if we were stuck at the end and it's not idle
                    self.print_rich(
                        "[bold magenta]Station updated. Auto-playing next track...[/bold magenta]"
                    )
                    self.next_track()
                else:
                    self.print_rich(
                        "[bold magenta]Station updated. Auto-playing next track...[/bold magenta]"
                    )

        except Exception as e:
            self.print_rich(f"[red]Error fetching station tracks: {e}[/red]")
        finally:
            self.fetching_station = False

    def _check_station_refill(self):
        if not self.station_mode:
            return

        # If we are near the end of the queue (e.g., less than 3 tracks remaining)
        # queue is list, current_index is int.
        # remaining = len - 1 - current_index
        remaining = len(self.player.queue) - 1 - self.player.current_index

        if remaining < 5 and self.station_next_href:
            threading.Thread(target=self._fetch_station_tracks).start()

    # --------------------------

    def _get_media_stream(self, track):
        media = track.get("media", {}).get("transcodings", [])
        return self.client.get_stream_url(media)

    def play_track(self, id_or_url: str):
        try:
            # Removed console.status
            track = self._resolve_track(id_or_url)

            stream_url = self._get_media_stream(track)
            if not stream_url:
                self.print_rich("[red]No stream available for this track.[/red]")
                return

            self.player.play_now(track, stream_url)
            self.print_rich(f"[bold green]Playing:[/bold green] {track.get('title')}")

        except Exception as e:
            self.print_rich(f"[red]Error playing track: {e}[/red]")

    def queue_track(self, id_or_url: str):
        try:
            self.print_rich("Resolving track...")
            track = self._resolve_track(id_or_url)
            self.player.add_to_queue(track)
            self.print_rich(f"Added to queue: {track.get('title')}")
        except Exception as e:
            self.print_rich(f"[red]Error queuing: {e}[/red]")

    def show_queue(self):
        if not self.player.queue:
            self.print_rich("Queue is empty.")
            return

        total = len(self.player.queue)
        current = self.player.current_index

        # Window: start = max(0, current - 5)
        #         end = min(total, current + 15)
        start_idx = max(0, current - 5)
        end_idx = min(total, current + 15)

        table = Table(title=f"Queue ({start_idx + 1}-{end_idx} of {total})")
        table.add_column("#", style="dim")
        table.add_column("Title")

        if start_idx > 0:
            table.add_row("...", "...", style="dim")

        for i in range(start_idx, end_idx):
            track = self.player.queue[i]
            style = "bold green" if i == current else ""
            idx = str(i + 1) if i != current else "▶"
            table.add_row(idx, track.get("title", "Unknown"), style=style)

        if end_idx < total:
            table.add_row("...", f"{total - end_idx} more...", style="dim")

        self.print_rich(table)

    def next_track(self):
        track = self.player.next()
        if track:
            # Need to load stream
            stream_url = self._get_media_stream(track)
            self.player.load_stream(stream_url)
            self.print_rich(
                f"[bold green]Now Playing:[/bold green] {track.get('title')}"
            )
        else:
            if self.station_mode:
                # we need to fetch more tracks instead of stopping
                self._fetch_station_tracks()

            else:
                self.print_rich("End of queue.")

    def prev_track(self):
        track = self.player.prev()
        if track:
            stream_url = self._get_media_stream(track)
            self.player.load_stream(stream_url)
            self.print_rich(
                f"[bold green]Now Playing:[/bold green] {track.get('title')}"
            )
        else:
            self.print_rich("Start of queue.")

    def show_status(self):
        track = self.player.current_track()
        if track:
            self.print_rich(f"Playing: {track.get('title')}")
            # Could add time checks if mpv property access works well
        else:
            self.print_rich("Nothing playing.")

    def set_repeat(self, mode_str: str):
        mode_str = mode_str.lower()
        if mode_str == "all":
            self.player.set_repeat_mode(RepeatMode.ALL)
        elif mode_str == "one":
            self.player.set_repeat_mode(RepeatMode.ONE)
        elif mode_str == "off":
            self.player.set_repeat_mode(RepeatMode.OFF)
        else:
            self.print_rich("Usage: repeat <one/all/off>")
            return
        self.print_rich(f"Repeat Mode set to: {self.player.repeat_mode.name}")

    def add_favorite(self, id_or_url: str):
        try:
            track = self._resolve_track(id_or_url)
            self.db.add_favorite(track)
            self.print_rich(f"Added to favorites: {track.get('title')}")
        except Exception as e:
            self.print_rich(f"[red]Error: {e}[/red]")

    def remove_favorite(self, id_or_url: str):
        # If arg is numeric index in favorites list? Or ID?
        # For simplicity, resolve it first (supports search index or ID),
        # then remove by ID.
        try:
            track = self._resolve_track(id_or_url)
            self.db.remove_favorite(track.get("id"))
            self.print_rich(f"Removed from favorites: {track.get('title')}")
        except Exception as e:
            self.print_rich(f"[red]Error: {e}[/red]")

    def show_favorites(self):
        if not self.db.favorites:
            self.print_rich("No favorites saved.")
            return

        # We treat favorites list as search results so user can `play 1` from it!
        self.last_search_results = self.db.favorites

        table = Table(title="Favorites")
        table.add_column("#", style="dim")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="magenta")

        for i, track in enumerate(self.db.favorites):
            table.add_row(
                str(i + 1), str(track.get("id")), track.get("title", "Unknown")
            )

        self.print_rich(table)
        self.print_rich(
            "[dim]You can now select these using numbers (e.g., play 1)[/dim]"
        )

    def save_queue_as_playlist(self, name: str):
        if not self.player.queue:
            self.print_rich("Queue is empty.")
            return
        self.db.save_playlist(name, self.player.queue)
        self.print_rich(
            f"Saved playlist '{name}' with {len(self.player.queue)} tracks."
        )

    def show_playlists(self):
        if not self.db.playlists:
            self.print_rich("No playlists saved.")
            return

        table = Table(title="Playlists")
        table.add_column("Name", style="cyan")
        table.add_column("Track Count")

        for name, tracks in self.db.playlists.items():
            table.add_row(name, str(len(tracks)))
        self.print_rich(table)

    def load_playlist(self, name: str):
        tracks = self.db.get_playlist(name)
        if not tracks:
            self.print_rich(f"[red]Playlist '{name}' not found.[/red]")
            return

        was_empty = len(self.player.queue) == 0

        for t in tracks:
            self.player.add_to_queue(t)
        self.print_rich(f"Added {len(tracks)} tracks from '{name}' to queue.")

        # If queue was empty and we are not playing, start playing first track
        if was_empty and self.player.current_index == -1:
            self.print_rich("[dim]Auto-starting playback...[/dim]")
            self.next_track()

    def unqueue_track(self, index: int):
        # UI is 1-indexed, internal is 0-indexed
        if self.player.remove_from_queue(index - 1):
            self.print_rich(f"Removed track at #{index}.")
        else:
            self.print_rich("Could not remove (invalid index or currently playing).")

    def _get_bottom_toolbar(self):
        try:
            track = self.player.current_track()
            if not track:
                return HTML(
                    ' <style bg="black" fg="white"> STOPPED </style> [No Track Loaded]'
                )

            # Status
            # Status
            if self.player.mpv.pause:
                status_xml = '<style bg="yellow" fg="black"> PAUSED </style>'
            else:
                status_xml = '<style bg="green" fg="black"> PLAYING </style>'

            # Info
            # Safe access to nested dicts
            user_data = track.get("user")
            if isinstance(user_data, dict):
                user = user_data.get("username", "Unknown")
            else:
                user = "Unknown"

            title = track.get("title", "Unknown")

            # Escape HTML special chars to prevent parser errors
            user = html.escape(str(user))
            title = html.escape(str(title))

            # Time
            pos, dur = self.player.get_time_info()
            # Ensure they are numbers
            try:
                pos = float(pos)
                dur = float(dur)
            except (ValueError, TypeError):
                pos = 0.0
                dur = 0.0

            pos_str = f"{int(pos) // 60:02d}:{int(pos) % 60:02d}"
            dur_str = f"{int(dur) // 60:02d}:{int(dur) % 60:02d}"

            return HTML(
                f' {status_xml} <style fg="cyan">{user}</style> - <b><style fg="white">{title}</style></b> '
                f'<style fg="gray">| {pos_str} / {dur_str}</style>'
            )
        except Exception as e:
            return HTML(f'<style bg="red" fg="white"> ERROR: {e} </style>')

    def show_info(self):
        track = self.player.current_track()
        if not track:
            self.print_rich("[red]Nothing playing.[/red]")
            return

        # Metadata Table
        meta_table = Table(show_header=False, box=None, padding=(0, 1))
        meta_table.add_column("Key", style="cyan")
        meta_table.add_column("Value", style="yellow", overflow="fold")

        meta_table.add_row("Title", track.get("title"))
        meta_table.add_row("Artist", track.get("user", {}).get("username"))
        meta_table.add_row("Genre", track.get("genre"))
        meta_table.add_row("Date", track.get("created_at", "")[:10])
        val_desc = str(track.get("description", ""))[:200].replace("\n", " ") + "..."
        meta_table.add_row("Desc", val_desc)
        meta_table.add_row("ID", str(track.get("id")))
        meta_table.add_row("Permalink", track.get("permalink_url"))

        # ASCII Art
        art = Text("[No Art]", style="dim")
        if self.config.get("ascii_enabled", True):
            url = track.get("artwork_url")
            if url:
                url = url.replace("large", "t500x500")
                art = generate_ascii_from_url(
                    url, width=self.config.get("ascii_art_width", 60)
                )

        # Main Layout
        layout = Table(show_header=False, box=None, padding=(0, 2))
        layout.add_column("Art")
        layout.add_column("Meta")
        layout.add_row(art, meta_table)

        panel = Panel(
            layout,
            title="[bold magenta]Track Info[/bold magenta]",
            subtitle="[dim]SoundCloud CLI[/dim]",
        )
        self.print_rich(panel)

    def view_playlist(self, name: str):
        tracks = self.db.get_playlist(name)
        if not tracks:
            self.print_rich(f"[red]Playlist '{name}' not found.[/red]")
            return

        table = Table(title=f"Playlist: {name}")
        table.add_column("#", style="dim")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Artist", style="magenta")
        table.add_column("Duration", style="yellow")

        for i, track in enumerate(tracks):
            duration_ms = track.get("duration", 0)
            dur_str = f"{duration_ms // 60000}:{(duration_ms // 1000) % 60:02d}"
            user = track.get("user", {}).get("username", "Unknown")
            table.add_row(
                str(i + 1),
                str(track.get("id")),
                track.get("title", "Unknown"),
                user,
                dur_str,
            )

        self.print_rich(table)

    def on_track_finished(self):
        def _next():
            self.next_track()
            self._check_station_refill()

        threading.Thread(target=_next).start()
