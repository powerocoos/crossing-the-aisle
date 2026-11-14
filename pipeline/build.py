"""Build the public site: data/ -> public/ (shared app files, data.json, and one page per vote, bill and member).

Usage: python3 pipeline/build.py
"""
import collections
import datetime as dt
import hashlib
import html
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


SITE = "https://crossingtheaisle.us"
NAME = "Crossing the Aisle"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PARTY_NAME = {"D": "Democrats", "R": "Republicans"}
OTHER = {"D": "R", "R": "D"}
POS_NAME = {"Y": "Yea", "N": "Nay"}
STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
          "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
          "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
          "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
          "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
          "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
          "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
          "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
          "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
          "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia", "PR": "Puerto Rico", "GU": "Guam",
          "VI": "U.S. Virgin Islands", "AS": "American Samoa", "MP": "Northern Mariana Islands"}


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def fdate(d):
    y, m, day = d.split("-")
    return "%s %d, %s" % (MONTHS[int(m) - 1], int(day), y)


def clip(text, n):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n - 1].rsplit(" ", 1)[0] + "…"


def tag(m):
    d = ""
    if m["c"] == "h" and m.get("d") is not None:
        d = "-%s" % ("AL" if m["d"] == 0 else m["d"])
    return "(%s-%s%s)" % (m["p"], m["s"], d)


def seat(m):
    st = STATES.get(m["s"], m["s"])
    if m["c"] == "s":
        return "Senator, " + st
    if not m.get("vot", 1):
        return "Delegate, " + st
    return "Representative, %s%s" % (st, (" district %s" % m["d"]) if m.get("d") else " at large")


def chamber(c):
    return "House" if c == "h" else "Senate"


def head(title, desc, path):
    url = SITE + path
    return "\n".join([
        "<title>%s</title>" % esc(title),
        '<meta name="description" content="%s">' % esc(desc),
        '<link rel="canonical" href="%s">' % esc(url),
        '<meta property="og:site_name" content="%s">' % NAME,
        '<meta property="og:title" content="%s">' % esc(title),
        '<meta property="og:description" content="%s">' % esc(desc),
        '<meta property="og:type" content="website">',
        '<meta property="og:url" content="%s">' % esc(url),
        '<meta property="og:image" content="%s/og.png">' % SITE,
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="theme-color" content="#1b4fbf">',
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">',
    ])


def vote_facts(v, order, by_id):
    """Party tallies and the members who crossed over, for one built vote."""
    ids = order[v["c"]]
    tally = {"D": collections.Counter(), "R": collections.Counter()}
    cross = {"D": [], "R": []}
    split = bool(v["mD"] and v["mR"] and v["mD"] != v["mR"])
    for i, p in zip(ids, v["pos"]):
        m = by_id[i]
        if p == "." or m["g"] not in tally:
            continue
        tally[m["g"]][p] += 1
        if split and p in "YN" and p != v["m" + m["g"]]:
            cross[m["g"]].append(m)
    return tally, cross, split


def vote_link(v):
    label = (v["lab"] + ": ") if v.get("lab") else ""
    return '<a href="/vote/%s/">%s</a> (%s, %s; %s)' % (
        v["id"], esc(clip(label + v["t"], 110)), chamber(v["c"]), fdate(v["dt"]), esc(v["res"] or ""))


def member_link(m):
    return '<a href="/member/%s/">%s</a> %s' % (m["id"], esc(m["n"]), tag(m))


