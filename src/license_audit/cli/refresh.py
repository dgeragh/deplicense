"""The `refresh` CLI command, update bundled OSADL data."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen

import click
import platformdirs
from rich.console import Console

_MATRIX_URL = "https://www.osadl.org/fileadmin/checklists/matrix.json"
_COPYLEFT_URL = "https://www.osadl.org/fileadmin/checklists/copyleft.json"

_MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB


def get_cache_dir() -> Path:
    """Return the user-writable cache directory for OSADL data."""
    return Path(platformdirs.user_cache_dir("license_audit")) / "osadl"


@click.command("refresh")
def refresh_cmd() -> None:
    """Download the latest OSADL compatibility data."""
    console = Console()

    data_path = get_cache_dir()
    data_path.mkdir(parents=True, exist_ok=True)

    console.print("Downloading OSADL compatibility matrix...")
    _download(str(_MATRIX_URL), data_path / "osadl_matrix.json")
    console.print("[green]\\[/][/green] matrix.json updated")

    console.print("Downloading OSADL copyleft data...")
    _download(str(_COPYLEFT_URL), data_path / "copyleft.json")
    console.print("[green]\\[/][/green] copyleft.json updated")

    console.print(f"\nData saved to {data_path}")
    console.print("[bold green]OSADL data refreshed successfully.[/bold green]")


def _download(url: str, dest: Path) -> None:
    """Download a URL to a file, validating the response."""
    with urlopen(url, timeout=30) as resp:  # noqa: S310
        data = resp.read(_MAX_RESPONSE_BYTES + 1)
    if len(data) > _MAX_RESPONSE_BYTES:
        msg = f"Response from {url} exceeds {_MAX_RESPONSE_BYTES} bytes"
        raise RuntimeError(msg)
    # Validate that the response is valid JSON before writing
    json.loads(data)
    dest.write_bytes(data)
