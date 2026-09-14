#!/usr/bin/env python3
"""Process files in the Inbox folder: analyze, sort, create proxy notes."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import process_inbox

if __name__ == "__main__":
    processed = process_inbox()
    print(f"Processed {len(processed)} inbox files.")