import json
import os
from typing import List, Dict, Any, Optional

class Database:
    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            # Default to ~/.config/soundcloud-cli/db.json
            config_dir = os.path.join(os.path.expanduser("~"), ".config", "soundcloud-cli")
            os.makedirs(config_dir, exist_ok=True)
            self.db_path = os.path.join(config_dir, "db.json")
        else:
            self.db_path = db_path
            
        self.favorites: List[Dict[str, Any]] = []
        self.playlists: Dict[str, List[Dict[str, Any]]] = {}
        self.load()

    def load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    self.favorites = data.get('favorites', [])
                    self.playlists = data.get('playlists', {})
            except Exception as e:
                print(f"Error loading database: {e}")
                self.favorites = []
                self.playlists = {}
        else:
            self.favorites = []
            self.playlists = {}

    def save(self):
        try:
            data = {
                'favorites': self.favorites,
                'playlists': self.playlists
            }
            with open(self.db_path, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving database: {e}")

    def add_favorite(self, track: Dict[str, Any]):
        # Check for duplicates by ID
        track_id = track.get('id')
        for existing in self.favorites:
            if existing.get('id') == track_id:
                return # Already exists
        self.favorites.append(track)
        self.save()

    def remove_favorite(self, track_id: int):
        self.favorites = [t for t in self.favorites if t.get('id') != track_id]
        self.save()

    def is_favorite(self, track_id: int) -> bool:
        return any(t.get('id') == track_id for t in self.favorites)

    def save_playlist(self, name: str, tracks: List[Dict[str, Any]]):
        self.playlists[name] = tracks
        self.save()

    def delete_playlist(self, name: str):
        if name in self.playlists:
            del self.playlists[name]
            self.save()

    def get_playlist(self, name: str) -> Optional[List[Dict[str, Any]]]:
        return self.playlists.get(name)
