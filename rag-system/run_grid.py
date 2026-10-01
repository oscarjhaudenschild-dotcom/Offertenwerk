#!/usr/bin/env python3
"""
Run the full measurement grid and write one combined CSV.

    python3 run_grid.py                     baseline, letterhead indexed as-is
    python3 run_grid.py --strip-letterhead   comparison run, letterhead removed

4 corpus sizes x 4 values of k x 3 repeats x 2 noise designs.

k is varied because a fixed k=3 turned out to be the dominant limit: with no
distractors at all the hit rate stopped at 27 percent, while k=20 reached 98.
Reporting a degradation curve at one k would have described that ceiling rather
than the effect of the noise.
"""

import csv
import subprocess
import sys
import time
from pathlib import Path

LEVELS = "10,50,100,200"
K_VALUES = [3, 5, 10, 20]
MODES = ["unrelated", "confusable"]
RUNS = 3


def main() -> int:
    strip = "--strip-letterhead" in sys.argv
    out = Path("measurements/results_grid_no_letterhead.csv" if strip
               else "measurements/results_grid.csv")
    gold = "measurements/gold_set_no_letterhead.json" if strip else "measurements/gold_set.json"
    out.parent.mkdir(exist_ok=True)
    tmp = Path("/tmp/_grid_part.csv")
    rows, header = [], None
    started = time.time()

    for mode in MODES:
        for k in K_VALUES:
            print(f"  {mode:11} k={k:<3} ", end="", flush=True)
            t0 = time.time()
            cmd = [sys.executable, "run_experiment.py",
                   "--noise-levels", LEVELS, "--runs", str(RUNS),
                   "--k", str(k), "--noise-mode", mode, "--out", str(tmp),
                   "--gold-set", gold]
            if strip:
                cmd.append("--strip-letterhead")
            code = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if code != 0:
                print("FEHLGESCHLAGEN")
                return code
            with open(tmp, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                header = header or reader.fieldnames
                part = list(reader)
            rows.extend(part)
            print(f"{len(part):>4} Zeilen  {time.time() - t0:5.1f}s")

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{len(rows)} Zeilen -> {out}")
    print(f"Gesamtdauer: {time.time() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
