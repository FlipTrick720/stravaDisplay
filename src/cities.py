"""Static city list for map context labels.

Only cities relevant to Alpine cycling/skiing regions.
Add more as needed - runs offline, no API.
"""

# (name, latitude, longitude, population_rank)
# Lower rank = more prominent (shown first when space is tight)
CITIES = [
    # Rank 1: capitals / major cities
    ("München", 48.1351, 11.5820, 1),
    ("Wien", 48.2082, 16.3738, 1),
    ("Zürich", 47.3769, 8.5417, 1),
    ("Milano", 45.4642, 9.1900, 1),

    # Rank 2: regional centers
    ("Innsbruck", 47.2692, 11.4041, 2),
    ("Salzburg", 47.8095, 13.0550, 2),
    ("Graz", 47.0707, 15.4395, 2),
    ("Bern", 46.9481, 7.4474, 2),
    ("Bolzano", 46.4983, 11.3548, 2),
    ("Como", 45.8081, 9.0852, 2),
    ("Verona", 45.4384, 10.9916, 2),
    ("Klagenfurt", 46.6247, 14.3050, 2),
    ("Linz", 48.3069, 14.2858, 2),

    # Rank 3: smaller towns, useful for orientation
    ("Kufstein", 47.5834, 12.1697, 3),
    ("Kitzbühel", 47.4462, 12.3922, 3),
    ("St. Anton", 47.1289, 10.2683, 3),
    ("Garmisch", 47.4915, 11.0954, 3),
    ("Chur", 46.8508, 9.5320, 3),
    ("Davos", 46.8027, 9.8368, 3),
    ("St. Moritz", 46.4980, 9.8399, 3),
    ("Bregenz", 47.5031, 9.7471, 3),
    ("Landeck", 47.1408, 10.5687, 3),
    ("Lienz", 46.8296, 12.7686, 3),
    ("Zell am See", 47.3252, 12.7947, 3),
    ("Meran", 46.6713, 11.1594, 3),
    ("Cortina", 46.5405, 12.1357, 3),
    ("Sondrio", 46.1710, 9.8720, 3),
]


def cities_in_bounds(
    lat_min: float, lat_max: float, lon_min: float, lon_max: float,
    max_cities: int = 6,
) -> list[tuple[str, float, float]]:
    """Return cities within bounds, most prominent first, capped at max_cities.

    Returns list of (name, lat, lon).
    """
    in_bounds = [
        (name, lat, lon, rank)
        for name, lat, lon, rank in CITIES
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max
    ]
    in_bounds.sort(key=lambda c: c[3])  # by rank (most prominent first)
    return [(name, lat, lon) for name, lat, lon, _ in in_bounds[:max_cities]]
