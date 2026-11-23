"""`status.military` (runtime v346, military.lua): what of it ends a run of quiet turns and what the briefing warns of.

The user, 2026-11-23: "giving the LLM the info it needs in real time". Live, small-king-venice-a, Sonnet 5.5: Venice
held two Warriors and a Scout beside the Zulus at turn 88 and was told of an army only when it stood 4 plots from the
city, at war; the city fell on turn 95. The status of the seat's own turn now carries the Demographics screen's
Soldiers row, the armies of other players in sight near its cities (at peace too) and the state of each city under
threat; this module is the Python half: the record of one status, the difference between two, and the briefing rows.
Facts only: nothing here says what to do about them.
"""
from __future__ import annotations

#: A civilization at peace whose units near my cities grew by this many since the previous turn wakes a quiet run.
GROWTH = 2
#: The words of the diplomacy list that end a quiet run when a leader's changes to one of them, and that the briefing lists.
WARY = ("HOSTILE", "GUARDED", "WAR")
#: The briefing warns of my Soldiers figure when it is the lowest, or the highest is this many times mine.
FAR_BEHIND = 2


def record(ts: dict) -> dict | None:
    """What one status says, kept to compare the next turn's against: {turn, forces {civ: [units, at_war]},
    cities {id: [name, hp]}, last (my Soldiers figure is the lowest and the highest is half again mine), approach
    {civ: word}}. None for a status without the block (an older
    runtime, another player's turn, the main menu)."""
    m = ts.get("military") if isinstance(ts, dict) else None
    if not isinstance(m, dict) or not isinstance(ts.get("turn"), int):
        return None
    forces = {}
    for r in m.get("forces") or []:
        if isinstance(r, dict) and r.get("civ") and isinstance(r.get("units"), int) and r.get("player_id") is not None:
            forces[str(r["civ"])] = [r["units"], bool(r.get("at_war"))]
    cities = {}
    for c in m.get("cities") or []:
        if isinstance(c, dict) and c.get("id") is not None and isinstance(c.get("hp"), int):
            cities[str(c["id"])] = [str(c.get("name")), c["hp"]]
    s = m.get("soldiers") if isinstance(m.get("soldiers"), dict) else {}
    # The lowest by a margin (the highest half again mine): two armies of the same size swap ranks turn by turn.
    last = isinstance(s.get("of"), int) and s["of"] >= 2 and s.get("rank") == s["of"] \
        and isinstance(s.get("mine"), int) and isinstance(s.get("best"), int) and 2 * s["best"] >= 3 * s["mine"]
    approach = {str(k): str(v) for k, v in (m.get("approach") or {}).items()} if isinstance(m.get("approach"), dict) else {}
    return {"turn": ts["turn"], "forces": forces, "cities": cities, "last": bool(last), "approach": approach}


def as_record(kept) -> dict | None:
    """A stored record back, or None for anything else (an older notebook, a hand-edited one)."""
    if isinstance(kept, dict) and isinstance(kept.get("turn"), int) and isinstance(kept.get("forces"), dict) \
            and isinstance(kept.get("cities"), dict):
        return kept
    return None


def wake_reasons(rec: dict | None, prev: dict | None) -> list[str]:
    """Why `rec` is not a quiet turn. An army of a civilization at war with me in sight near a city never is, with
    or without a baseline. Against the previous turn's record: an army at peace that appeared or grew by GROWTH, a
    city newly listed or with fewer hit points, my Soldiers figure becoming the lowest, and a leader's word on the
    diplomacy list changing to one of WARY."""
    if not rec:
        return []
    out: list[str] = []
    known = prev is not None and prev["turn"] < rec["turn"]
    for civ in sorted(rec["forces"]):
        units, war = rec["forces"][civ]
        was = ((prev["forces"].get(civ) if known else None) or [0, False])[0]
        if war:
            out.append(f"enemy_forces_near:{civ}:{units}")
        elif known and (was == 0 or units - was >= GROWTH):
            out.append(f"foreign_forces_near:{civ}:{was}->{units}")
    if not known:
        return out
    for cid in sorted(rec["cities"]):
        name, hp = rec["cities"][cid]
        before = prev["cities"].get(cid)
        if before is None:
            out.append(f"city_threatened:{name}")
        elif isinstance(before, list) and len(before) == 2 and isinstance(before[1], int) and hp < before[1]:
            out.append(f"city_damaged:{name}:{before[1]}->{hp}")
    if rec["last"] and not prev.get("last"):
        out.append("soldiers_rank_lowest")
    before = prev.get("approach") if isinstance(prev.get("approach"), dict) else {}
    for civ in sorted(rec.get("approach") or {}):
        now = rec["approach"][civ]
        if now in WARY and civ in before and before[civ] != now:
            out.append(f"approach_changed:{civ}:{before[civ]}->{now}")
    return out


def _types(row: dict) -> str:
    types = row.get("types") if isinstance(row.get("types"), dict) else {}
    return ", ".join(f"{n} {t}" for t, n in sorted(types.items(), key=lambda kv: (-kv[1], kv[0])))


