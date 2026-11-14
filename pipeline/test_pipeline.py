"""Checks that run before every publish. Usage: python3 pipeline/test_pipeline.py"""
import os
import sys

from build import build, load
from common import DATA, read_json, vote_path
from parse import parse_house, parse_senate

HERE = os.path.dirname(os.path.abspath(__file__))
failures = []


def check(name, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + name + (" " + str(detail) if detail and not ok else ""))
    if not ok:
        failures.append(name)


def fixture(name):
    with open(os.path.join(HERE, "fixtures", name), "rb") as f:
        return f.read()


members = read_json(os.path.join(DATA, "members.json"))
lis = {m["lis"]: m["id"] for m in members if m.get("lis")}

# Parsers reproduce the stored record for known official files.
for name, parser, args in [("house_2025_roll010.xml", parse_house, ()),
                           ("senate_119_1_00001.xml", parse_senate, (lis,)),
                           ("senate_119_1_00015_tie_break.xml", parse_senate, (lis,))]:
    rec, _ = parser(fixture(name), *args)
    stored = read_json(vote_path(rec["id"]))
    check("parse " + name, rec == stored, [k for k in rec if rec[k] != stored.get(k)])
rec, _ = parse_house(fixture("house_2025_roll002_speaker.xml"))
check("speaker election has no yea/nay positions", set(rec["pos"].values()) <= {"S", "P", "X"})

# The built data is internally consistent.
m, b, v = load()
data, unknown = build(m, b, v)
check("every position belongs to someone on the roster", not unknown, dict(unknown))
check("vote ids are unique", len({x["id"] for x in data["votes"]}) == len(data["votes"]))
bad = [x["id"] for x in data["votes"] if len(x["pos"]) != len(data["hm"] if x["c"] == "h" else data["sm"])]
check("position strings match the roster length", not bad, bad[:3])
bad = []
for x in data["votes"]:
    y, n = x["pos"].count("Y"), x["pos"].count("N")
    # The Vice President's tie-breaking vote is in the official total but is not a senator's position.
    if x["y"] is not None and (abs(y - x["y"]) > 1 or abs(n - x["n"]) > 1):
        bad.append((x["id"], y, x["y"], n, x["n"]))
check("member positions add up to the official totals", not bad, bad[:3])
check("known vote: H.R. 2102 passed the House 392-18",
      any(x["id"] == "h119-2-0323" and (x["y"], x["n"]) == (392, 18) for x in data["votes"]))
bad = [x["id"] for x in data["members"] if x["pl"] and not (0 <= x["x"] <= x["pl"] <= x["pm"] <= x["vc"] <= x["rc"])]
check("member statistics are ordered sensibly", not bad, bad[:3])
check("both parties present", {x["g"] for x in data["members"]} >= {"D", "R"})

from build import render_pages
pages = list(render_pages(data))
paths = [p[0] for p in pages]
check("one page per vote, bill and member", len(paths) == len(set(paths)) == 5 + len(data["votes"]) + len(data["bills"]) + len(data["members"]))
check("every page has a title and description", all(p[1] and p[2] for p in pages))

if failures:
    print("%d check(s) failed" % len(failures))
    sys.exit(1)
print("all checks passed")
