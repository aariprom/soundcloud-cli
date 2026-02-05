import logging
import shlex
import threading
import time
from typing import List
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from sc_cli.core.client import SoundCloudClient
from sc_cli.core.player import Player

console = Console(width=120)

class REPL:
    def __init__(self):
        self.client = SoundCloudClient()
        self.player = Player()
        self.running = True
        
    def start(self):
        console.print("[bold green]SoundCloud CLI Interactive Mode[/bold green]")
        console.print("Type 'help' for commands.")
        
        while self.running:
            try:
                user_input = Prompt.ask("[bold cyan]sc-cli[/bold cyan]")
                if not user_input.strip():
                    continue
                
                parts = shlex.split(user_input)
                cmd = parts[0].lower()
                args = parts[1:]
                
                if cmd in ['exit', 'quit', 'q']:
                    self.stop()
                    break
                elif cmd == 'help':
                    self.show_help()
                elif cmd == 'search':
                    self.search(" ".join(args))
                elif cmd == 'play':
                    if not args:
                        self.player.play()
                        console.print("Resumed.")
                    else:
                        self.play_track(args[0])
                elif cmd == 'pause':
                    self.player.toggle_pause()
                    console.print("Toggled pause.")
                elif cmd == 'stop':
                    self.player.stop()
                    console.print("Stopped.")
                elif cmd == 'queue':
                    if args:
                        self.queue_track(args[0])
                    else:
                        self.show_queue()
                elif cmd in ['next', 'n']:
                    self.next_track()
                elif cmd in ['prev', 'p']:
                    self.prev_track()
                elif cmd == 'status':
                    self.show_status()
                else:
                    console.print(f"[red]Unknown command: {cmd}[/red]")
                    
            except KeyboardInterrupt:
                console.print("\nType 'exit' to quit.")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                
    def stop(self):
        self.player.stop()
        self.running = False
        console.print("Goodbye!")

    def show_help(self):
        table = Table(title="Commands")
        table.add_column("Command", style="cyan")
        table.add_column("Description")
        table.add_row("search <query>", "Search for tracks.")
        table.add_row("play <id|url>", "Play a track immediately (clears queue).")
        table.add_row("queue <id|url>", "Add a track to the queue.")
        table.add_row("queue", "Show current queue.")
        table.add_row("next / n", "Skip to next track.")
        table.add_row("prev / p", "Go to previous track.")
        table.add_row("pause", "Toggle pause.")
        table.add_row("exit", "Exit the application.")
        console.print(table)

    def search(self, query: str):
        with console.status(f"Searching for '{query}'..."):
            results = self.client.search_tracks(query)
            
        if not results:
            console.print("[red]No results.[/red]")
            return

        table = Table(title=f"Results for '{query}'")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="magenta")
        table.add_column("Artist", style="green")
        table.add_column("Duration", style="yellow")
        
        for track in results:
            title = track.get('title', 'Unknown')
            user = track.get('user', {}).get('username', 'Unknown')
            duration_ms = track.get('duration', 0)
            dur_str = f"{duration_ms // 60000}:{(duration_ms // 1000) % 60:02d}"
            tid = str(track.get('id', ''))
            table.add_row(tid, title, user, dur_str)
            
        console.print(table)

    def _resolve_track(self, id_or_url: str):
        if id_or_url.isdigit():
            # ID lookup
            return self.client.get_track_by_id(int(id_or_url))
        elif "soundcloud.com" in id_or_url:
            return self.client.get_track_details(id_or_url)
        else:
            raise ValueError("Invalid argument. Provide a Track ID or SoundCloud URL.")

    def _get_media_stream(self, track):
        media = track.get('media', {}).get('transcodings', [])
        return self.client.get_stream_url(media)

    def play_track(self, id_or_url: str):
        try:
            with console.status("Resolving track..."):
                track = self._resolve_track(id_or_url)
                
            stream_url = self._get_media_stream(track)
            if not stream_url:
                console.print("[red]No stream available for this track.[/red]")
                return

            self.player.play_now(track, stream_url)
            console.print(f"[bold green]Playing:[/bold green] {track.get('title')}")
            
        except Exception as e:
            console.print(f"[red]Error playing track: {e}[/red]")

    def queue_track(self, id_or_url: str):
        try:
            with console.status("Resolving track..."):
                track = self._resolve_track(id_or_url)
            self.player.add_to_queue(track)
            console.print(f"Added to queue: {track.get('title')}")
        except Exception as e:
            console.print(f"[red]Error queuing: {e}[/red]")

    def show_queue(self):
        if not self.player.queue:
            console.print("Queue is empty.")
            return
            
        table = Table(title="Queue")
        table.add_column("#", style="dim")
        table.add_column("Title")
        
        for i, track in enumerate(self.player.queue):
            style = "bold green" if i == self.player.current_index else ""
            table.add_row(str(i+1), track.get('title', 'Unknown'), style=style)
            
        console.print(table)

    def next_track(self):
        track = self.player.next()
        if track:
            # Need to load stream
            stream_url = self._get_media_stream(track)
            self.player.load_stream(stream_url)
            console.print(f"[bold green]Now Playing:[/bold green] {track.get('title')}")
        else:
            console.print("End of queue.")

    def prev_track(self):
        track = self.player.prev()
        if track:
             stream_url = self._get_media_stream(track)
             self.player.load_stream(stream_url)
             console.print(f"[bold green]Now Playing:[/bold green] {track.get('title')}")
        else:
             console.print("Start of queue.")

    def show_status(self):
        track = self.player.current_track()
        if track:
            console.print(f"Playing: {track.get('title')}")
            # Could add time checks if mpv property access works well
        else:
            console.print("Nothing playing.")

