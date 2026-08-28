import re
with open("components/map_view.py", "r") as f:
    src = f.read()
    
old_marker = """class MapMarker:
    def __init__(self, lat: float, lon: float, is_start_end: bool = False):
        self.lat = lat
        self.lon = lon
        self.is_start_end = is_start_end"""

new_marker = """class MapMarker:
    def __init__(self, lat: float, lon: float, label: str = "", is_start_end: bool = False):
        self.lat = lat
        self.lon = lon
        self.label = label
        self.is_start_end = is_start_end"""

src = src.replace(old_marker, new_marker)

# Also fix _lookup_cities call, which takes positional unpacking `*bounds`
src = src.replace("_lookup_cities(lat_min, lat_max, lon_min, lon_max, max_cities)", "_lookup_cities(lat_min, lat_max, lon_min, lon_max, max_cities=max_cities)")

with open("components/map_view.py", "w") as f:
    f.write(src)
print("patched")
