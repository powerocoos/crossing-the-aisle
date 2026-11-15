"""Fetch new roll call votes from the official House and Senate records, and refresh the roster.

Sources
  House:   https://clerk.house.gov/evs/{year}/roll{NNN}.xml
  Senate:  https://www.senate.gov/legislative/LIS/roll_call_votes/...
  Roster:  github.com/unitedstates/congress-legislators (public domain)
  Bills:   api.congress.gov summaries, only when CONGRESS_API_KEY is set

Usage
  python3 pipeline/fetch.py              fetch anything new, re-check the most recent few votes
  python3 pipeline/fetch.py --verify 25  also re-download the last 25 stored votes per chamber and
                                         report any difference from what is stored (changes nothing)
"""
import argparse
import html
import json
import os
import re
import sys
import urllib.error

from common import (CONGRESS, DATA, FIRST_YEAR, SESSIONS, VOTES_DIR, bill_key, http_get, read_json,
                    vote_id, vote_path, write_json)
from parse import parse_house, parse_senate, senate_menu_numbers

HOUSE_URL = "https://clerk.house.gov/evs/{year}/roll{roll:03d}.xml"
SENATE_MENU = "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_{c}_{s}.xml"
SENATE_URL = "https://www.senate.gov/legislative/LIS/roll_call_votes/vote{c}{s}/vote_{c}_{s}_{n:05d}.xml"
ROSTER_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/gh-pages/legislators-current.json"
SUMMARY_URL = "https://api.congress.gov/v3/bill/{c}/{t}/{n}/summaries?format=json"
REFRESH_RECENT = 5          # re-download this many of the latest votes to pick up corrections
MAX_MISSES = 2
PARTY = {"Democrat": "D", "Republican": "R", "Independent": "I"}
TERRITORIES = {"DC", "PR", "GU", "VI", "AS", "MP"}
MEMBERS_PATH = os.path.join(DATA, "members.json")
BILLS_PATH = os.path.join(DATA, "bills.json")


def stored_rolls(chamber, session):
    prefix = "%s%d-%d-" % (chamber, CONGRESS, session)
    return sorted(int(f[len(prefix):-5]) for f in os.listdir(VOTES_DIR) if f.startswith(prefix) and f.endswith(".json"))


def save_if_changed(rec):
    old = read_json(vote_path(rec["id"]))
    if old == rec:
        return False
    write_json(vote_path(rec["id"]), rec)
    return True


def fetch_house_vote(session, roll):
    status, body = http_get(HOUSE_URL.format(year=FIRST_YEAR + session - 1, roll=roll))
    if status != 200 or b"<rollcall-vote" not in body:
        return None, None      # past the last vote the Clerk answers 200 with an error page, or 404
    if ("<congress>%d</congress>" % CONGRESS).encode() not in body:
        raise ValueError("House session %d roll %d is not from the %dth Congress" % (session, roll, CONGRESS))
    return parse_house(body)


def fetch_house(people):
    changed = 0
    for session in SESSIONS:
        have = stored_rolls("h", session)
        roll = max(1, have[-1] - REFRESH_RECENT + 1) if have else 1
        misses = 0
        while misses < MAX_MISSES:
            rec, who = fetch_house_vote(session, roll)
            if rec is None:
                misses += 1
            else:
                misses = 0
                people.update({k: dict(v, c="h") for k, v in who.items()})
                if save_if_changed(rec):
                    changed += 1
                    print("house", rec["id"], rec["dt"], rec["t"][:70])
            roll += 1
    return changed


def fetch_senate(people, lis_map):
    changed = 0
    for session in SESSIONS:
        status, body = http_get(SENATE_MENU.format(c=CONGRESS, s=session))
        if status == 404:
            continue
        numbers = senate_menu_numbers(body)
        have = set(stored_rolls("s", session))
        recent = set(numbers[-REFRESH_RECENT:])
        for n in numbers:
            if n in have and n not in recent:
                continue
            status, vote = http_get(SENATE_URL.format(c=CONGRESS, s=session, n=n))
            if status != 200 or b"<roll_call_vote" not in vote:
                raise ValueError("Senate session %d vote %d: response is not a roll call vote" % (session, n))
            rec, who = parse_senate(vote, lis_map)
            people.update({k: dict(v, c="s") for k, v in who.items()})
            if save_if_changed(rec):
                changed += 1
                print("senate", rec["id"], rec["dt"], rec["t"][:70])
    return changed


def refresh_roster(members):
    """Update names, parties, seats and contact details from congress-legislators. Never drops anyone."""
    status, body = http_get(ROSTER_URL)
    if status != 200:
        print("roster: HTTP %s, keeping the stored roster" % status, file=sys.stderr)
        return members
    by_id = {m["id"]: m for m in members}
    current = set()
    for p in json.loads(body):
        # Everyone in this file is a sitting member; recorded term end dates can lag (special elections).
        term = p["terms"][-1]
        bid = p["id"]["bioguide"]
        current.add(bid)
        party = PARTY.get(term.get("party"), "I")
        caucus = PARTY.get(term.get("caucus"), party)
        chamber = "s" if term["type"] == "sen" else "h"
        m = by_id.setdefault(bid, {"id": bid})
        m.update({
            "lis": p["id"].get("lis"),
            "n": p["name"].get("official_full") or (p["name"]["first"] + " " + p["name"]["last"]),
            "first": p["name"]["first"], "l": p["name"]["last"],
            "s": term["state"], "d": term.get("district") if chamber == "h" else None,
            "c": chamber, "p": party, "g": caucus, "cur": 1,
            "vot": 0 if (chamber == "h" and term["state"] in TERRITORIES) else 1,
            "web": term.get("url"), "ph": term.get("phone"),
        })
    for m in by_id.values():
        if m["id"] not in current:
            m["cur"] = 0
    return sorted(by_id.values(), key=lambda m: m["id"])


