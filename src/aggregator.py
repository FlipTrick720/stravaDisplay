"""Aggregate Strava activities into overview data.

- Categorizes activities into Road/MTB/Ski/Hike/Other
- Determines the 2 most-recently-used categories
- Aggregates YTD stats per category
- Collects polylines per category (with outlier filtering)
"""
from collections import defaultdict
from datetime import datetime
from typing import NamedTuple
import polyline as pl


CATEGORY_MAP = {
    # Road
    "Ride": "Road",
    "VirtualRide": "Road",
    "EBikeRide": "Road",
    # MTB
    "MountainBikeRide": "MTB",
    "GravelRide": "MTB",
    "EMountainBikeRide": "MTB",
    # Ski
    "BackcountrySki": "Ski",
    "AlpineSki": "Ski",
    "NordicSki": "Ski",
    "TourSki": "Ski",
    # Hike
    "Hike": "Hike",
}


class CategoryStats(NamedTuple):
    category: str
    count: int
    distance_m: float
    elevation_m: float
    moving_time_s: int
    polylines: list[str]


class Overview(NamedTuple):
    year: int
    categories: list[CategoryStats]
    last_activity: dict


def categorize(activity: dict) -> str:
    """Map an activity's sport_type to a high-level category."""
    sport = activity.get("sport_type") or activity.get("type", "")
    return CATEGORY_MAP.get(sport, "Other")


def _polyline_center(poly: str) -> tuple[float, float] | None:
    """Return (lat, lon) center of a polyline's bounding box."""
    points = pl.decode(poly)
    if not points:
        return None
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return ((min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2)


def _filter_outlier_polylines(polylines: list[str], max_km_from_median: float = 100.0) -> list[str]:
    """Drop polylines whose center is far from the median center.

    Purpose: exclude vacation trips (e.g. one ride in Spain) that would
    force the heatmap projection to zoom out and squash local rides.

    Never returns empty - falls back to original list if filter would kill everything.
    """
    if len(polylines) < 3:
        return polylines

    centers = [(p, _polyline_center(p)) for p in polylines]
    centers = [(p, c) for p, c in centers if c is not None]
    if not centers:
        return polylines

    lats = sorted(c[0] for _, c in centers)
    lons = sorted(c[1] for _, c in centers)
    med_lat = lats[len(lats) // 2]
    med_lon = lons[len(lons) // 2]

    # 1 deg lat ~= 111 km. Rough enough for outlier detection.
    max_deg = max_km_from_median / 111.0

    filtered = [
        p for p, (lat, lon) in centers
        if abs(lat - med_lat) < max_deg and abs(lon - med_lon) < max_deg * 1.5
    ]
    return filtered or polylines


def _filter_dominant_cluster(polylines: list[str], cell_size_deg: float = 0.2) -> list[str]:
    """Keep only polylines whose center is in the densest 3x3 grid area.

    cell_size_deg: 0.2 deg ~= 22 km. So we group tracks by ~20km cells,
    then keep only the ones in the top cell + its 8 neighbors.
    """
    if len(polylines) < 5:
        return polylines

    # Bucket polylines by (lat_cell, lon_cell)
    buckets: dict[tuple[int, int], list[str]] = defaultdict(list)
    centers: dict[str, tuple[float, float]] = {}

    for poly in polylines:
        center = _polyline_center(poly)
        if center is None:
            continue
        centers[poly] = center
        lat_cell = int(center[0] / cell_size_deg)
        lon_cell = int(center[1] / cell_size_deg)
        buckets[(lat_cell, lon_cell)].append(poly)

    if not buckets:
        return polylines

    # Find the densest cell
    top_cell = max(buckets.keys(), key=lambda k: len(buckets[k]))
    top_lat, top_lon = top_cell

    # Keep polylines whose center is in top cell OR its 8 neighbors
    kept = []
    for poly, (lat, lon) in centers.items():
        lat_cell = int(lat / cell_size_deg)
        lon_cell = int(lon / cell_size_deg)
        if abs(lat_cell - top_lat) <= 1 and abs(lon_cell - top_lon) <= 1:
            kept.append(poly)

    return kept or polylines


def build_overview(activities: list[dict], year: int | None = None) -> Overview:
    """Build overview from a list of activities (assumed YTD, newest first)."""
    if not activities:
        raise ValueError("Cannot build overview from empty activities list")

    year = year or datetime.now().year

    # Two most-recently-used categories, in order of last use
    recent_categories: list[str] = []
    for act in activities:
        cat = categorize(act)
        if cat == "Other":
            continue
        if cat not in recent_categories:
            recent_categories.append(cat)
        if len(recent_categories) == 2:
            break

    # Fallback if user only has 1 category
    if len(recent_categories) < 2:
        all_cats = {categorize(a) for a in activities}
        all_cats.discard("Other")
        for cat in all_cats:
            if cat not in recent_categories:
                recent_categories.append(cat)
                break
        if len(recent_categories) < 2:
            recent_categories.append(recent_categories[0] if recent_categories else "Other")

    # Group activities by category
    by_category: dict[str, list[dict]] = defaultdict(list)
    for act in activities:
        by_category[categorize(act)].append(act)

    # Build stats per selected category
    category_stats: list[CategoryStats] = []
    for cat in recent_categories:
        acts = by_category.get(cat, [])
        polylines_raw = [
            a["map"]["summary_polyline"]
            for a in acts
            if a.get("map", {}).get("summary_polyline")
        ]
        MAX_POLYLINES_PER_CAT = 15
        recent_polylines = polylines_raw[:MAX_POLYLINES_PER_CAT]
        polylines_filtered = _filter_dominant_cluster(recent_polylines)

        stats = CategoryStats(
            category=cat,
            count=len(acts),
            distance_m=sum(a.get("distance", 0) for a in acts),
            elevation_m=sum(a.get("total_elevation_gain", 0) for a in acts),
            moving_time_s=sum(a.get("moving_time", 0) for a in acts),
            polylines=polylines_filtered,
        )
        category_stats.append(stats)

    return Overview(
        year=year,
        categories=category_stats,
        last_activity=activities[0],
    )


if __name__ == "__main__":
    import strava_client

    client = strava_client.StravaClient()
    year_start = int(datetime(datetime.now().year, 1, 1).timestamp())
    activities = client.activities_since(year_start, per_page=100)

    overview = build_overview(activities)
    print(f"Year: {overview.year}")
    print(f"Total activities fetched: {len(activities)}")
    print(f"\nTop 2 recent categories:")
    for stats in overview.categories:
        raw_count = sum(
            1 for a in activities
            if categorize(a) == stats.category and a.get("map", {}).get("summary_polyline")
        )
        print(f"  {stats.category:10s} "
              f"{stats.count:3d} rides, "
              f"{stats.distance_m/1000:6.1f} km, "
              f"{int(stats.elevation_m):5d} hm, "
              f"{stats.moving_time_s/3600:5.1f} h "
              f"({len(stats.polylines)}/{raw_count} polylines after outlier filter)")
    print(f"\nLast activity: {overview.last_activity['name']}")
