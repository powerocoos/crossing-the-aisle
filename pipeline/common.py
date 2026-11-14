"""Shared helpers for the Crossing the Aisle data pipeline (standard library only)."""
import json
import os
import re
import time
import urllib.error
import urllib.request

CONGRESS = 119
SESSIONS = (1, 2)
FIRST_YEAR = 2 * CONGRESS + 1787          # 119th Congress -> 2025
USER_AGENT = "crossing-the-aisle (+https://crossingtheaisle.us)"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
VOTES_DIR = os.path.join(DATA, "votes")

BILL_TYPES = {"HR": "hr", "S": "s", "HRES": "hres", "SRES": "sres", "HJRES": "hjres",
              "SJRES": "sjres", "HCONRES": "hconres", "SCONRES": "sconres"}
CITATION = {"hr": "H.R.", "s": "S.", "hres": "H.Res.", "sres": "S.Res.", "hjres": "H.J.Res.",
            "sjres": "S.J.Res.", "hconres": "H.Con.Res.", "sconres": "S.Con.Res."}
CONGRESS_GOV_SLUG = {"hr": "house-bill", "s": "senate-bill", "hres": "house-resolution",
                     "sres": "senate-resolution", "hjres": "house-joint-resolution",
                     "sjres": "senate-joint-resolution", "hconres": "house-concurrent-resolution",
                     "sconres": "senate-concurrent-resolution"}
POSITION_CODE = {"Yea": "Y", "Aye": "Y", "Nay": "N", "No": "N", "Present": "P", "Not Voting": "X"}


def parse_measure(text):
    """'H R 2102' or 'S.J.Res. 98' -> ('hr', '2102'); None for nominations and non-measures."""
    if not text:
        return None
    m = re.fullmatch(r"([A-Za-z. ]+?)\s*(\d+)", text.strip())
    if not m:
        return None
    bill_type = BILL_TYPES.get(re.sub(r"[^A-Z]", "", m.group(1).upper()))
    return (bill_type, m.group(2)) if bill_type else None


def bill_key(bill_type, number):
    return "%d-%s-%s" % (CONGRESS, bill_type, number)


def bill_url(bill_type, number):
    return "https://www.congress.gov/bill/%dth-congress/%s/%s" % (CONGRESS, CONGRESS_GOV_SLUG[bill_type], number)


def vote_id(chamber, session, roll):
    return "%s%d-%d-%04d" % (chamber, CONGRESS, session, roll)


def vote_path(vid):
    return os.path.join(VOTES_DIR, vid + ".json")


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json(path, obj, pretty=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        else:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


_last_request = [0.0]


def http_get(url, headers=None, tries=4, delay=0.3):
    """GET with a polite pause between requests and a few retries. Returns (status, bytes)."""
    hdrs = {"User-Agent": USER_AGENT}
    hdrs.update(headers or {})
    backoff = [5, 15, 45]
    for attempt in range(tries):
        wait = delay - (time.monotonic() - _last_request[0])
        if wait > 0:
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=30) as resp:
                _last_request[0] = time.monotonic()
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            _last_request[0] = time.monotonic()
            if e.code == 404:
                return 404, b""
            if attempt == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            _last_request[0] = time.monotonic()
            if attempt == tries - 1:
                raise
        time.sleep(backoff[min(attempt, len(backoff) - 1)])
    raise RuntimeError("unreachable")
