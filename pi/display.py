"""Minimal e-paper client.

Fetches pre-rendered PNGs from the server and pushes them to the Waveshare
7.5" V2 panel. No Strava calls, no rendering, no aggregation: all of that lives
on the server. See CLAUDE.md "API-first rendering".

Two responsibilities, kept separate on purpose:
  fetch_or_cached(view) -> PIL.Image   network + cache + fallback
  push_to_display(img)                 hardware

Run:
  python3 display.py        loop forever
  python3 display.py once   one fetch + push, then exit (for testing)
"""
import io
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

import requests
import yaml
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,          # systemd/journald captures stdout
)
log = logging.getLogger("display")

HERE = Path(__file__).parent
CONFIG_PATH = HERE / "config.yaml"
FALLBACK_PATH = HERE / "fallback" / "no-server.png"

PANEL_SIZE = (800, 480)

DEFAULTS = {
    "server_url": "https://strava-display.maltebraig.com",
    "refresh_interval_seconds": 300,
    "views": ["weekly", "overview", "activity"],
    "cache_path": "/home/flip/.cache/strava-display/current.png",
    "request_timeout_seconds": 30,
}


def load_config() -> dict:
    """Read config.yaml, falling back to DEFAULTS for anything absent."""
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        loaded = yaml.safe_load(CONFIG_PATH.read_text()) or {}
        cfg.update({k: v for k, v in loaded.items() if v is not None})
    else:
        log.warning("%s not found, using defaults", CONFIG_PATH)
    cfg["server_url"] = str(cfg["server_url"]).rstrip("/")
    return cfg


def _normalize(img: Image.Image) -> Image.Image:
    """Force the panel's exact geometry and bit depth."""
    if img.size != PANEL_SIZE:
        log.warning("Image is %s, expected %s, resizing", img.size, PANEL_SIZE)
        img = img.resize(PANEL_SIZE)
    if img.mode != "1":
        img = img.convert("1")
    return img


def _write_cache(path: Path, data: bytes) -> None:
    """Atomic write, so a power cut mid-write cannot leave a truncated cache."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".current.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def fetch_or_cached(cfg: dict, view: str) -> Image.Image:
    """Fetch one view, falling back to the cache and then the static image.

    Never raises: the panel must always get something to show.
    """
    url = f"{cfg['server_url']}/display/{view}.png"
    cache_path = Path(cfg["cache_path"])

    try:
        resp = requests.get(url, timeout=cfg["request_timeout_seconds"])
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        img.load()                       # force decode now, inside the try
        generated = resp.headers.get("X-Generated-At", "unknown")
        log.info("Fetched %s (%d bytes, server rendered at %s)",
                 view, len(resp.content), generated)
        try:
            _write_cache(cache_path, resp.content)
        except OSError as e:
            log.warning("Could not write cache %s: %s", cache_path, e)
        return _normalize(img)
    except Exception as e:
        log.warning("Fetch failed for %s (%s: %s)", view, type(e).__name__, e)

    if cache_path.exists():
        try:
            img = Image.open(cache_path)
            img.load()
            age = time.time() - cache_path.stat().st_mtime
            log.info("Using cached image (%.0f min old)", age / 60)
            return _normalize(img)
        except Exception as e:
            log.warning("Cached image unreadable (%s), falling through", e)

    log.warning("No cache, using static fallback %s", FALLBACK_PATH)
    return _normalize(Image.open(FALLBACK_PATH))


def push_to_display(img: Image.Image) -> None:
    """Send a PIL image to the panel.

    Imported inside the function so this module stays importable off-Pi
    (waveshare_epd is not installable on a dev machine).
    """
    from waveshare_epd import epd7in5_V2

    epd = epd7in5_V2.EPD()
    epd.init()
    epd.display(epd.getbuffer(img))
    epd.sleep()


def main_loop(cfg: dict) -> None:
    views = cfg["views"]
    interval = cfg["refresh_interval_seconds"]
    log.info("Server %s, %d views, %ds per view", cfg["server_url"], len(views), interval)

    index = 0
    while True:
        started = time.time()
        view = views[index % len(views)]
        index += 1

        img = fetch_or_cached(cfg, view)
        try:
            push_to_display(img)
            log.info("Displayed %s", view)
        except Exception as e:
            log.exception("Display push failed (%s)", type(e).__name__)

        elapsed = time.time() - started
        sleep_for = max(0, interval - elapsed)
        log.info("Cycle took %.1fs, sleeping %.0fs", elapsed, sleep_for)
        time.sleep(sleep_for)


if __name__ == "__main__":
    config = load_config()

    if len(sys.argv) > 1 and sys.argv[1] == "once":
        first = config["views"][0]
        image = fetch_or_cached(config, first)
        out = HERE / "preview.png"
        image.save(out)
        log.info("Saved %s", out)
        try:
            push_to_display(image)
            log.info("Pushed %s to display", first)
        except Exception as exc:
            log.warning("Could not push to display (%s: %s). "
                        "Expected if not running on the Pi.", type(exc).__name__, exc)
    else:
        main_loop(config)
