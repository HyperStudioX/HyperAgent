#!/usr/bin/env python3
"""Pull all Docker images required by the BoxLite local sandbox provider.

Reads image names from .env (or falls back to defaults) and pulls them
via `docker pull`.
"""

import subprocess
import sys
from pathlib import Path

# Defaults matching app/config.py
DEFAULTS = {
    "BOXLITE_CODE_IMAGE": "python:3.12-slim",
    "BOXLITE_DESKTOP_IMAGE": "boxlite/desktop:latest",
    "BOXLITE_APP_IMAGE": "node:20-slim",
}


def load_env(env_path: Path) -> dict[str, str]:
    """Parse a .env file into a dict (simple key=value, ignores comments)."""
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def get_images() -> list[tuple[str, str]]:
    """Return (label, image) tuples from .env or defaults."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    env = load_env(env_path)

    return [
        ("Code execution", env.get("BOXLITE_CODE_IMAGE", DEFAULTS["BOXLITE_CODE_IMAGE"])),
        ("Desktop / browser", env.get("BOXLITE_DESKTOP_IMAGE", DEFAULTS["BOXLITE_DESKTOP_IMAGE"])),
        ("App development", env.get("BOXLITE_APP_IMAGE", DEFAULTS["BOXLITE_APP_IMAGE"])),
    ]


def check_docker() -> bool:
    """Check that Docker is available and running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
    except subprocess.TimeoutExpired:
        return False


def pull_image(image: str) -> bool:
    """Pull a single Docker image. Returns True on success."""
    result = subprocess.run(
        ["docker", "pull", image],
        timeout=600,
    )
    return result.returncode == 0


def main() -> int:
    if not check_docker():
        print(
            "Error: Docker is not available. "
            "Make sure Docker is installed and the daemon is running.",
            file=sys.stderr,
        )
        return 1

    images = get_images()
    total = len(images)
    failed: list[str] = []

    print(f"Pulling {total} BoxLite Docker images...\n")

    for i, (label, image) in enumerate(images, 1):
        print(f"[{i}/{total}] {label}: {image}")
        if pull_image(image):
            print(f"  -> OK\n")
        else:
            print(f"  -> FAILED\n", file=sys.stderr)
            failed.append(image)

    if failed:
        print(f"\n{len(failed)} image(s) failed to pull:", file=sys.stderr)
        for img in failed:
            print(f"  - {img}", file=sys.stderr)
        return 1

    print(f"All {total} images pulled successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
