#!/usr/bin/env python3
"""
github-graph-writer
-------------------
Generates backdated git commits to spell a word/message
on your GitHub contribution graph.

Usage:
    python scripts/generate_commits.py --text "HELLO" [--year 2024] [--intensity 4]

The script works out which dates (weeks × days) map to each pixel
of the message, then creates empty commits on those dates.

GitHub's contribution graph:
  - X-axis = weeks (left → right, oldest → newest)
  - Y-axis = rows Sun(0) → Sat(6) top → bottom
  - Each letter uses 5 columns (weeks) + 1 column gap
  - Letters are 7 rows tall → fits perfectly in Sun–Sat (rows 0-6)
"""

import argparse
import subprocess
import sys
import os
from datetime import date, timedelta
from font import FONT


def get_start_date(year: int) -> date:
    """
    Find the Sunday that starts the contribution graph for a given year.
    GitHub's graph starts on the first Sunday on or before Jan 1.
    """
    jan1 = date(year, 1, 1)
    # weekday(): Mon=0 … Sun=6  →  isoweekday(): Mon=1 … Sun=7
    # We want the Sunday before or on Jan 1
    days_since_sunday = jan1.isoweekday() % 7  # Sun=0, Mon=1, …, Sat=6
    return jan1 - timedelta(days=days_since_sunday)


def text_to_pixel_columns(text: str):
    """
    Convert a string into a list of 7-tall columns (list of lists of bool).
    Each character = 5 columns, followed by 1 blank column spacer
    (except after the last character).
    """
    columns = []
    for char_idx, ch in enumerate(text.upper()):
        glyph = FONT.get(ch, FONT[' '])
        # glyph is 7 rows × 5 chars; we need 5 columns × 7 rows
        for col in range(5):
            column = [glyph[row][col] == 'X' for row in range(7)]
            columns.append(column)
        # Add spacer column between characters (not after last)
        if char_idx < len(text) - 1:
            columns.append([False] * 7)
    return columns


def columns_to_dates(columns, start_date: date, week_offset: int = 0):
    """
    Map pixel columns to actual calendar dates.
    Returns list of dates where a commit should be made.
    """
    commit_dates = []
    for col_idx, column in enumerate(columns):
        week = col_idx + week_offset
        for row_idx, filled in enumerate(column):
            if filled:
                # row 0 = Sunday, row 1 = Monday, …, row 6 = Saturday
                target_date = start_date + timedelta(weeks=week, days=row_idx)
                commit_dates.append(target_date)
    return commit_dates


def make_commit(commit_date: date, intensity: int, message: str, dry_run: bool):
    """
    Create `intensity` commits on a specific date using git commit --date.
    """
    date_str = commit_date.strftime("%Y-%m-%dT12:00:00")
    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = date_str
    env["GIT_COMMITTER_DATE"] = date_str

    for i in range(intensity):
        # Write a tiny file to have something to commit
        filepath = os.path.join("output", f"commit_{commit_date}_{i}.txt")
        if not dry_run:
            with open(filepath, "w") as f:
                f.write(f"{message} — {commit_date} #{i+1}\n")

            subprocess.run(["git", "add", filepath], check=True)
            subprocess.run(
                ["git", "commit", "--allow-empty", "-m", f"[graph] {message} {commit_date} {i+1}"],
                env=env,
                check=True,
            )
        else:
            print(f"  [dry-run] Would commit on {commit_date} (commit {i+1}/{intensity})")


def preview_art(columns, text):
    """Print an ASCII preview of what the graph will look like."""
    print(f"\nPreview for: '{text}'")
    print("=" * (len(columns) + 2))
    for row in range(7):
        line = "".join("█" if col[row] else " " for col in columns)
        print(f"|{line}|")
    print("=" * (len(columns) + 2))
    print(f"  → Needs {len(columns)} weeks of graph space\n")


def main():
    parser = argparse.ArgumentParser(
        description="Write text on your GitHub contribution graph via backdated commits."
    )
    parser.add_argument("--text", required=True, help="Word or message to write (A-Z, 0-3, spaces)")
    parser.add_argument("--year", type=int, default=date.today().year - 1,
                        help="Year to write in (default: last year)")
    parser.add_argument("--week-offset", type=int, default=2,
                        help="How many weeks from the start of the year to begin (default: 2)")
    parser.add_argument("--intensity", type=int, default=4, choices=[1, 2, 3, 4],
                        help="Commit intensity: 1=light, 2=medium, 3=dark, 4=darkest (default: 4)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview which dates would get commits, without making any")
    args = parser.parse_args()

    # Validate text
    unsupported = [ch for ch in args.text.upper() if ch not in FONT]
    if unsupported:
        print(f"⚠️  Unsupported characters: {set(unsupported)}")
        print(f"   Supported: A-Z, 0-3, space, ! and .")
        sys.exit(1)

    columns = text_to_pixel_columns(args.text)
    preview_art(columns, args.text)

    total_weeks_needed = len(columns) + args.week_offset
    if total_weeks_needed > 52:
        print(f"⚠️  Message needs {total_weeks_needed} weeks but a year only has ~52.")
        print("   Try a shorter message or smaller week-offset.")
        sys.exit(1)

    start_date = get_start_date(args.year)
    commit_dates = columns_to_dates(columns, start_date, week_offset=args.week_offset)

    print(f"📅  Graph year:     {args.year}")
    print(f"📆  Start date:     {start_date} (first Sunday of graph)")
    print(f"📝  Total commits:  {len(commit_dates) * args.intensity}")
    print(f"🎨  Intensity:      {args.intensity} commits/pixel")

    if args.dry_run:
        print("\n--- DRY RUN: no commits will be made ---")
        for d in sorted(set(commit_dates)):
            print(f"  {d}")
        print("\nRun without --dry-run to actually create commits.")
        return

    print("\n🚀 Creating commits...")
    for i, d in enumerate(commit_dates):
        make_commit(d, args.intensity, args.text, dry_run=False)
        if (i + 1) % 10 == 0:
            print(f"   {i+1}/{len(commit_dates)} pixels done...")

    print(f"\n✅ Done! {len(commit_dates) * args.intensity} commits created.")
    print("   Push with:  git push origin main")
    print("   The art will appear on your GitHub profile once pushed.")


if __name__ == "__main__":
    main()
