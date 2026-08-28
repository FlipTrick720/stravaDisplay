"""Render Strava data to 800x480 images for the e-paper display."""
from datetime import datetime
from pathlib import Path
from typing import Iterable
from math import cos, radians
import polyline as pl
from PIL import Image, ImageDraw, ImageFont

import cities

WIDTH, HEIGHT = 800, 480


FONT_DIR = "/usr/share/fonts/truetype/dejavu"


# =========================
# Shared helpers
# =========================

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"{FONT_DIR}/{name}", size)


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Simple word-wrap on whitespace.

    Returns list of lines, each not exceeding max_chars (as long as individual
    words fit).
    """
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = f"{current} {word}".strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# =========================
# Error screen (Windows XP homage)
# =========================

def render_error(
    error_message: str,
    technical_details: str | None = None,
    heading: str | None = None,
) -> Image.Image:
    """Render a Windows XP style error dialog for display failures.

    Fills the entire 800x480 area (no border, no interactive elements since
    the display isn't touch).

    heading: optional short line above the message (e.g. "Zu viel Watt registriert").
             If None, uses the classic "Strava Display hat ein Problem festgestellt".
    """
    img = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    # Title bar
    title_h = 40
    draw.rectangle([0, 0, WIDTH, title_h], fill=0)
    draw.text((16, 12), "Strava Display", font=_font(18, bold=True), fill=1)

    # [X] Close button (decorative only)
    x_box_size = 28
    x_box_x = WIDTH - x_box_size - 8
    x_box_y = (title_h - x_box_size) // 2
    draw.rectangle(
        [x_box_x, x_box_y, x_box_x + x_box_size, x_box_y + x_box_size],
        outline=1, fill=1,
    )
    draw.line([(x_box_x + 7, x_box_y + 7),
               (x_box_x + x_box_size - 7, x_box_y + x_box_size - 7)], fill=0, width=2)
    draw.line([(x_box_x + x_box_size - 7, x_box_y + 7),
               (x_box_x + 7, x_box_y + x_box_size - 7)], fill=0, width=2)

    # Content area
    content_top = title_h + 40

    # Big [X] warning icon
    icon_x = 60
    icon_y = content_top
    icon_size = 90
    draw.ellipse(
        [icon_x, icon_y, icon_x + icon_size, icon_y + icon_size],
        outline=0, width=4,
    )
    inset = 22
    draw.line(
        [(icon_x + inset, icon_y + inset),
         (icon_x + icon_size - inset, icon_y + icon_size - inset)],
        fill=0, width=6,
    )
    draw.line(
        [(icon_x + icon_size - inset, icon_y + inset),
         (icon_x + inset, icon_y + icon_size - inset)],
        fill=0, width=6,
    )

    # Heading (right of icon)
    text_x = icon_x + icon_size + 40
    text_y = content_top

    if heading:
        # Custom heading (word-wrap in case it's long)
        heading_lines = _wrap_text(heading, max_chars=32)
        for i, line in enumerate(heading_lines[:2]):
            draw.text((text_x, text_y + i * 32),
                      line, font=_font(22, bold=True), fill=0)
        heading_end_y = text_y + len(heading_lines[:2]) * 32
    else:
        draw.text((text_x, text_y), "Strava Display hat ein Problem",
                  font=_font(22, bold=True), fill=0)
        draw.text((text_x, text_y + 32), "festgestellt und muss beendet werden.",
                  font=_font(22, bold=True), fill=0)
        heading_end_y = text_y + 64

    # Error message
    msg_y = heading_end_y + 30
    draw.text((text_x, msg_y), "Fehlermeldung:", font=_font(14), fill=0)
    wrapped = _wrap_text(error_message, max_chars=48)
    for i, line in enumerate(wrapped[:4]):
        draw.text((text_x, msg_y + 22 + i * 20), line, font=_font(14), fill=0)

    # Technical details (optional)
    if technical_details:
        tech_y = HEIGHT - 90
        draw.text((60, tech_y), "Technische Details:", font=_font(12), fill=0)
        tech_wrapped = _wrap_text(technical_details, max_chars=80)
        for i, line in enumerate(tech_wrapped[:2]):
            draw.text((60, tech_y + 16 + i * 14), line, font=_font(12), fill=0)

    # Status bar hint
    info_y = HEIGHT - 24
    draw.text((60, info_y), "Falls das Problem weiterhin besteht, wende dich bitte an "
              "deinen Systemadministrator (Malte).", font=_font(12), fill=0)

    return img


# =========================
# CLI
# =========================

if __name__ == "__main__":
    import sys
    import strava_client
    import aggregator
    from views import render_dashboard, render_overview

    mode = sys.argv[1] if len(sys.argv) > 1 else "overview"

    if mode == "error":
        import error_messages
        # Optional: category via 2nd arg
        category = sys.argv[2] if len(sys.argv) > 2 else "overload"
        heading, message = error_messages.get_error(category)
        img = render_error(
            error_message=message,
            heading=heading,
            technical_details=f"Category: {category} · sample technical detail here",
        )
        out = "preview_error.png"
    else:
        client = strava_client.StravaClient()
        if mode == "latest":
            activities = client.activities(per_page=1)
            if not activities:
                raise SystemExit("No activities found")
            activity_id = activities[0]["id"]
            activity = client.activity(activity_id)
            streams = client.activity_streams(activity_id)
            img = render_dashboard(activity, streams)
            out = "preview_latest.png"
        else:
            year_start = int(datetime(datetime.now().year, 1, 1).timestamp())
            activities = client.activities_since(year_start, per_page=100)
            overview = aggregator.build_overview(activities)
            athlete = client.athlete()
            name = f"{athlete['firstname']} {athlete['lastname']}"
            img = render_overview(overview, name)
            out = "preview_overview.png"

    output_path = Path(__file__).parent.parent / out
    img.save(output_path)
    print(f"Rendered {mode} to {output_path}")
