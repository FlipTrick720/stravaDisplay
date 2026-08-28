import re

with open("components/map_view.py", "r") as f:
    src = f.read()

src = src.replace("from components.cities import _lookup_cities", "from cities import cities_in_bounds as _lookup_cities")

with open("components/map_view.py", "w") as f:
    f.write(src)
print("patched")