def add_stubs(members, people):
    """Anyone who voted but is not on the roster yet gets a minimal entry from the vote record itself."""
    known = {m["id"] for m in members} | {"lis:" + m["lis"] for m in members if m.get("lis")}
    for key, who in people.items():
        if key in known or key.startswith("lis:"):
            continue
        party = (who.get("p") or "I")[:1]
        members.append({"id": key, "lis": who.get("lis"), "n": ((who.get("first") or "") + " " + (who.get("l") or key)).strip(),
                        "first": who.get("first"), "l": who.get("l") or key, "s": who.get("s"), "d": None,
                        "c": who.get("c", "h"), "p": party, "g": party if party in "DR" else "O", "cur": 1,
                        "vot": 1, "web": None, "ph": None})
        print("roster: added", key, who.get("l"), "from a vote record")
    return sorted(members, key=lambda m: m["id"])


SUMMARY_MAX = 1800


def needs_summary(b):
    """No summary yet, or one that was cut short (ends with an ellipsis)."""
    return not b.get("sum") or b["sum"].rstrip().endswith("\u2026")


def fetch_summaries(bills, limit=120):
    """Best effort: fill in missing or cut-off CRS summaries. Returns (filled, note). Never stops the update."""
    key = os.environ.get("CONGRESS_API_KEY")
    if not key:
        return 0, "no API key set"
    filled = tried = 0
    note = ""
    for bk, b in bills.items():
        if not needs_summary(b) or tried >= limit:
            continue
        _, bill_type, number = bk.split("-")
        tried += 1
        try:
            status, body = http_get(SUMMARY_URL.format(c=CONGRESS, t=bill_type, n=number), headers={"X-Api-Key": key}, tries=2)
            items = json.loads(body).get("summaries") or [] if status == 200 else []
            if not items:
                continue
            text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", items[-1].get("text") or ""))).strip()
            if b.get("t") and text.startswith(b["t"]):
                text = text[len(b["t"]):].strip()
            if len(text) > SUMMARY_MAX:
                text = text[:SUMMARY_MAX].rsplit(" ", 1)[0] + "\u2026"
            if text and text != b.get("sum"):
                b["sum"] = text
                filled += 1
        except urllib.error.HTTPError as e:
            note = "Congress.gov refused the request (HTTP %d)%s" % (e.code, ": the API key was not accepted" if e.code in (401, 403) else "")
            break
        except Exception as e:                      # noqa: BLE001 - optional step
            note = "stopped early (%s)" % type(e).__name__
            break
    return filled, note or "key accepted, %d bills checked" % tried


def verify(count, lis_map):
    """Re-download stored votes and compare them with what is on disk. Read-only."""
    problems = checked = 0
    for chamber in ("h", "s"):
        for session in SESSIONS:
            for roll in stored_rolls(chamber, session)[-count:]:
                stored = read_json(vote_path(vote_id(chamber, session, roll)))
                if chamber == "h":
                    fresh, _ = fetch_house_vote(session, roll)
                else:
                    _, body = http_get(SENATE_URL.format(c=CONGRESS, s=session, n=roll))
                    fresh, _ = parse_senate(body, lis_map)
                checked += 1
                if fresh is None:
                    problems += 1
                    print("VERIFY missing at source:", stored["id"])
                    continue
                diffs = [k for k in ("dt", "q", "res", "y", "n", "bt", "bn") if (fresh.get(k) or 0) != (stored.get(k) or 0)]
                pos = [k for k in set(fresh["pos"]) | set(stored["pos"]) if fresh["pos"].get(k) != stored["pos"].get(k)]
                if diffs or pos:
                    problems += 1
                    print("VERIFY differs:", stored["id"], "fields", diffs, "positions", len(pos), pos[:5])
    print("VERIFY checked %d stored votes against the official records: %d differ" % (checked, problems))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", type=int, default=0)
    args = ap.parse_args()

    members = refresh_roster(read_json(MEMBERS_PATH, []))
    lis_map = {m["lis"]: m["id"] for m in members if m.get("lis")}
    people = {}
    changed = fetch_house(people) + fetch_senate(people, lis_map)
    members = add_stubs(members, people)
    write_json(MEMBERS_PATH, members, pretty=True)

    bills = read_json(BILLS_PATH, {})
    filled, note = fetch_summaries(bills)
    if filled:
        write_json(BILLS_PATH, bills, pretty=True)
    print("fetch: %d votes added or corrected, %d summaries added, %d people on the roster" % (changed, filled, len(members)))
    print("SUMMARIES: %s (%d added)" % (note, filled))
    if args.verify:
        verify(args.verify, lis_map)


if __name__ == "__main__":
    main()
