"""Generate pi/fallback/no-server.png.

Build-time tool, run on a dev machine (needs server/ deps, which the Pi does
not have). The resulting PNG is committed so the Pi never needs to render.

Re-run after any change to renderer.render_error():

    python3 pi/make_fallback.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

import renderer  # noqa: E402

OUT = ROOT / "pi" / "fallback" / "no-server.png"


def main() -> None:
    img = renderer.render_error(
        heading="Warte auf Server...",
        error_message=(
            "Malte hat geflippt. Das Display kann den Server nicht erreichen "
            "und zeigt deshalb dieses Bild. Es versucht es alle paar Minuten "
            "erneut."
        ),
        technical_details=(
            "Kein zwischengespeichertes Bild vorhanden. "
            "Pruefe WLAN am Pi und ob der Server laeuft."
        ),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes, {img.size[0]}x{img.size[1]} mode={img.mode})")


if __name__ == "__main__":
    main()
