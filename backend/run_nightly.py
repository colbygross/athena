#!/usr/bin/env python3
"""
Nightly pipeline: daily brief (today) → daily summary (archive yesterday) → rolling summaries.
Runs after inbox processing completes.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import generate_daily_brief, generate_daily_summary, generate_obsidian_summaries

if __name__ == "__main__":
    print("=== NIGHTLY SUMMARY PIPELINE ===")
    print("1/3 Daily Brief (today)...")
    generate_daily_brief()
    print("2/3 Daily Summary (archive yesterday)...")
    generate_daily_summary()
    print("3/3 Rolling summaries...")
    generate_obsidian_summaries()
    print("=== PIPELINE COMPLETE ===")