"""Config loader for Strava Display.

Loads and saves config.json which holds Strava OAuth tokens and display settings.
Kept intentionally simple - just a thin dict wrapper.
"""
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def load() -> dict:
    """Load config.json from repo root."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"config.json not found at {CONFIG_PATH}. "
            "Copy config.example.json to config.json and fill in your Strava credentials."
        )
    with CONFIG_PATH.open() as f:
        return json.load(f)


def save(config: dict) -> None:
    """Save config back to config.json (used to persist refreshed tokens)."""
    with CONFIG_PATH.open("w") as f:
        json.dump(config, f, indent=2)


if __name__ == "__main__":
    # Smoke test
    cfg = load()
    print(f"Loaded config with keys: {list(cfg.keys())}")
    print(f"Strava client_id: {cfg['strava']['client_id']}")
