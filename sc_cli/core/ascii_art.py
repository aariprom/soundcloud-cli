import requests
import io
from PIL import Image
from rich.text import Text
from rich.style import Style
from rich.color import Color


def generate_ascii_from_url(url: str, width: int = 60) -> Text:
    """Generates a block-based colorful ANSI art from an image URL."""
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()

        # Load image
        img = Image.open(io.BytesIO(resp.content))
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        aspect = h / w

        # Terminal cells are approx 1x2 ratio visually
        # visual_height = width * aspect * 0.5
        # But we use 2 pixels per char (half-block)
        # So physical height of resized image should be 2 * visual_height
        # = width * aspect

        new_height = int(width * aspect)
        # Make sure height is even for row pairing
        if new_height % 2 != 0:
            new_height += 1

        img = img.resize((width, new_height), resample=Image.Resampling.BILINEAR)

        pixels = img.load()
        text = Text()

        for y in range(0, new_height, 2):
            for x in range(width):
                r1, g1, b1 = pixels[x, y]
                # Check for boundary (just in case)
                if y + 1 < new_height:
                    r2, g2, b2 = pixels[x, y + 1]
                else:
                    r2, g2, b2 = 0, 0, 0

                # Top pixel = Foreground, Bottom pixel = Background
                # Character = Upper Half Block '▀'

                color_fg = Color.from_rgb(r1, g1, b1)
                color_bg = Color.from_rgb(r2, g2, b2)

                style = Style(color=color_fg, bgcolor=color_bg)
                text.append("▀", style=style)
            text.append("\n")

        return text

    except Exception as e:
        return Text(f"[Error loading art: {e}]", style="red")
