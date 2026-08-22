"""Config loader for Strava Display.

Loads and saves config.json which holds Strava OAuth tokens and display settings.

Two sources, in priority order:

  1. STRAVA_CONFIG_DIR - directory holding config.json. Set to /data in
                         docker-compose (host side ./data).
  2. repo root         - local dev fallback, where setup_strava.py writes.

save() uses atomic write-then-rename to prevent corruption on power loss or
kernel kill mid-write. This matters because save() is called on every OAuth
token refresh (~every 6h) - over months of runtime, a non-atomic write will
eventually corrupt the file.
"""
import json
import os
import tempfile
from pathlib import Path

# Resolved at import time, so STRAVA_CONFIG_DIR must be set before this module
# is imported (it is, via docker-compose.yml `environment:`).
CONFIG_DIR = Path(os.environ.get("STRAVA_CONFIG_DIR", Path(__file__).parent.parent))
CONFIG_PATH = CONFIG_DIR / "config.json"


def load() -> dict:
    """Load config.json from CONFIG_PATH.

    Raises FileNotFoundError with a helpful message if the file is missing.
    Raises json.JSONDecodeError if the file exists but is malformed - caller
    should catch and handle (the file might be corrupted from a bad prior write).
    """
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"config.json not found at {CONFIG_PATH}. "
            "Copy config.example.json to config.json and fill in your Strava credentials."
        )
    with CONFIG_PATH.open() as f:
        return json.load(f)


def save(config: dict) -> None:
    """Atomically persist config back to config.json.

    Strategy:
      1. Write to a sibling temp file
      2. fsync() so bytes are physically on disk (not just in the page cache)
      3. os.replace() to rename atomically over the existing config

    On POSIX filesystems (ext4 on the Pi), replace() is guaranteed atomic:
    a reader will see either the old file or the new one, never a partial state.
    """
    target_dir = CONFIG_PATH.parent
    # Create temp in same directory so rename is atomic (cross-fs rename isn't)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".config.",
        suffix=".tmp",
        dir=target_dir,
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(config, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, CONFIG_PATH)
    except Exception:
        # Clean up temp file if anything failed before the rename
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


if __name__ == "__main__":
    # Smoke test: round-trip
    cfg = load()
    print(f"Loaded config from {CONFIG_PATH}")
    print(f"Keys: {list(cfg.keys())}")
    print(f"Strava client_id: {cfg['strava']['client_id']}")

    save(cfg)
    cfg2 = load()
    assert cfg == cfg2, "Round-trip failed"
    print("Atomic save round-trip: ok")
