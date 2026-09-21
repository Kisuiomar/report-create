"""
Alias package to allow importing via `offline_dossier_pipeline.app...`
"""

import sys
from pathlib import Path

# Ensure root is in path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import app

__all__ = ["app"]
