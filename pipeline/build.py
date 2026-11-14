"""Build the public site: data/ -> public/data.json, plus a copy of everything in site/.

Usage: python3 pipeline/build.py
"""
import collections
import datetime as dt
import os
import re
import shutil
import sys

from common import DATA, ROOT, VOTES_DIR, bill_key, bill_url, read_json, write_json

PASSAGE = re.compile(
    r"^On Passage|Suspend the Rules and (Pass|Agree)|^On Agreeing to the Resolution|^On the Joint Resolution"
    r"|^On the Resolution|^On the Concurrent Resolution|Conference Report|Concur in the Senate Amendment|Overrid")


def pct(part, whole):
    """Percentage to one decimal, rounding halves up (integer arithmetic, no float surprises)."""
    return (2000 * part + whole) // (2 * whole) / 10 if whole else None


def load():
    members = read_json(os.path.join(DATA, "members.json"), [])
    bills = read_json(os.path.join(DATA, "bills.json"), {})
    votes = [read_json(os.path.join(VOTES_DIR, f)) for f in sorted(os.listdir(VOTES_DIR)) if f.endswith(".json")]
    return members, bills, votes


def build(members, bills, votes):
    by_id = {m["id"]: m for m in members}
    by_lis = {m["lis"]: m["id"] for m in members if m.get("lis")}
    group = {m["id"]: (m["g"] if m.get("g") in ("D", "R") else "O") for m in members}
    unknown = collections.Counter()

    # Resolve Senate positions that were stored under an LIS id before the roster knew the senator.
    for v in votes:
        fixed = {}
        for k, p in v["pos"].items():
            if k.startswith("lis:") and k[4:] in by_lis:
                k = by_lis[k[4:]]
            fixed[k] = p
        v["pos"] = fixed

    seen = {"h": set(), "s": set()}
    for v in votes:
        for k in v["pos"]:
            if k in by_id:
                seen[v["c"]].add(k)
            else:
                unknown[k] += 1
    order = {c: sorted(seen[c], key=lambda i: (by_id[i]["l"], by_id[i].get("first") or "", i)) for c in ("h", "s")}

    stats = {i: collections.Counter() for i in by_id}
    out_votes = []
    for v in votes:
        ids = order[v["c"]]
        pos = v["pos"]
        count = {"D": collections.Counter(), "R": collections.Counter()}
        for i in ids:
            p = pos.get(i)
            if p and group[i] in count:
                count[group[i]][p] += 1
        maj = {}
        for g in ("D", "R"):
            y, n = count[g]["Y"], count[g]["N"]
            maj[g] = "Y" if y > n else "N" if n > y else ""
        party_line = bool(maj["D"] and maj["R"] and maj["D"] != maj["R"])
        for i in ids:
            p = pos.get(i)
            if not p:
                continue
            st = stats[i]
            st["rc"] += 1
            if p == "X":
                st["missed"] += 1
            else:
                st["vc"] += 1
            g = group[i]
            if p in "YN" and maj.get(g):
                st["pm"] += 1
                if p != maj[g]:
                    st["ag"] += 1
                if party_line:
                    st["pl"] += 1
                    if p != maj[g]:
                        st["x"] += 1
        bk = bill_key(v["bt"], v["bn"]) if v.get("bt") else None
        if bk and bk not in bills:
            bills[bk] = {"lab": v["lab"], "t": v["t"], "url": bill_url(v["bt"], v["bn"]), "intro": None, "sum": None}
        q = v["q"] or ""
        is_nom = (v.get("lab") or "").startswith("PN") or "Nomination" in q
        out_votes.append({
            "id": v["id"], "c": v["c"], "dt": v["dt"], "r": v["r"], "ses": v["ses"], "q": q, "t": v["t"] or q,
            "lab": v.get("lab"), "b": bk, "k": "b" if bk else ("n" if is_nom else "o"),
            "fp": 1 if (bk and PASSAGE.search(q) and not v.get("amn")) else 0,
            "res": v.get("res"), "y": v.get("y"), "n": v.get("n"), "mD": maj["D"], "mR": maj["R"],
            "src": v["src"], "am": v.get("am") if v.get("amn") else None,
            "pos": "".join(pos.get(i, ".") for i in ids),
        })
    out_votes.sort(key=lambda x: (x["dt"], x["c"], x["r"]), reverse=True)

    out_members = []
    for m in sorted(members, key=lambda m: (m["l"], m.get("first") or "", m["id"])):
        st = stats[m["id"]]
        if not st["rc"] and not m.get("cur"):
            continue
        out_members.append({
            "id": m["id"], "n": m["n"], "l": m["l"], "g": group[m["id"]], "s": m["s"], "d": m.get("d"),
            "c": m["c"], "p": m["p"], "cur": m.get("cur", 0), "vot": m.get("vot", 1),
            "web": m.get("web"), "ph": m.get("ph"),
            "rc": st["rc"], "vc": st["vc"],
            "miss": pct(st["missed"], st["rc"]),
            "w": pct(st["pm"] - st["ag"], st["pm"]),
            "ag": st["ag"], "pm": st["pm"], "x": st["x"], "pl": st["pl"],
        })
    used_bills = {v["b"] for v in out_votes if v["b"]}
    latest = max((v["dt"] for v in out_votes), default=None)
    data = {
        "meta": {"latest": latest, "votes": len(out_votes), "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")},
        "members": out_members, "hm": order["h"], "sm": order["s"], "votes": out_votes,
        "bills": {k: b for k, b in bills.items() if k in used_bills},
    }
    return data, unknown


def main():
    members, bills, votes = load()
    data, unknown = build(members, bills, votes)
    if unknown:
        print("warning: positions for ids missing from the roster:", dict(unknown.most_common(10)), file=sys.stderr)
    pub = os.path.join(ROOT, "public")
    os.makedirs(pub, exist_ok=True)
    for name in os.listdir(os.path.join(ROOT, "site")):
        shutil.copy2(os.path.join(ROOT, "site", name), os.path.join(pub, name))
    # "built" changes daily; keep the file stable when nothing else changed so commits stay meaningful.
    old = read_json(os.path.join(pub, "data.json"))
    if old:
        probe = dict(data, meta=dict(data["meta"], built=old.get("meta", {}).get("built")))
        if probe == old:
            data = old
    write_json(os.path.join(pub, "data.json"), data)
    print("built %d votes, %d members, %d bills, latest %s" % (
        len(data["votes"]), len(data["members"]), len(data["bills"]), data["meta"]["latest"]))


if __name__ == "__main__":
    main()
