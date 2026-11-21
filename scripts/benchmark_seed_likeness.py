#!/usr/bin/env python3
"""Are runs on seeds next to each other more alike at the end of their turns than runs on seeds far apart?

usage: benchmark_seed_likeness.py ROWS [ROWS ...] [--shuffles N]

A check on the seeds, not a part of a player's number: seeds are meant to be separate games, and two seeds that
use the same random numbers for the same things play alike (docs/BENCHMARK.md, "The seeds").

Each finished run is read where its turns ended: the seat's share of the living players' total in every
indicator (benchmark_fit.end_point_of). The distance between two runs is the sum over indicators of the squared
difference of the shares, each indicator scaled by its spread over all the runs. The likeness of a set of pairs
is 1 - (their mean distance / the mean distance of all other pairs): 0 when they differ as much as any two runs,
1 when they are the same position, below 0 when they differ more. The figure beside it is the share of N random
orderings of the same runs whose neighbours come out at least as alike: a small share says the order of the
seeds matters, which it should not.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_fit import end_point_of
from benchmark_run import mean_sd, read_rows

GAPS = (1, 2, 3)
FEWEST = 4


def points(rows: list[dict]) -> list[tuple[int, dict]]:
    """(seed, shares at the end of the turns) of every finished run that has them, in the order of the seeds."""
    out = []
    for r in rows:
        if r.get("result", "finished") != "finished":
            continue
        got = end_point_of(r)
        if got:
            out.append((r.get("run", len(out)), got[0]))
    return sorted(out, key=lambda p: p[0])


def distances(pts: list[tuple[int, dict]]) -> list[list[float]]:
    """The distance of every pair: squared differences of the shares, each indicator over its own spread. An
    indicator every run ended level on says nothing and is left out."""
    keys = [k for k in pts[0][1] if all(k in p[1] for p in pts)]
    sds = {k: mean_sd([p[1][k] for p in pts])[1] for k in keys}
    keys = [k for k in keys if sds[k] > 0]
    n = len(pts)
    return [[sum(((pts[i][1][k] - pts[j][1][k]) / sds[k]) ** 2 for k in keys) for j in range(n)] for i in range(n)]


def likeness(d: list[list[float]], order: list[int], gap: int) -> float:
    """1 - the mean distance of the pairs `gap` apart in `order` over the mean distance of every other pair."""
    n = len(order)
    near = [d[order[i]][order[i + gap]] for i in range(n - gap)]
    far = [d[order[i]][order[j]] for i in range(n) for j in range(i + 1, n) if j - i != gap]
    return 1 - (sum(near) / len(near)) / (sum(far) / len(far))


def likeness_lines(rows: list[dict], name: str = "", shuffles: int = 20000, rng: random.Random | None = None) -> list[str]:
    rng = rng or random.Random(1)
    pts = points(rows)
    if len(pts) < FEWEST:
        return [f"{name}: {len(pts)} finished runs, too few"]
    d = distances(pts)
    order = list(range(len(pts)))
    same = sum(1 for i in order for j in order if i < j and d[i][j] == 0)
    out = [f"{name}: {len(pts)} finished runs, seeds {pts[0][0]} to {pts[-1][0]}",
           f"  pairs that ended on the same shares: {same}"]
    if same == len(pts) * (len(pts) - 1) // 2:
        return out
    for gap in GAPS:
        if len(pts) <= gap + 1:
            continue
        seen = likeness(d, order, gap)
        at_least = 0
        for _ in range(shuffles):
            o = order[:]
            rng.shuffle(o)
            at_least += likeness(d, o, gap) >= seen
        out.append(f"  seeds {gap} apart ({len(pts) - gap} pairs): likeness {seen:+.3f}; "
                   f"{at_least / shuffles:.3f} of {shuffles} random orderings are at least as alike")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rows", nargs="+", type=Path)
    ap.add_argument("--shuffles", type=int, default=20000)
    a = ap.parse_args()
    for path in a.rows:        # the same orderings for a file whatever is read beside it
        print("\n".join(likeness_lines(read_rows(path), path.name, a.shuffles, random.Random(1))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
