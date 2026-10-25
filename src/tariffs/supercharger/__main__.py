"""Executable module entrypoint for python -m tariffs.supercharger."""

from __future__ import annotations

import sys

from tariffs.supercharger.cli import main

if __name__ == "__main__":
    sys.exit(main())
