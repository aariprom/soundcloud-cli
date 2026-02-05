import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

class ConfigManager:
    CONFIG_DIR = Path.home() / ".config" / "soundcloud-cli"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    
    DEFAULTS = {
        "theme_color": "cyan",
        "ascii_art_width": 60,
        "ascii_enabled": True
    }

    def __init__(self):
        self.config: Dict[str, Any] = self.DEFAULTS.copy()
        self.load()

    def load(self):
        if not self.CONFIG_FILE.exists():
            return
        
        try:
            text = self.CONFIG_FILE.read_text()
            data = json.loads(text)
            self.config.update(data)
        except Exception as e:
            logging.error(f"Failed to load config: {e}")

    def save(self):
        try:
            self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self.CONFIG_FILE.write_text(json.dumps(self.config, indent=4))
        except Exception as e:
            logging.error(f"Failed to save config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default if default is not None else self.DEFAULTS.get(key))

    def set(self, key: str, value: Any):
        # Basic type inference for boolean/int
        if isinstance(value, str):
            if value.lower() in ("true", "yes"):
                value = True
            elif value.lower() in ("false", "no"):
                value = False
            elif value.isdigit():
                value = int(value)
                
        self.config[key] = value
        self.save()
        
    def list(self) -> Dict[str, Any]:
        return self.config
