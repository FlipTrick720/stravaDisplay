"""Aggregate Strava activities into overview and weekly-comparison data.

- Categorizes activities into Road/MTB/Ski/Hike/Other
- Determines the 2 most-recently-used categories
- Aggregates YTD stats per category
- Collects polylines per category (with outlier filtering)
- Buckets activities (all sport types) into the last 6 ISO weeks
"""
from collections import defaultdict
from datetime import date, datetime, timedelta
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
    """Build overview from a list of activities.

    Sorts activities newest-first internally, so caller can pass any order
    (Strava's /activities returns DESC, /activities?after=... returns ASC).
    """
    if not activities:
        raise ValueError("Cannot build overview from empty activities list")

    # Normalize: always work with newest-first
    activities = sorted(
        activities,
        key=lambda a: a["start_date"],
        reverse=True,
    )

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


# =========================
# Weekly comparison
# =========================

class WeekStats(NamedTuple):
    iso_week: int
    year: int
    start_date: date          # Monday
    end_date: date            # Sunday
    distance_m: float
    elevation_m: float
    moving_time_s: int
    avg_heartrate_bpm: float | None
    activity_count: int
    days_with_activity: int
    is_current: bool


class WeeklyOverview(NamedTuple):
    weeks: list[WeekStats]        # 6 entries, oldest first
    current_week: WeekStats       # alias for weeks[-1]
    avg_distance_m: float         # avg across the 5 previous COMPLETED weeks
    avg_elevation_m: float
    avg_heartrate_bpm: float | None
    total_distance_m: float       # sum across all 6 weeks
    total_elevation_m: float
    total_activities: int
    date_range_start: date        # Monday of the oldest week
    date_range_end: date          # Sunday of the current week


def _local_date(iso: str) -> date:
    """Calendar date from a Strava start_date_local timestamp.

    start_date_local carries local wall-clock numbers with a 'Z' suffix (a
    documented Strava API quirk, not a real UTC timestamp) - see
    renderer._format_date for the same convention. We only ever read the
    date/time fields off it and never convert its timezone.
    """
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).date()


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def build_weekly(activities: list[dict], now: datetime | None = None) -> WeeklyOverview:
    """Bucket activities into the last 6 ISO weeks (Monday-Sunday), including
    the current, in-progress week. All sport types are included - unlike
    build_overview, there is no category filtering here.
    """
    today = (now or datetime.now()).date()
    current_monday = _monday_of(today)
    mondays = [current_monday - timedelta(weeks=i) for i in range(5, -1, -1)]

    buckets: dict[date, list[dict]] = {monday: [] for monday in mondays}
    for act in activities:
        raw = act.get("start_date_local") or act.get("start_date")
        if not raw:
            continue
        monday = _monday_of(_local_date(raw))
        if monday in buckets:
            buckets[monday].append(act)

    weeks: list[WeekStats] = []
    for i, monday in enumerate(mondays):
        acts = buckets[monday]
        iso_year, iso_week, _ = monday.isocalendar()

        hr_weighted_sum = 0.0
        hr_weight = 0
        days = set()
        for act in acts:
            hr = act.get("average_heartrate")
            if hr:
                weight = act.get("moving_time", 0)
                hr_weighted_sum += hr * weight
                hr_weight += weight
            days.add(_local_date(act.get("start_date_local") or act.get("start_date")))

        weeks.append(WeekStats(
            iso_week=iso_week,
            year=iso_year,
            start_date=monday,
            end_date=monday + timedelta(days=6),
            distance_m=sum(a.get("distance", 0) for a in acts),
            elevation_m=sum(a.get("total_elevation_gain", 0) for a in acts),
            moving_time_s=sum(a.get("moving_time", 0) for a in acts),
            avg_heartrate_bpm=(hr_weighted_sum / hr_weight) if hr_weight else None,
            activity_count=len(acts),
            days_with_activity=len(days),
            is_current=(i == len(mondays) - 1),
        ))

    current_week = weeks[-1]
    previous_weeks = weeks[:-1]  # 5 previous COMPLETED weeks
    previous_mondays = mondays[:-1]

    avg_distance_m = sum(w.distance_m for w in previous_weeks) / len(previous_weeks)
    avg_elevation_m = sum(w.elevation_m for w in previous_weeks) / len(previous_weeks)

    # Weighted directly over the underlying activities (not over per-week
    # averages) so weeks mixing HR and non-HR activities don't get diluted.
    hr_weighted_sum = 0.0
    hr_weight = 0
    for monday in previous_mondays:
        for act in buckets[monday]:
            hr = act.get("average_heartrate")
            if hr:
                weight = act.get("moving_time", 0)
                hr_weighted_sum += hr * weight
                hr_weight += weight
    avg_heartrate_bpm = (hr_weighted_sum / hr_weight) if hr_weight else None

    return WeeklyOverview(
        weeks=weeks,
        current_week=current_week,
        avg_distance_m=avg_distance_m,
        avg_elevation_m=avg_elevation_m,
        avg_heartrate_bpm=avg_heartrate_bpm,
        total_distance_m=sum(w.distance_m for w in weeks),
        total_elevation_m=sum(w.elevation_m for w in weeks),
        total_activities=sum(w.activity_count for w in weeks),
        date_range_start=weeks[0].start_date,
        date_range_end=current_week.end_date,
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
