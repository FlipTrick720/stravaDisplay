import math
import os
from io import BytesIO
from pathlib import Path
from PIL import Image
import requests

TILE_SIZE = 256
TILE_CACHE_DIR = Path(os.environ.get("STRAVA_CONFIG_DIR", Path(__file__).resolve().parents[1] / "data")) / "tiles"
BASE_URL = "https://tile.opentopomap.org/{z}/{x}/{y}.png"

def fetch_tile(z: int, x: int, y: int) -> Image.Image:
    TILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = TILE_CACHE_DIR / f"opentopo_{z}_{x}_{y}.png"

    if cache_path.exists():
        return Image.open(cache_path).convert("RGBA")

    url = BASE_URL.format(z=z, x=x, y=y)
    headers = {"User-Agent": "StravaDisplay/1.0"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        img.save(cache_path)
        return img
    except Exception as e:
        print(f"Failed to fetch tile {url}: {e}")
        return Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (255, 255, 255, 255))

def get_centered_map_image(center_lat: float, center_lon: float, zoom: int, box_w: int, box_h: int):
    n = 2.0 ** zoom
    center_x = (center_lon + 180.0) / 360.0 * n
    lat_rad = math.radians(center_lat)
    center_y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    
    x_min = int(center_x - (box_w / 2 / TILE_SIZE))
    x_max = int(center_x + (box_w / 2 / TILE_SIZE))
    y_min = int(center_y - (box_h / 2 / TILE_SIZE))
    y_max = int(center_y + (box_h / 2 / TILE_SIZE))
    
    stitched = Image.new("RGBA", ((x_max - x_min + 1) * TILE_SIZE, (y_max - y_min + 1) * TILE_SIZE), (255, 255, 255, 255))
    
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            tile = fetch_tile(zoom, x, y)
            stitched.paste(tile, ((x - x_min) * TILE_SIZE, (y - y_min) * TILE_SIZE))
            
    px = int((center_x - x_min) * TILE_SIZE)
    py = int((center_y - y_min) * TILE_SIZE)
    
    crop_x0 = px - box_w // 2
    crop_y0 = py - box_h // 2
    
    cropped = stitched.crop((crop_x0, crop_y0, crop_x0 + box_w, crop_y0 + box_h))
    
    def project(lat, lon):
        n = 2.0 ** zoom
        xp = (lon + 180.0) / 360.0 * n * TILE_SIZE
        yp = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n * TILE_SIZE
        return int(xp - (x_min * TILE_SIZE + crop_x0)), int(yp - (y_min * TILE_SIZE + crop_y0))
        
    return cropped, project

def calculate_zoom(lat_min: float, lat_max: float, lon_min: float, lon_max: float, box_w: int, box_h: int) -> int:
    for z in range(18, 0, -1):
        n = 2.0 ** z
        x0 = (lon_min + 180.0) / 360.0 * n * TILE_SIZE
        x1 = (lon_max + 180.0) / 360.0 * n * TILE_SIZE
        y0 = (1.0 - math.asinh(math.tan(math.radians(lat_max))) / math.pi) / 2.0 * n * TILE_SIZE
        y1 = (1.0 - math.asinh(math.tan(math.radians(lat_min))) / math.pi) / 2.0 * n * TILE_SIZE
        
        if (x1 - x0) <= box_w and (y1 - y0) <= box_h:
            return z
    return 1
