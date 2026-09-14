#!/usr/bin/env python3
"""Generate the daily brief markdown file in the Obsidian vault."""
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import generate_daily_brief

if __name__ == "__main__":
    generate_daily_brief()