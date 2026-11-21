#!/usr/bin/env python3
"""Fit the win-chance formula on games the engine played by itself, and value a player's turns by one read of where they end.

Rule 1 of docs/BENCHMARK.md values a position by the seat's chance to win from it. Playing that out costs about
ten seeds a side to tell 0.3 from 0.0 and every seed is 100 turns of a model's tokens. The engine's own games
cost none: `scripts/benchmark_run.py --path N` keeps every player's indicators every N turns of an AI finish, and
each such point with the game's outcome is a row here. The fit is a logistic regression of "the seat's team won"
on the seat's share of the living players' total in each named indicator, less an even share (so 0 is parity).

    scripts/benchmark_fit.py --fit logs/boards/duel-d/whole-path.jsonl --features score techs delegates \
        --model logs/boards/duel-d/win-chance.json
    scripts/benchmark_fit.py --model logs/boards/duel-d/win-chance.json --value logs/boards/duel-d/floor2-t100.jsonl

`--turns LO HI` fits on the points read in those turns only. What decides a game changes as it goes (on the
Celts duel delegates say nothing before turn 200 and most of it after 260), so a model meant for runs that
end by turn 100 is fitted on the turns such runs end in, and `--value` says when a run ended outside them.

A feature is an indicator or a route of benchmark_run (`score`, `delegates`), the same times the turn in hundreds
(`score*t`: a lead late is worth more than a lead early), or `t` alone. With no `--features` a few sets are
compared.

The game is the unit, not the point: a game's thirty points are one outcome. Every figure of merit is taken
leaving one game out (fitted on the others, scored on its points) and stands beside the same figure for the
base rate alone, which is what the win-chance formula has to beat. A run's row gives one point per decided
AI finish, all at the position its turns ended on, or the points of each finish's path, and a run's finishes are
left out together: they start from one position. AI finishes played later on a run's end save are in a rows file
of their own and are given with `--later`, which counts them with their run. A fit is of the starting saves
it was fitted on: the intercept is the seat's own edge there.

`--value` reads the point each run's turns ended on (`end_point`, or the seat's shares in a row older than
that) and gives the estimate beside the share of AI finishes won where the row has one, by player, with the standard
error over seeds. That error is the spread of the player's positions, not the model's own error, which is
given beside it: a jackknife over the fit's games (the estimate under each fit that leaves one game out, their
spread scaled up by the number of games). The range of those fits is not an error and is not printed: on nineteen
games it ran from 0.36 to 0.44 for runs that forty more games put at 0.49. Two players valued in one call
also get their difference, whose model error is taken on the difference itself, since one fit values both. The
estimate is as good as the fit, and AI finishes are what check it.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_run import DECIDED, INDICATORS, ROUTES, THE_SAVE, player_of, mean_sd, read_rows, with_later_finishes

KEYS = INDICATORS + ROUTES
SETS = (("score",), ("score", "score*t"), ("score", "techs", "cities"), ("score", "delegates", "allies"),
        ("score", "techs", "cities", "military", "delegates", "allies"))
BANDS = ((0, 50), (50, 100), (100, 200), (200, 10_000))


def shares_of(players: list[dict], seat: int) -> tuple[dict, int] | None:
    """The seat's share of the living players' total in every key the point has, and how many live. An indicator
    nobody has any of (delegates before a Congress sits) is an even share. None when the seat is dead."""
    living = [p for p in players if p["alive"]]
    me = next((p for p in living if p["id"] == seat), None)
    if me is None:
        return None
    out = {}
    for k in KEYS:
        if k in me:
            total = sum(max(p.get(k, 0), 0) for p in living)
            out[k] = max(me[k], 0) / total if total else 1 / len(living)
    return out, len(living)


def seat_of(row: dict, c: dict | None = None, seat: int | None = None) -> int | None:
    """The seat a game was played for: the AI finish's own, else the row's (a row that only values a save names
    none), else the one given by hand for rows older than both."""
    found = (c or {}).get("seat", row.get("seat"))
    return seat if found is None else found


def end_point_of(row: dict) -> tuple[dict, int, int] | None:
    """Where a run's turns ended: the seat's shares, the living, the turn. From the row's `end_point`, else from the
    seat's own view in a row older than that (the indicators only). None for a row with no turns played or a dead seat."""
    if row.get("end_point"):
        got = shares_of(row["end_point"]["players"], row["seat"])
        return (*got, row["end_point"]["turn"]) if got else None
    end = row.get("end") or {}
    if end.get("alive") and end.get("share") and end.get("of"):
        return dict(end["share"]), end["of"], end["turn"]
    return None


