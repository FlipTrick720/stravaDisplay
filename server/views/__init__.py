"""Per-view render functions.

    from views import render_dashboard, render_overview, render_weekly, render_error

render_error stays defined in renderer.py (it's shared error-screen furniture,
not a Strava data view); render_dashboard and render_overview were moved here
verbatim from renderer.py in Phase 2 Step 2 and still reach back into
renderer.* for shared drawing helpers. render_weekly is the first view built
directly on components/.
"""
from renderer import render_error
from .activity import render_dashboard
from .overview import render_overview
from .weekly import render_weekly

__all__ = ["render_dashboard", "render_overview", "render_weekly", "render_error"]
