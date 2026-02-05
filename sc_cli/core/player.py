import logging
import mpv
from typing import List, Dict, Any, Optional

class Player:
    def __init__(self):
        try:
            # log_handler=print helps debug, but might be too noisy for REPL
            self.mpv = mpv.MPV(input_default_bindings=True, input_vo_keyboard=True, ytdl=True)
            self.mpv['vo'] = 'null' # Audio only
        except Exception as e:
            raise RuntimeError(f"Could not initialize MPV. Ensure libmpv is installed: {e}")

        self.queue: List[Dict[str, Any]] = []
        self.current_index = -1
        
        # Set up event callbacks if needed, e.g. on track end
        @self.mpv.event_callback('end-file')
        def on_end_file(event):
            # event is usually a dictionary or MpvEvent object.
            # python-mpv 1.0+ MpvEvent usually has .as_dict() or simple getattr
            # safely check reason
            try:
                reason = getattr(event, 'event_data', {}).get('reason') if hasattr(event, 'event_data') else None
                if not reason and hasattr(event, 'data'):
                     reason = event.data.get('reason')
                
                # If we want to implement auto-next, we'd need a way to call self.next()
                # But self.next() requires client resolution (which Player doesn't have).
                # For now, we just pass to avoid the error.
                pass 
            except Exception:
                pass
        
    def play_now(self, track: Dict[str, Any], stream_url: str):
        """Clears queue and plays this track immediately."""
        self.stop()
        self.queue = [track]
        self.current_index = 0
        self._load(stream_url)
        
    def add_to_queue(self, track: Dict[str, Any]):
        """Adds a track to the end of the queue."""
        self.queue.append(track)
        
    def _load(self, url: str):
        self.mpv.play(url)
        self.mpv.wait_until_playing()

    def play(self):
        """Resume playback."""
        self.mpv.pause = False

    def pause(self):
        """Pause playback."""
        self.mpv.pause = True

    def toggle_pause(self):
        self.mpv.pause = not self.mpv.pause

    def stop(self):
        self.mpv.stop()
        
    def current_track(self) -> Optional[Dict[str, Any]]:
        if 0 <= self.current_index < len(self.queue):
            return self.queue[self.current_index]
        return None

    def next(self) -> Optional[Dict[str, Any]]:
        if self.current_index + 1 < len(self.queue):
            self.current_index += 1
            # Note: The caller (REPL) needs to fetch the stream URL for the next track 
            # and call _load, because Player doesn't have the Client to resolve URLs.
            # Or we pass the client to the player? 
            # Better design: Return the track to the controller, controller resolves, then calls player.load_stream
            return self.queue[self.current_index]
        return None

    def prev(self) -> Optional[Dict[str, Any]]:
        if self.current_index - 0 > 0:
            self.current_index -= 1
            return self.queue[self.current_index]
        return None
    
    def load_stream(self, stream_url: str):
        self._load(stream_url)
