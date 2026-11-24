"""The tactical view's legend, said once (GitLab #152).

The legend of `state(what="unit", view="tactical")` is prose that never changes between reads, and a seat read it
on every move check (about two thousand characters a time, four times in a Grok seat's opening turns). It lives in
docs/TOOL_REPLIES.md as the view's reply reference, where `reference(book="playbook", section=...)` serves it. A
server process attaches the whole text to its first tactical reply (`legend`) and nothing after that. Until
2026-11-23 every later reply carried a one-line `key` (300 characters, with the section's name): a Codex seat read
the view 73 times in thirty turns and each key was sent again with every later request of its instance. The legend
names its own section, the playbook's index lists it, and a seat loop's instance has a server of its own, so its
first read brings the legend. A reader whose context was reset under a server that lives on gets it back two ways:
`turn(action="briefing", since="turn")`, the read the instructions name for that moment, makes the next tactical
reply carry the legend again (`forget`), and `reference(section="legend")` returns it at any time (`NAMES`).
"""
from __future__ import annotations

from . import guide

#: The reply reference's heading in docs/TOOL_REPLIES.md, and the section name a reader passes to reference().
TOPIC = 'state(what="unit", view="tactical")'

#: The one-line key: enough to read the grid and the `move` column without the legend (a city is the cell's ground, GitLab
#: #177; an open step's cost, GitLab #180). It stands in for the legend where docs/ is not installed (`text`).
KEY = ("cell = ground+occupant: M mountain ~ water H hills F forest . open C city _ unrevealed | @ this unit X hostile "
       "u yours o other ? fogged; move: attack / open (cost, left, zoc) / refused (why) / enemy; "
       "reach.plots: [x, y, left]; "
       f"the legend: reference(book='playbook', section='{TOPIC}')")


#: The short words that name the legend's section in `reference` (either book): harness/guide.py TOPIC_ALIASES.
NAMES = ("legend", "tactical")


def text() -> str:
    """The legend as the reply reference holds it (the heading dropped), or the key when docs/ is not installed."""
    body = guide.reply_topic(TOPIC)
    if not body:
        return KEY
    lines = body.strip().splitlines()
    return "\n".join(lines[1:]).strip() if lines and lines[0].startswith("## ") else body.strip()


def attach(reply: dict, seen: set[str]) -> dict:
    """`legend` the first time a process answers a tactical read, nothing after; `seen` is the process's memory."""
    if TOPIC not in seen:
        seen.add(TOPIC)
        reply["legend"] = text()
    return reply


def forget(seen: set[str] | None) -> None:
    """The process's memory of having said the legend, cleared: its next tactical reply carries it again."""
    if seen is not None:
        seen.discard(TOPIC)
