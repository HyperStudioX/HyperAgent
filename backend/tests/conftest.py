"""Pytest configuration and fixtures."""

import sys
from pathlib import Path

# Add the api directory to the path so imports work correctly
api_dir = Path(__file__).parent.parent
sys.path.insert(0, str(api_dir))
