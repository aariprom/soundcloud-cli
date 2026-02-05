import re
import logging
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup

class SoundCloudClient:
    BASE_URL = "https://api-v2.soundcloud.com"
    SITE_URL = "https://soundcloud.com"

    CONFIG_DIR = Path.home() / ".config" / "soundcloud-cli"
    CLIENT_ID_FILE = CONFIG_DIR / "client_id"

    def __init__(self, client_id: Optional[str] = None):
        self.session = requests.Session()
        self.client_id = client_id
        
        # Try loading from cache if not provided
        if not self.client_id:
            self.client_id = self._get_cached_client_id()
            
        if not self.client_id:
            self.client_id = self._fetch_client_id()
            if self.client_id:
                self._save_client_id(self.client_id)
        
        if not self.client_id:
            raise ValueError("Could not find a valid Client ID. Please provide one manually.")

    def _get_cached_client_id(self) -> Optional[str]:
        if self.CLIENT_ID_FILE.exists():
            try:
                cid = self.CLIENT_ID_FILE.read_text().strip()
                if cid and len(cid) > 20: # Basic validation
                    print(f"Loaded Client ID from cache: {cid}")
                    return cid
            except Exception:
                pass
        return None

    def _save_client_id(self, client_id: str):
        try:
            self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self.CLIENT_ID_FILE.write_text(client_id)
            print(f"Saved Client ID to {self.CLIENT_ID_FILE}")
        except Exception as e:
            print(f"Warning: Could not save client_id: {e}")

    def _fetch_client_id(self) -> Optional[str]:
        """
        Scrapes the SoundCloud website to find a valid Client ID.
        SoundCloud's frontend app.js usually contains the client_id.
        """
        try:
            print("Fetching public Client ID...")
            response = self.session.get(self.SITE_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all script tags with src
            scripts = [script['src'] for script in soup.find_all('script') if script.get('src')]
            
            # The app js usually looks like https://a-v2.sndcdn.com/assets/2-....js
            # We iterate through them to find the client_id
            for script_url in scripts:
                if "sndcdn.com" in script_url:
                    js_resp = self.session.get(script_url)
                    if js_resp.status_code == 200:
                        # Look for client_id:"..." or client_id="..." with 32 chars
                        # Pattern found in SC JS: client_id:"rP0..."
                        match = re.search(r'client_id:"([a-zA-Z0-9]{32})"', js_resp.text)
                        if match:
                            cid = match.group(1)
                            print(f"Found Client ID: {cid}")
                            return cid
                        
                        # Fallback pattern
                        match = re.search(r'client_id="([a-zA-Z0-9]{32})"', js_resp.text)
                        if match:
                             cid = match.group(1)
                             print(f"Found Client ID: {cid}")
                             return cid

        except Exception as e:
            logging.error(f"Error fetching client ID: {e}")
        
        return None

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def search_tracks(self, query: str, limit: int = 10, next_href: Optional[str] = None) -> tuple[List[Dict[str, Any]], Optional[str]]:
        if next_href:
             # Ensure client_id is present in the URL
             if "client_id=" not in next_href:
                 sep = "&" if "?" in next_href else "?"
                 next_href += f"{sep}client_id={self.client_id}"
                 
             # Use the provided next_href for pagination
             resp = self.session.get(next_href, headers=self._get_headers())
        else:
            params = {
                "q": query,
                "client_id": self.client_id,
                "limit": limit,
                "app_version": "1706696706", # Mock version
                "app_locale": "en"
            }
            resp = self.session.get(f"{self.BASE_URL}/search/tracks", params=params, headers=self._get_headers())
            
        resp.raise_for_status()
        data = resp.json()
        return data.get('collection', []), data.get('next_href')

    def get_track_details(self, track_url: str) -> Dict[str, Any]:
        """Resolve a track URL to its details."""
        params = {
            "url": track_url,
            "client_id": self.client_id
        }
        resp = self.session.get(f"{self.BASE_URL}/resolve", params=params, headers=self._get_headers())
        resp.raise_for_status()
        return resp.json()

    def get_track_by_id(self, track_id: int) -> Dict[str, Any]:
        """Fetch track details by ID using the /tracks endpoints."""
        params = {
            "ids": str(track_id),
            "client_id": self.client_id
        }
        # /tracks returns a list of tracks
        resp = self.session.get(f"{self.BASE_URL}/tracks", params=params, headers=self._get_headers())
        resp.raise_for_status()
        data = resp.json()
        if data and isinstance(data, list):
            return data[0]
        raise ValueError(f"Track ID {track_id} not found.")

    def get_stream_url(self, track_transcodings: List[Dict[str, Any]]) -> Optional[str]:
        """
        Extract the highest quality stream URL from the track's transcoding list.
        Prefers 'audio/mpeg' (MP3) or 'audio/ogg; codecs="opus"'.
        """
        # Priority: hls/mp3 -> progressive/mp3
        # The transcoding object has a 'url' property which is an API endpoint.
        # We need to hit that endpoint (with client_id) to get the actual media URL.
        
        target_transcoding = None
        
        # Simple heuristic: find 'progressive' first (easier for mpv), then 'hls'
        for t in track_transcodings:
             format_protocol = t.get('format', {}).get('protocol')
             if format_protocol == 'progressive':
                 target_transcoding = t
                 break
        
        if not target_transcoding:
            # Fallback to hls
             for t in track_transcodings:
                if t.get('format', {}).get('protocol') == 'hls':
                    target_transcoding = t
                    break
        
        if target_transcoding:
            # Get the resolution URL
            api_url = target_transcoding.get('url')
            params = {
                "client_id": self.client_id
            }
            resp = self.session.get(api_url, params=params, headers=self._get_headers())
            if resp.status_code == 200:
                return resp.json().get('url')
        
        return None