def warnings(ts: dict) -> list[dict]:
    """The briefing's rows from `status.military`: `military_standing` when my Soldiers figure is the lowest or the
    highest is FAR_BEHIND times mine, `foreign_forces_near` / `enemy_forces_near` for each army of another
    civilization in sight near my cities (the barbarians are the briefing's `threats`), `city_threatened` for each
    city damaged or with hostile units close, `wary_leaders` when the diplomacy list shows a leader as one of WARY,
    `enemy_city_in_reach` for each enemy city in sight near my units. Each row carries the status row and a
    sentence with the figures."""
    m = ts.get("military") if isinstance(ts, dict) else None
    if not isinstance(m, dict):
        return []
    out: list[dict] = []
    s = m.get("soldiers") if isinstance(m.get("soldiers"), dict) else None
    if s and all(isinstance(s.get(k), int) for k in ("mine", "rank", "of", "best", "average")) and s["of"] >= 2 \
            and s["best"] > s["mine"] and (s["rank"] == s["of"] or s["best"] >= FAR_BEHIND * s["mine"]):
        whose = f"{s['best_civ']}'s" if s.get("best_civ") else "an unmet civilization's"
        times = f", {s['best'] / s['mine']:.1f} times yours" if s["mine"] > 0 else ""
        out.append({"kind": "military_standing", **s, "combat_units": m.get("combat_units"),
                    "note": (f"Soldiers on the Demographics screen: yours {s['mine']}, rank {s['rank']} of {s['of']}; the "
                             f"highest is {whose} {s['best']}{times}; the average is {s['average']}. You have "
                             f"{m.get('combat_units')} combat unit(s). status.military carries the row on every turn; "
                             "state(what='empire', view='demographics') is the screen")})
    for r in m.get("forces") or []:
        if not isinstance(r, dict) or r.get("player_id") is None:
            continue
        near = r.get("nearest") if isinstance(r.get("nearest"), dict) else {}
        war = bool(r.get("at_war"))
        approach = f", approach towards you as the diplomacy list shows it: {r['approach_guess']}" if r.get("approach_guess") else ""
        out.append({"kind": "enemy_forces_near" if war else "foreign_forces_near", **r,
                    "note": (f"{r.get('units')} combat unit(s) of {r.get('civ')} in sight within 5 plots of your cities "
                             f"({_types(r)}), {'at war with you' if war else 'at peace with you'}{approach}; the nearest is "
                             f"{near.get('distance')} plot(s) from {near.get('city')}, {r.get('in_my_land')} stand inside your "
                             "borders")})
    for c in m.get("cities") or []:
        if not isinstance(c, dict):
            continue
        close = c.get("hostile_close") if isinstance(c.get("hostile_close"), dict) else None
        buy = c.get("can_buy") if isinstance(c.get("can_buy"), dict) else None
        said = f"{c.get('name')}: {c.get('hp')} of {c.get('max_hp')} hit points, strength {c.get('strength')}, " \
               f"{'garrison ' + str(c['garrison']) if c.get('garrison') else 'no unit garrisoned'}"
        if close:
            said += f"; {close.get('units')} hostile unit(s) within 3 plots ({_types(close)})"
        if buy:
            units = ", ".join(f"{u.get('item')} {u.get('gold')}" for u in buy.get("units") or [] if isinstance(u, dict))
            walls = ", ".join(f"{b.get('item')} {b.get('gold')}" for b in buy.get("buildings") or [] if isinstance(b, dict))
            cheapest = buy.get("cheapest_unit") if isinstance(buy.get("cheapest_unit"), dict) else None
            listed = "; ".join(x for x in (units, walls) if x)
            blocked = ", ".join(f"{u.get('item')} {u.get('gold')}" for u in buy.get("blocked") or [] if isinstance(u, dict))
            if blocked:
                listed = "; ".join(x for x in (f"no combat unit while one stands on the city's tile (a bought unit "
                                               f"appears there and a tile holds one; the gold covers {blocked})", walls) if x)
            if listed:
                said += f"; the treasury ({buy.get('gold')} gold) buys here now: {listed}"
            elif cheapest:
                said += (f"; the treasury ({buy.get('gold')} gold) buys no combat unit here: the cheapest is "
                         f"{cheapest.get('item')} at {cheapest.get('gold')}")
        out.append({"kind": "city_threatened", **c, "note": said})
    wary = {civ: word for civ, word in (m.get("approach") or {}).items() if word in WARY} \
        if isinstance(m.get("approach"), dict) else {}
    if wary:
        out.append({"kind": "wary_leaders", "approach": wary,
                    "note": "the diplomacy list's word for these leaders' approach towards you: "
                            + ", ".join(f"{civ} {word}" for civ, word in sorted(wary.items()))
                            + ". state(what='civ', id=<player>, view='summary') has each one's reasons"})
    for g in m.get("sieges") or []:
        if not isinstance(g, dict):
            continue
        mine = g.get("my_units_close") if isinstance(g.get("my_units_close"), dict) else {}
        theirs = g.get("enemy_units_close") if isinstance(g.get("enemy_units_close"), dict) else {}
        out.append({"kind": "enemy_city_in_reach", **g,
                    "note": (f"{g.get('city')} of {g.get('civ')}{' (its capital)' if g.get('capital') else ''} at "
                             f"({g.get('x')},{g.get('y')}): {g.get('hp')} of {g.get('max_hp')} hit points, strength "
                             f"{g.get('strength')}; within 3 plots of it you have {mine.get('units', 0)} combat unit(s)"
                             f"{' (' + _types(mine) + ')' if mine.get('units') else ''} and {theirs.get('units', 0)} of "
                             f"its owner's are in sight{' (' + _types(theirs) + ')' if theirs.get('units') else ''}")})
    return out