def render_pages(data):
    """Yield (path, title, description, static_html) for every page of the site."""
    by_id = {m["id"]: m for m in data["members"]}
    order = {"h": data["hm"], "s": data["sm"]}
    votes = data["votes"]
    facts = {v["id"]: vote_facts(v, order, by_id) for v in votes}
    by_bill = collections.defaultdict(list)
    for v in votes:
        if v["b"]:
            by_bill[v["b"]].append(v)

    # Section pages
    recent = [v for v in votes if v["fp"]][:40]
    yield ("/", NAME,
           "See how every Democrat and Republican in Congress voted on each bill, and who crossed the aisle to vote "
           "with the other party. Built from official House and Senate roll call records.",
           "<h2>Recent votes</h2><ul>%s</ul>" % "".join("<li>%s</li>" % vote_link(v) for v in recent))
    bills = sorted(data["bills"].items(), key=lambda kv: by_bill[kv[0]][0]["dt"] if by_bill[kv[0]] else "", reverse=True)
    yield ("/bills/", "Bills · " + NAME,
           "Every bill and resolution of the 119th Congress that reached a recorded vote, with each roll call on it.",
           "<h2>Bills</h2><ul>%s</ul>" % "".join(
               '<li><a href="/bill/%s/">%s</a></li>' % (k, esc(clip("%s: %s" % (b["lab"], b.get("t") or ""), 120))) for k, b in bills))
    yield ("/members/", "Members of Congress · " + NAME,
           "Voting records for every member of the 119th Congress: how often they vote with their party, and how "
           "often they cross the aisle.",
           "<h2>Members</h2><ul>%s</ul>" % "".join("<li>%s, %s</li>" % (member_link(m), esc(seat(m))) for m in data["members"]))
    yield ("/find/", "Find my rep · " + NAME,
           "Pick your state to see your senators and representatives and how they have voted.",
           "<h2>Find my rep</h2><p>Enter your ZIP code, or pick your state, to see who represents you in Congress.</p>")
    top = []
    for g in ("D", "R"):
        for c in ("s", "h"):
            ranked = sorted((m for m in data["members"] if m["g"] == g and m["c"] == c and m["pl"] >= 50),
                            key=lambda m: (-m["x"] / m["pl"], -m["x"]))[:15]
            top.append("<h3>%s %s who side with %s most often</h3><ul>%s</ul>" % (
                chamber(c), PARTY_NAME[g], PARTY_NAME[OTHER[g]],
                "".join("<li>%s: %d of %d split votes</li>" % (member_link(m), m["x"], m["pl"]) for m in ranked)))
    yield ("/crossing/", "Who crosses the aisle · " + NAME,
           "Which Democrats vote with Republicans most often, which Republicans vote with Democrats, and on which votes.",
           "<h2>Crossing the aisle</h2>" + "".join(top))

    # One page per vote
    for v in votes:
        tally, cross, split = facts[v["id"]]
        label = (v["lab"] + ": ") if v.get("lab") else ""
        title = "%s · %s vote %s · %s" % (clip(label + v["t"], 70), chamber(v["c"]), fdate(v["dt"]), NAME)
        parts = ["%s, %s: %s." % (chamber(v["c"]), fdate(v["dt"]), v["res"] or "recorded vote"),
                 "Democrats %d-%d, Republicans %d-%d." % (tally["D"]["Y"], tally["D"]["N"], tally["R"]["Y"], tally["R"]["N"])]
        if split:
            parts.append("%d Democrat%s sided with Republicans and %d Republican%s sided with Democrats." % (
                len(cross["D"]), "" if len(cross["D"]) == 1 else "s", len(cross["R"]), "" if len(cross["R"]) == 1 else "s"))
        elif v["mD"] and v["mR"]:
            parts.append("Most members of both parties voted the same way.")
        body = ["<p>%s · %s roll call %d%s</p>" % (fdate(v["dt"]), chamber(v["c"]), v["r"], (" · " + esc(v["lab"])) if v.get("lab") else ""),
                "<h2>%s</h2>" % esc(v["t"]), "<p>%s. <b>%s</b>. Whole chamber: %s Yea, %s Nay.</p>" % (esc(v["q"]), esc(v["res"] or ""), v["y"], v["n"]),
                "<p>Democrats: %d Yea, %d Nay. Republicans: %d Yea, %d Nay.</p>" % (tally["D"]["Y"], tally["D"]["N"], tally["R"]["Y"], tally["R"]["N"])]
        if split:
            for g in ("D", "R"):
                body.append("<h3>%s who sided with %s (%d)</h3>" % (PARTY_NAME[g], PARTY_NAME[OTHER[g]], len(cross[g])))
                body.append("<ul>%s</ul>" % "".join("<li>%s</li>" % member_link(m) for m in cross[g]) if cross[g] else "<p>None.</p>")
        if v["b"]:
            body.append('<p><a href="/bill/%s/">All votes on %s</a></p>' % (v["b"], esc(data["bills"][v["b"]]["lab"])))
        body.append('<p><a href="%s" rel="noopener">Official record</a></p>' % esc(v["src"]))
        yield ("/vote/%s/" % v["id"], title, " ".join(parts), "".join(body))

    # One page per bill
    for k, b in data["bills"].items():
        rolls = by_bill[k]
        title = "%s · %s" % (clip("%s: %s" % (b["lab"], b.get("t") or ""), 80), NAME)
        desc = clip(b.get("sum") or "", 150) if b.get("sum") else "Every recorded House and Senate vote on %s, with how each party and each member voted." % b["lab"]
        body = ["<p>%s</p>" % esc(b["lab"]), "<h2>%s</h2>" % esc(b.get("t") or b["lab"])]
        if b.get("sum"):
            body.append("<p>%s</p>" % esc(b["sum"]))
        if b.get("url"):
            body.append('<p><a href="%s" rel="noopener">Full text and status on Congress.gov</a></p>' % esc(b["url"]))
        body.append("<h3>Roll calls on this measure (%d)</h3><ul>%s</ul>" % (len(rolls), "".join("<li>%s: %s</li>" % (esc(v["q"]), vote_link(v)) for v in rolls)))
        yield ("/bill/%s/" % k, title, desc, "".join(body))

    # One page per member
    crossed = collections.defaultdict(list)
    for v in votes:
        for g in ("D", "R"):
            for m in facts[v["id"]][1][g]:
                if len(crossed[m["id"]]) < 15:
                    crossed[m["id"]].append(v)
    for m in data["members"]:
        g = m["g"]
        own, other = PARTY_NAME.get(g, "their party"), PARTY_NAME.get(OTHER.get(g), "the other party")
        title = "%s %s voting record · %s" % (m["n"], tag(m), NAME)
        if m["rc"]:
            desc = "%s, %s. Sided with %s on %d of %d split votes, voted with most %s %s%% of the time, missed %s%% of votes." % (
                m["n"], seat(m), other, m["x"], m["pl"], own, m["w"], m["miss"])
        else:
            desc = "%s, %s. No recorded votes yet in the 119th Congress." % (m["n"], seat(m))
        body = ["<h2>%s</h2>" % esc(m["n"]), "<p>%s · %s%s</p>" % (esc(seat(m)), "Independent, caucuses with " + own if m["p"] == "I" else own[:-1],
                                                                 "" if m.get("cur") else " · no longer serving"), "<p>%s</p>" % esc(desc)]
        if crossed[m["id"]]:
            body.append("<h3>Recent votes with %s</h3><ul>%s</ul>" % (other, "".join("<li>%s</li>" % vote_link(v) for v in crossed[m["id"]])))
        if m.get("web"):
            body.append('<p><a href="%s" rel="noopener">Official website</a></p>' % esc(m["web"]))
        yield ("/member/%s/" % m["id"], title, desc, "".join(body))


