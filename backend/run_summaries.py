#!/usr/bin/env python3
"""Regenerate summary markdown files in the Obsidian vault from SQLite data."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import generate_obsidian_summaries

if __name__ == "__main__":
    generate_obsidian_summaries()