def points_of(rows: list[dict], name: str = "", seat: int | None = None) -> list[dict]:
    """Every position with an outcome in the rows: each point of a decided AI finish's path, or, for an
    AI finish that kept none, the position the run's turns ended on. `group` is what is left out together: a game
    of a save finished as it is (`--finish-only`), and all the AI finishes of a run, which start from one position
    and go together (the seed is the unit, docs/BENCHMARK.md rule 6)."""
    out = []
    for i, row in enumerate(rows):
        a_run = row.get("end_reason") != "finish_only" and player_of(row) != THE_SAVE
        for c in row.get("ai_finishes") or ():
            if c.get("end_reason") not in DECIDED:
                continue
            if c.get("path"):
                for pt in c["path"]:
                    got = shares_of(pt["players"], seat_of(row, c, seat))
                    if got:
                        out.append({"group": f"{name}:{i}" if a_run else f"{name}:{i}:{c['m']}", "turn": pt["turn"],
                                    "share": got[0], "n": got[1], "won": bool(c["won"])})
            else:
                got = end_point_of(row)
                if got:
                    out.append({"group": f"{name}:{i}", "turn": got[2], "share": got[0], "n": got[1], "won": bool(c["won"])})
    return out


def features_of(point: dict, features: tuple[str, ...]) -> list[float] | None:
    """The point as the model sees it, the constant first. None when the point lacks a named key."""
    x = [1.0]
    for f in features:
        key, _, by = f.partition("*")
        t = point["turn"] / 100
        if key == "t":
            x.append(t)
            continue
        if key not in point["share"]:
            return None
        lead = point["share"][key] - 1 / point["n"]
        x.append(lead * t if by == "t" else lead)
    return x


def sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def solve(a: list[list[float]], b: list[float]) -> list[float]:
    """a x = b by elimination with partial pivoting; a is small, symmetric and made positive by the ridge."""
    n = len(b)
    m = [[*a[i], b[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(col + 1, n):
            k = m[r][col] / m[col][col]
            for j in range(col, n + 1):
                m[r][j] -= k * m[col][j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (m[i][n] - sum(m[i][j] * x[j] for j in range(i + 1, n))) / m[i][i]
    return x


def fit(xs: list[list[float]], ys: list[bool], ridge: float = 1.0) -> list[float]:
    """Logistic regression by Newton's method. Each column is scaled to unit root mean square and the ridge is on
    the scaled coefficients, never on the constant; the coefficients come back in the features' own units. The
    ridge keeps a fit finite when a feature splits the games cleanly, which a few dozen games easily do."""
    k = len(xs[0])
    scale = [1.0] + [math.sqrt(sum(x[j] ** 2 for x in xs) / len(xs)) or 1.0 for j in range(1, k)]
    zs = [[x[j] / scale[j] for j in range(k)] for x in xs]
    b = [0.0] * k
    for _ in range(50):
        grad = [-ridge * b[j] if j else 0.0 for j in range(k)]
        hess = [[(ridge if i == j and i else 0.0) for j in range(k)] for i in range(k)]
        for z, y in zip(zs, ys):
            p = sigmoid(sum(bj * zj for bj, zj in zip(b, z)))
            w = max(p * (1 - p), 1e-9)
            for i in range(k):
                grad[i] += (y - p) * z[i]
                for j in range(i, k):
                    hess[i][j] += w * z[i] * z[j]
        for i in range(k):
            for j in range(i):
                hess[i][j] = hess[j][i]
        step = solve(hess, grad)
        b = [bj + sj for bj, sj in zip(b, step)]
        if max(abs(s) for s in step) < 1e-8:
            break
    return [b[j] / scale[j] for j in range(k)]


def predict(coef: list[float], x: list[float]) -> float:
    return sigmoid(sum(c * v for c, v in zip(coef, x)))


def fits_left_out(usable: list[tuple[dict, list[float]]], ridge: float = 1.0) -> dict[str, list[float]]:
    """For each game, the fit on every other game."""
    out = {}
    for g in sorted({p["group"] for p, _ in usable}):
        train = [(p, x) for p, x in usable if p["group"] != g]
        if train:
            out[g] = fit([x for _, x in train], [p["won"] for p, _ in train], ridge)
    return out


def left_out(points: list[dict], features: tuple[str, ...], ridge: float = 1.0) -> list[tuple[dict, float]]:
    """Every point with the chance given it by a fit that never saw its game."""
    usable = [(p, x) for p in points if (x := features_of(p, features)) is not None]
    fits = fits_left_out(usable, ridge)
    return [(p, predict(fits[p["group"]], x)) for p, x in usable if p["group"] in fits]


def merit(scored: list[tuple[dict, float]]) -> dict:
    """Log loss and Brier score of scored points, and the same by band of turns."""
    def of(pairs):
        if not pairs:
            return None
        ll = -sum(math.log(min(max(q if p["won"] else 1 - q, 1e-6), 1.0)) for p, q in pairs) / len(pairs)
        brier = sum((q - p["won"]) ** 2 for p, q in pairs) / len(pairs)
        return {"points": len(pairs), "log_loss": round(ll, 4), "brier": round(brier, 4)}
    out = of(scored) or {"points": 0}
    out["bands"] = {f"{lo}-{hi - 1}" if hi < 10_000 else f"{lo}+": m for lo, hi in BANDS
                    if (m := of([(p, q) for p, q in scored if lo <= p["turn"] < hi]))}
    return out


def fit_lines(points: list[dict], sets: tuple[tuple[str, ...], ...], ridge: float) -> tuple[list[str], dict | None]:
    """A table of the feature sets by what they give a game they never saw, and the best one fitted on everything."""
    games = sorted({p["group"] for p in points})
    won = len({p["group"] for p in points if p["won"]})
    lines = [f"{len(points)} points of {len(games)} games, the seat won {won}",
             f"{'features':<48} {'points':>6} {'log loss':>9} {'Brier':>7}   log loss by turn band"]
    best = None
    for features in ((), *sets):
        m = merit(left_out(points, features, ridge))
        if not m["points"]:
            lines.append(f"{' '.join(features):<48} no point has every feature")
            continue
        bands = "  ".join(f"{k} {v['log_loss']:.3f}" for k, v in m["bands"].items())
        lines.append(f"{' '.join(features) or '(the base rate alone)':<48} {m['points']:>6} {m['log_loss']:>9.4f} "
                     f"{m['brier']:>7.4f}   {bands}")
        if features and (best is None or m["log_loss"] < best[1]["log_loss"]):
            best = (features, m)
    if best is None:
        return lines, None
    usable = [(p, x) for p in points if (x := features_of(p, best[0])) is not None]
    coef = fit([x for _, x in usable], [p["won"] for p, _ in usable], ridge)
    model = {"features": list(best[0]), "coef": [round(c, 5) for c in coef], "ridge": ridge,
             "points": len(usable), "games": len({p["group"] for p, _ in usable}), "left_out": best[1],
             "left_out_coefs": [[round(c, 5) for c in f] for f in fits_left_out(usable, ridge).values()]}
    lines.append("fitted on every game: " + ", ".join(f"{n} {c:+.3f}" for n, c in zip(("constant", *best[0]), coef)))
    return lines, model


def jackknife(values: list[float]) -> float:
    """The standard error of a figure, from the same figure with each game in turn left out of the fit."""
    n, mean = len(values), sum(values) / len(values)
    return math.sqrt((n - 1) / n * sum((v - mean) ** 2 for v in values))


def runs_of(model: dict, rows: list[dict]) -> dict[str, dict]:
    """Each player's runs as the model sees them: the features of the point each ended on, the estimate
    there, the same mean under every fit that left a game out, and the share of AI finishes won where the row has one."""
    features = tuple(model["features"])
    lo, hi = model.get("turns") or (0, 10_000)
    out = {}
    for name in dict.fromkeys(player_of(r) for r in rows):
        w = {"xs": [], "est": [], "played": [], "outside": 0}
        for row in (r for r in rows if player_of(r) == name):
            got = end_point_of(row) if row.get("end_reason") == "all_turns_played" else None   # a run that did not finish has no value
            x = features_of({"share": got[0], "n": got[1], "turn": got[2]}, features) if got else None
            if x is None:
                continue
            w["outside"] += not lo <= got[2] <= hi
            w["xs"].append(x)
            w["est"].append(predict(model["coef"], x))
            if row.get("value") is not None:
                w["played"].append((w["est"][-1], row["value"]))
        w["left_out"] = [sum(predict(coef, x) for x in w["xs"]) / len(w["xs"])
                         for coef in (model.get("left_out_coefs") or ()) if w["xs"]]
        out[name] = w
    return out


def value_lines(model: dict, rows: list[dict]) -> list[str]:
    """Each player's runs valued by the model at the point their turns ended on, beside the share of AI finishes won."""
    lo, hi = model.get("turns") or (0, 10_000)
    lines = []
    for name, w in runs_of(model, rows).items():
        est, played = w["est"], w["played"]
        if not est:
            lines.append(f"{name}: no run with every feature of the model")
            continue
        mean, sd = mean_sd(est)
        line = f"{name}: estimate {mean:.3f} over {len(est)} seeds (standard error over seeds {sd / math.sqrt(len(est)):.3f}"
        if len(w["left_out"]) > 1:
            line += f", of the model {jackknife(w['left_out']):.3f} by a jackknife over its {len(w['left_out'])} games"
        line += ")"
        if played:
            line += (f"; AI finishes won {sum(v for _, v in played) / len(played):.3f} on {len(played)} of them, "
                     f"estimated {sum(e for e, _ in played) / len(played):.3f} there")
        if w["outside"]:
            line += f"; {w['outside']} ended outside turns {lo} to {hi}, which the model was fitted on"
        lines.append(line)
    return lines


def difference_lines(runs: dict[str, dict]) -> list[str]:
    """Each pair of players: the difference of their estimates, its error over seeds and the model's error, which
    is taken on the difference (one fit values both, so the two estimates move together) and then both together."""
    names = [n for n, w in runs.items() if w["est"]]
    lines = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            wa, wb = runs[a], runs[b]
            (ma, sa), (mb, sb) = mean_sd(wa["est"]), mean_sd(wb["est"])
            seeds = math.sqrt(sa ** 2 / len(wa["est"]) + sb ** 2 / len(wb["est"]))
            line = f"{a} less {b}: {ma - mb:+.3f} (standard error over seeds {seeds:.3f}"
            if len(wa["left_out"]) > 1:
                fit_se = jackknife([x - y for x, y in zip(wa["left_out"], wb["left_out"])])
                line += f", of the model {fit_se:.3f}, together {math.hypot(seeds, fit_se):.3f}"
            lines.append(line + ")")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fit", nargs="+", type=Path, metavar="ROWS", help="rows files whose decided games are fitted")
    ap.add_argument("--features", nargs="+", metavar="F", help="one feature set; without it several are compared")
    ap.add_argument("--seat", type=int, help="the seat of rows that name none (a save valued before 2026-11-18)")
    ap.add_argument("--turns", nargs=2, type=int, metavar=("LO", "HI"), help="fit on the points read in these turns only")
    ap.add_argument("--ridge", type=float, default=1.0, help="the penalty on the scaled coefficients (default 1)")
    ap.add_argument("--model", type=Path, help="with --fit the file the best fit is written to; with --value the one read")
    ap.add_argument("--value", nargs="+", type=Path, metavar="ROWS", help="rows files whose runs the model values")
    ap.add_argument("--later", nargs="+", type=Path, metavar="ROWS", default=[],
                    help="rows files of --finish-only runs on the end saves of runs in the --fit and --value files: their "
                         "AI finishes are counted with the run they were played from (given under --fit instead, each "
                         "would stand as a game of its own)")
    a = ap.parse_args(argv)
    if not a.fit and not (a.value and a.model):
        ap.error("give --fit ROWS, or --model FILE --value ROWS")
    later = [r for f in a.later for r in read_rows(f)]
    rows_of = lambda f: with_later_finishes(read_rows(f), later)[0]
    model = None
    if a.fit:
        lo, hi = a.turns or (0, 10_000)
        points = [p for f in a.fit for p in points_of(rows_of(f), f.stem, a.seat) if lo <= p["turn"] <= hi]
        if len({p["group"] for p in points}) < 3:
            print("fewer than three decided games in the rows: nothing to fit", file=sys.stderr)
            return 2
        lines, model = fit_lines(points, (tuple(a.features),) if a.features else SETS, a.ridge)
        print("\n".join(lines))
        if model and a.model:
            model["fitted_on"] = [str(f) for f in a.fit]
            if a.turns:
                model["turns"] = a.turns
            a.model.write_text(json.dumps(model, indent=1) + "\n")
    elif a.model:
        model = json.loads(a.model.read_text())
    if a.value and model:
        seen: dict[str, dict] = {}
        for f in a.value:
            rows = rows_of(f)
            print(f"{f}:")
            print("\n".join("  " + line for line in value_lines(model, rows)))
            for name, w in runs_of(model, rows).items():
                seen[f"{name} ({f.stem})" if name in seen else name] = w
        for line in difference_lines(seen):
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
