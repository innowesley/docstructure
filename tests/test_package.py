"""Packaging compatibility test — verifies the built package installs correctly.

Creates a fresh virtual environment, builds + installs the package, and
runs a basic smoke test. Run after packaging changes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent.parent


def test_package_build_and_install():
    """Build the package and install it in a fresh venv, then smoke-test."""
    with tempfile.TemporaryDirectory(prefix="docstructure_pkg_test_") as tmpdir:
        tmp = Path(tmpdir)
        venv_dir = tmp / ".venv"
        venv_python = venv_dir / ("bin/python" if sys.platform != "win32" else "Scripts/python.exe")

        # Create venv
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # Build sdist
        build_dir = tmp / "build"
        build_dir.mkdir()
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "build"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(PACKAGE_DIR)
        )
        subprocess.run(
            [sys.executable, "-m", "build", "--sdist", str(PACKAGE_DIR)],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(PACKAGE_DIR)
        )

        # Find sdist
        dist_dir = PACKAGE_DIR / "dist"
        sdists = list(dist_dir.glob("*.tar.gz"))
        if not sdists:
            sdists = list(dist_dir.glob("*.zip"))
        assert sdists, "No sdist found after build"

        sdist_path = str(sdists[0])

        # Install in venv
        subprocess.run([str(venv_python), "-m", "pip", "install", sdist_path],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # Smoke test
        result = subprocess.run(
            [str(venv_python), "-c", """
from docstructure import analyze, parse, detect_format, validate, serialize, to_json, to_file
from docstructure import __version__, __all__
print("Version:", __version__)
print("API:", __all__)
assert __version__ == "0.2.0"
assert set(__all__) == {'analyze', 'parse', 'detect_format', 'validate', 'serialize', 'to_json', 'to_file', '__version__'}
print("OK")
"""],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        print(result.stdout)

    # Clean up dist
    for f in dist_dir.glob("*"):
        f.unlink()
    dist_dir.rmdir()

    print("Package build + install test PASSED")


if __name__ == "__main__":
    test_package_build_and_install()
