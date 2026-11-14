"""One-time seed: convert the open Yeas & Nays export (MIT, github.com/rachelsprague/yeas-and-nays,
data/out/) into this project's data/ layout. New votes after the seed come from fetch.py.

Usage: python3 pipeline/seed_from_yeas_and_nays.py /path/to/yeas-and-nays/data/out
"""
import html
import json
import os
import re
import sys

from common import DATA, POSITION_CODE, vote_path, write_json

src = sys.argv[1]
members = json.load(open(os.path.join(src, "members.json")))["members"]
votes = json.load(open(os.path.join(src, "votes.json")))
votes = votes if isinstance(votes, list) else votes["votes"]

out_members = []
for m in members:
    out_members.append({
        "id": m["bioguide_id"], "lis": m["lis_id"],
        "n": m["official_full_name"] or (m["first_name"] + " " + m["last_name"]),
        "first": m["first_name"], "l": m["last_name"], "s": m["state"], "d": m["district"],
        "c": m["chamber"][0], "p": m["party"], "g": m["caucus_party"],
        "cur": 1 if m["is_current"] else 0, "vot": 1 if m["is_voting_member"] else 0,
        "web": m["website_url"], "ph": m["phone"],
    })
out_members.sort(key=lambda m: m["id"])
write_json(os.path.join(DATA, "members.json"), out_members, pretty=True)

bills = {}
for v in votes:
    d = json.load(open(os.path.join(src, "votes", v["vote_id"] + ".json")))
    rec = {
        "id": v["vote_id"], "c": v["chamber"][0], "ses": v["session"], "r": v["roll_number"],
        "dt": v["vote_date"], "time": (v["vote_time_et"] or "")[11:16] or None,
        "q": v["question"] or "", "t": v["measure_title"] or v["vote_title"] or v["question"] or "",
        "lab": v["measure_label"], "bt": v["bill_type"], "bn": v["bill_number"],
        "res": v["result"], "y": v["yea_count"], "n": v["nay_count"],
        "amn": v["amendment_number"],
        "am": (v["amendment_purpose"] or v["amendment_author"]) if v["amendment_number"] else None,
        "src": v["source_url"],
        "pos": {k: POSITION_CODE.get(p, "S") for k, p in d["positions"].items()},
    }
    write_json(vote_path(rec["id"]), rec)
    if v["bill_type"]:
        key = "%d-%s-%s" % (v["congress"], v["bill_type"], v["bill_number"])
        b = bills.setdefault(key, {"lab": v["measure_label"], "t": v["measure_title"], "url": v["congress_gov_url"],
                                   "intro": v["introduced_date"], "sum": None})
        if not b["t"] and v["measure_title"]:
            b["t"] = v["measure_title"]
        sm = d.get("summary")
        if sm and sm.get("html") and not b["sum"]:
            txt = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", sm["html"]))).strip()
            if b["t"] and txt.startswith(b["t"]):
                txt = txt[len(b["t"]):].strip()
            if len(txt) > 520:
                txt = txt[:520].rsplit(" ", 1)[0] + "…"
            b["sum"] = txt
write_json(os.path.join(DATA, "bills.json"), bills, pretty=True)
print("seeded", len(out_members), "members,", len(votes), "votes,", len(bills), "bills")
