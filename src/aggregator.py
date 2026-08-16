"""Aggregate Strava activities into overview data.

- Categorizes activities into Road/MTB/Ski/Hike/Other
- Determines the 2 most-recently-used categories
- Aggregates YTD stats per category
- Collects polylines per category (for the overview 'heatmap')
"""
from collections import defaultdict
from datetime import datetime
from typing import NamedTuple


# Group Strava's fine-grained sport_type into high-level categories
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
    # Others fall through to "Other"
}


class CategoryStats(NamedTuple):
    """Aggregated stats for a single category (e.g. MTB)."""
    category: str
    count: int
    distance_m: float
    elevation_m: float
    moving_time_s: int
    polylines: list[str]  # summary_polyline strings from all activities


class Overview(NamedTuple):
    """Complete overview data for rendering."""
    year: int
    categories: list[CategoryStats]  # length 2, most recent first
    last_activity: dict  # most recent activity dict


def categorize(activity: dict) -> str:
    """Map an activity's sport_type to a high-level category."""
    sport = activity.get("sport_type") or activity.get("type", "")
    return CATEGORY_MAP.get(sport, "Other")


def build_overview(activities: list[dict], year: int | None = None) -> Overview:
    """Build overview from a list of activities (assumed to be YTD).

    Activities are expected to be sorted by start_date descending (Strava default).
    """
    if not activities:
        raise ValueError("Cannot build overview from empty activities list")

    year = year or datetime.now().year

    # Determine the 2 most-recently-used categories (in chronological order of last use)
    recent_categories: list[str] = []
    for act in activities:  # already sorted newest first
        cat = categorize(act)
        if cat == "Other":
            continue
        if cat not in recent_categories:
            recent_categories.append(cat)
        if len(recent_categories) == 2:
            break

    # Fallback if user only has 1 category
    if len(recent_categories) < 2:
        # Pick any second category from history, or repeat
        all_cats = {categorize(a) for a in activities}
        all_cats.discard("Other")
        for cat in all_cats:
            if cat not in recent_categories:
                recent_categories.append(cat)
                break
        if len(recent_categories) < 2:
            recent_categories.append(recent_categories[0] if recent_categories else "Other")

    # Aggregate per category
    by_category: dict[str, list[dict]] = defaultdict(list)
    for act in activities:
        by_category[categorize(act)].append(act)

    category_stats = []
    for cat in recent_categories:
        acts = by_category.get(cat, [])
        stats = CategoryStats(
            category=cat,
            count=len(acts),
            distance_m=sum(a.get("distance", 0) for a in acts),
            elevation_m=sum(a.get("total_elevation_gain", 0) for a in acts),
            moving_time_s=sum(a.get("moving_time", 0) for a in acts),
            polylines=[
                a["map"]["summary_polyline"]
                for a in acts
                if a.get("map", {}).get("summary_polyline")
            ],
        )
        category_stats.append(stats)

    return Overview(
        year=year,
        categories=category_stats,
        last_activity=activities[0],
    )


if __name__ == "__main__":
    # Smoke test
    import strava_client

    client = strava_client.StravaClient()
    year_start = int(datetime(datetime.now().year, 1, 1).timestamp())
    activities = client.activities_since(year_start, per_page=100)

    overview = build_overview(activities)
    print(f"Year: {overview.year}")
    print(f"Total activities fetched: {len(activities)}")
    print(f"\nTop 2 recent categories:")
    for stats in overview.categories:
        print(f"  {stats.category:10s} "
              f"{stats.count:3d} rides, "
              f"{stats.distance_m/1000:6.1f} km, "
              f"{int(stats.elevation_m):5d} hm, "
              f"{stats.moving_time_s/3600:5.1f} h "
              f"({len(stats.polylines)} polylines)")
    print(f"\nLast activity: {overview.last_activity['name']}")
