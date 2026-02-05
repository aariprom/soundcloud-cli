import mpv
import random
from enum import Enum
from typing import List, Dict, Any, Optional

class RepeatMode(Enum):
    OFF = 0
    ONE = 1
    ALL = 2

class Player:
    def __init__(self, on_finished_callback=None):
        try:
            # log_handler=print helps debug, but might be too noisy for REPL
            self.mpv = mpv.MPV(input_default_bindings=True, input_vo_keyboard=True, ytdl=True)
            self.mpv['vo'] = 'null' # Audio only
        except Exception as e:
            raise RuntimeError(f"Could not initialize MPV. Ensure libmpv is installed: {e}")

        self.queue: List[Dict[str, Any]] = []
        self.current_index = -1
        self.repeat_mode = RepeatMode.OFF
        self.on_finished_callback = on_finished_callback
        
        # Set up event callbacks if needed, e.g. on track end
        @self.mpv.event_callback('end-file')
        def on_end_file(event):
            try:
                
                # Check for natural end of file
                # Use as_dict() for reliable access
                reason = None
                if hasattr(event, 'as_dict'):
                     d = event.as_dict()
                     if 'reason' in d:
                         reason = d['reason']
                     elif 'event' in d and isinstance(d['event'], dict):
                         reason = d['event'].get('reason')
                
                # Handle bytes if returned by mpv
                if isinstance(reason, bytes):
                    reason = reason.decode('utf-8')

                if reason in ['eof', 'end-file', 0, 2, 3]: 
                     # Standard MPV: 0=EOF, 2=STOP, 3=QUIT, 4=ERROR
                     if self.on_finished_callback:
                         self.on_finished_callback()
            except Exception as e:
                print(f"Error in on_end_file: {e}")
                
    def seek(self, position: float, absolute=False):
        try:
            if absolute:
                self.mpv.seek(position, reference="absolute")
            else:
                self.mpv.seek(position)
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
        
    def set_repeat_mode(self, mode: RepeatMode):
        self.repeat_mode = mode
        # If REPEAT_ONE, tell mpv to loop file
        if mode == RepeatMode.ONE:
            self.mpv.loop = True
        else:
            self.mpv.loop = False

    def shuffle_queue(self):
        if not self.queue:
            return
            
        # Don't shuffle the *currently playing* track if possible,
        # or just shuffle the whole thing and reset index?
        # Better UX: Keep current track playing, shuffle the rest.
        
        current_track = self.current_track()
        if current_track:
            # We need to find current track in the list and keep it?
            # Or just shuffle everything and find the new index of current track.
            random.shuffle(self.queue)
            # Update index
            try:
                self.current_index = self.queue.index(current_track)
            except ValueError:
                self.current_index = 0 # Fallback
        else:
             random.shuffle(self.queue)
             self.current_index = -1

    def clear_queue(self):
        self.stop()
        self.queue = []
        self.current_index = -1

    def remove_from_queue(self, index: int) -> bool:
        if 0 <= index < len(self.queue):
            # If removing current track? Not allowed/undefined behavior usually.
            if index == self.current_index:
                 # Ideally stop or skip? For simplicity, we block it or just remove and adjust index.
                 return False
            
            self.queue.pop(index)
            if index < self.current_index:
                self.current_index -= 1
            return True
        return False

    def current_track(self) -> Optional[Dict[str, Any]]:
        if 0 <= self.current_index < len(self.queue):
            return self.queue[self.current_index]
        return None

    def next(self) -> Optional[Dict[str, Any]]:
        if self.repeat_mode == RepeatMode.ONE:
             # Logic is handled by mpv.loop usually, but if called manually:
             return self.current_track()

        if self.current_index + 1 < len(self.queue):
            self.current_index += 1
            return self.queue[self.current_index]
        elif self.repeat_mode == RepeatMode.ALL and self.queue:
            # Loop back to start
            self.current_index = 0
            return self.queue[self.current_index]
            
        return None

    def prev(self) -> Optional[Dict[str, Any]]:
        if self.current_index - 0 > 0:
            self.current_index -= 1
            return self.queue[self.current_index]
        return None
    
    def load_stream(self, stream_url: str):
        self._load(stream_url)

    def get_time_info(self):
        """Returns (current_time, total_duration) in seconds."""
        try:
            # mpv properties can be None if not playing/loaded
            pos = self.mpv.time_pos or 0
            dur = self.mpv.duration or 0
            return pos, dur
        except Exception:
            return 0, 0
