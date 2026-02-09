"""Pytest configuration for shared test fixtures and path setup."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repository root is available on sys.path for package imports during tests.
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