def load_zips():
    """ZIP code -> "ST12,ST13" (state plus district, 0 = at-large) from data/zip_districts.csv."""
    import csv
    out = {}
    with open(os.path.join(DATA, "zip_districts.csv"), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["zip"], []).append("%s%d" % (r["state"], int(r["district"])))
    return {z: ",".join(v) for z, v in out.items()}


def write_site(data):
    pub = os.path.join(ROOT, "public")
    shutil.rmtree(pub, ignore_errors=True)
    os.makedirs(pub)
    site = os.path.join(ROOT, "site")
    for name in os.listdir(os.path.join(site, "static")):
        shutil.copy2(os.path.join(site, "static", name), os.path.join(pub, name))
    version = hashlib.sha1()
    for name in ("app.css", "app.js"):
        with open(os.path.join(site, name), "rb") as f:
            blob = f.read()
        version.update(blob)
        with open(os.path.join(pub, name), "wb") as f:
            f.write(blob)
    write_json(os.path.join(pub, "data.json"), data)
    write_json(os.path.join(pub, "zips.json"), load_zips())
    with open(os.path.join(site, "template.html"), encoding="utf-8") as f:
        template = f.read().replace("{{V}}", version.hexdigest()[:10]).replace("{{LATEST}}", fdate(data["meta"]["latest"]))
    before, rest = template.split("{{HEAD}}")
    middle, after = rest.split("{{CONTENT}}")
    urls = []
    for path, title, desc, content in render_pages(data):
        folder = os.path.join(pub, path.strip("/"))
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "index.html"), "w", encoding="utf-8") as f:
            f.write(before + head(title, desc, path) + middle + content + after)
        urls.append(path)
    with open(os.path.join(pub, "404.html"), "w", encoding="utf-8") as f:
        f.write(before + head("Page not found · " + NAME, "That page does not exist.", "/404") + middle +
                '<h2>Page not found</h2><p>That page does not exist. <a href="/">See recent votes</a>.</p>' + after.replace(
                    '<script src="/app.js', '<script data-off src="/none.js'))
    with open(os.path.join(pub, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        f.writelines("<url><loc>%s%s</loc></url>\n" % (SITE, u) for u in urls)
        f.write("</urlset>\n")
    return len(urls)


def main():
    members, bills, votes = load()
    data, unknown = build(members, bills, votes)
    if unknown:
        print("warning: positions for ids missing from the roster:", dict(unknown.most_common(10)), file=sys.stderr)
    pages = write_site(data)
    print("built %d votes, %d members, %d bills, %d pages, latest %s" % (
        len(data["votes"]), len(data["members"]), len(data["bills"]), pages, data["meta"]["latest"]))


if __name__ == "__main__":
    main()
