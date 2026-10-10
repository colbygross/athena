#!/usr/bin/env python3
"""
Nightly pipeline:
1. Daily Archive (today): Archives today's events, completed tasks, transactions, and vitals; deletes today's brief.
2. Garbage Collection & Task Reset: Purges completed one-off tasks from DB and resets recurring tasks.
3. Daily Brief (tomorrow): Generates tomorrow's brief with schedule, tasks, and workout routine.
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agent

def run_nightly_pipeline():
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    print("=== NIGHTLY PIPELINE ===")
    print(f"1/3 Daily Archive (today: {today})...")
    agent.generate_daily_summary(target_date=today)

    print("2/3 Garbage collect completed tasks & reset recurring tasks...")
    agent.archive_and_reset_tasks_nightly(target_date=today)

    print(f"3/3 Daily Brief (tomorrow: {tomorrow})...")
    agent.generate_daily_brief(target_date=tomorrow)

    print("=== PIPELINE COMPLETE ===")

if __name__ == "__main__":
    run_nightly_pipeline()