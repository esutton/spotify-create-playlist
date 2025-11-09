"""Generate queries.txt using ShazamKit (macOS only).

This is a thin Python wrapper that builds and runs a small Swift command-line tool
that uses ShazamKit to identify audio segments. It mimics `fingerprint_to_queries.py`
behaviour: split/segmenting is not performed in Python here; instead the Swift CLI
attempts to match the provided audio file and prints matching Title - Artist lines.

Requirements
- macOS 12+
- Xcode toolchain (swift) available in PATH
- ShazamKit is available on the platform

Usage
-----
python src/fingerprint_shazam_queries.py /path/to/radio_capture.mp3 --output queries.txt

If no matches are found, the output file will be created but may contain no queries.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from typing import List


def build_shazam_cli(workdir: str) -> str:
    """Build the Swift Shazam CLI using `swift build --configuration release`.

    Returns path to executable on success.
    """
    pkg_dir = os.path.join(workdir, "tools", "shazam_cli")
    # Ensure swift is available
    if shutil.which("swift") is None:
        raise RuntimeError("`swift` not found in PATH. Install Xcode or Swift toolchain.")

    # Build release executable
    print("Building Shazam CLI (this may take a moment)...")
    subprocess.check_call(["swift", "build", "-c", "release"], cwd=pkg_dir)

    # built executable location
    exe_path = os.path.join(pkg_dir, ".build", "release", "shazamcli")
    if not os.path.exists(exe_path):
        raise RuntimeError(f"Expected built executable not found at {exe_path}")
    return exe_path


def run_shazam_cli(exe_path: str, input_path: str) -> List[str]:
    proc = subprocess.run([exe_path, input_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        # include stderr in error
        raise RuntimeError(f"shazamcli failed: {proc.stderr.strip()}")
    # parse stdout lines
    lines = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
    return lines


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Use ShazamKit (Swift CLI) to produce queries.txt")
    p.add_argument("input", help="Input audio file (mp3) containing radio capture")
    p.add_argument("--output", "-o", default="queries.txt", help="Output queries file (one per line)")
    p.add_argument("--rebuild", action="store_true", help="Force rebuild of Swift CLI")
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(list(argv) if argv is not None else None)

    # Platform check
    if platform.system() != "Darwin":
        print("ShazamKit is only available on macOS. This script must run on macOS.")
        return 3

    # Validate input
    if not os.path.exists(args.input):
        print(f"Input file not found: {args.input}")
        return 2

    # Build or locate executable
    exe_path = os.path.join(os.getcwd(), "tools", "shazam_cli", ".build", "release", "shazamcli")
    try:
        if args.rebuild or not os.path.exists(exe_path):
            exe_path = build_shazam_cli(os.getcwd())
    except Exception as e:
        print(f"Failed to build Shazam CLI: {e}")
        return 4

    try:
        lines = run_shazam_cli(exe_path, args.input)
    except Exception as e:
        print(f"Error running shazamcli: {e}")
        return 5

    # Write queries to output file
    with open(args.output, "w", encoding="utf-8") as fh:
        for l in lines:
            fh.write(l + "\n")

    print(f"Wrote {len(lines)} queries to {args.output}")
    for l in lines:
        print(l)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
