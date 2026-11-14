"""Parse official roll call XML from the House Clerk and the Senate into one plain record."""
import datetime as dt
import re
import xml.etree.ElementTree as ET

from common import CITATION, FIRST_YEAR, POSITION_CODE, parse_measure, vote_id

SESSION_NUM = {"1st": 1, "2nd": 2}


def _t(node, path):
    v = node.findtext(path) if node is not None else None
    v = v.strip() if v else None
    return v or None


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def parse_house(content):
    root = ET.fromstring(content)
    meta = root.find("vote-metadata")
    session = SESSION_NUM[_t(meta, "session")]
    roll = int(_t(meta, "rollcall-num"))
    date = dt.datetime.strptime(_t(meta, "action-date"), "%d-%b-%Y").date()
    tnode = meta.find("action-time")
    legis = _t(meta, "legis-num")
    bill = parse_measure(legis)
    totals = meta.find("vote-totals/totals-by-vote")
    question = _t(meta, "vote-question") or ""
    positions = {}
    for rv in root.iter("recorded-vote"):
        leg = rv.find("legislator")
        if leg is None or not leg.get("name-id"):
            continue
        positions[leg.get("name-id")] = (_t(rv, "vote") or "").strip()
    rec = {
        "id": vote_id("h", session, roll), "c": "h", "ses": session, "r": roll,
        "dt": date.isoformat(), "time": tnode.get("time-etz") if tnode is not None else None,
        "q": question, "t": _t(meta, "vote-desc") or question,
        "lab": ("%s %s" % (CITATION[bill[0]], bill[1])) if bill else None,
        "bt": bill[0] if bill else None, "bn": bill[1] if bill else None,
        "res": _t(meta, "vote-result"),
        "y": _int(_t(totals, "yea-total")), "n": _int(_t(totals, "nay-total")),
        "amn": _t(meta, "amendment-num"), "am": _t(meta, "amendment-author"),
        "src": "https://clerk.house.gov/Votes/%d%d" % (FIRST_YEAR + session - 1, roll),
        "pos": {k: POSITION_CODE.get(v, "S") for k, v in positions.items()},
    }
    people = {}
    for rv in root.iter("recorded-vote"):
        leg = rv.find("legislator")
        if leg is not None and leg.get("name-id"):
            people[leg.get("name-id")] = {"l": (leg.get("unaccented-name") or leg.text or "").split(" (")[0],
                                          "p": leg.get("party"), "s": leg.get("state")}
    return rec, people


def parse_senate(content, lis_to_bioguide):
    root = ET.fromstring(content)
    session = int(_t(root, "session"))
    roll = int(_t(root, "vote_number"))
    raw_date = re.sub(r"\s+", " ", _t(root, "vote_date"))
    when = dt.datetime.strptime(raw_date, "%B %d, %Y, %I:%M %p")
    doc_name = _t(root, "document/document_name")
    bill = parse_measure(doc_name)
    amn = _t(root, "amendment/amendment_number")
    question = _t(root, "vote_question_text") or _t(root, "question") or ""
    title = _t(root, "document/document_title") or _t(root, "vote_title") or question
    positions, people = {}, {}
    for m in root.iter("member"):
        lis = _t(m, "lis_member_id")
        if not lis:
            continue
        key = lis_to_bioguide.get(lis, "lis:" + lis)
        positions[key] = POSITION_CODE.get(_t(m, "vote_cast") or "", "S")
        people[key] = {"l": _t(m, "last_name"), "first": _t(m, "first_name"), "p": _t(m, "party"),
                       "s": _t(m, "state"), "lis": lis}
    base = "https://www.senate.gov/legislative/LIS/roll_call_votes/vote%d%d/vote_%d_%d_%05d" % (
        int(_t(root, "congress")), session, int(_t(root, "congress")), session, roll)
    rec = {
        "id": vote_id("s", session, roll), "c": "s", "ses": session, "r": roll,
        "dt": when.date().isoformat(), "time": when.strftime("%H:%M"),
        "q": question, "t": title,
        "lab": ("%s %s" % (CITATION[bill[0]], bill[1])) if bill else doc_name,
        "bt": bill[0] if bill else None, "bn": bill[1] if bill else None,
        "res": _t(root, "vote_result"),
        "y": _int(_t(root, "count/yeas")), "n": _int(_t(root, "count/nays")),
        "amn": amn, "am": _t(root, "amendment/amendment_purpose") if amn else None,
        "src": base + ".htm",
        "pos": positions,
    }
    return rec, people


def senate_menu_numbers(content):
    root = ET.fromstring(content)
    return sorted(int(v.findtext("vote_number")) for v in root.iter("vote") if v.findtext("vote_number"))
