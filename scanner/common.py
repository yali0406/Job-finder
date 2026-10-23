import hashlib
import logging
import re
import time
from dataclasses import dataclass, field, asdict

import requests

log = logging.getLogger("scanner")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9,he;q=0.8"})

ISRAEL_HINTS = re.compile(
    r"israel|tel[\s-]?aviv|herzliya|ramat[\s-]?gan|petah?[\s-]?tikva|ra'?anana|hod[\s-]?hasharon|"
    r"kfar[\s-]?saba|netanya|rishon|rehovot|holon|givatayim|bnei[\s-]?brak|or[\s-]?yehuda|"
    r"airport[\s-]?city|yokneam|haifa|jerusalem|modi'?in|caesarea|beer[\s-]?sheva|lod|ramla|"
    r"ישראל|תל[\s-]?אביב|הרצליה|רמת[\s-]?גן|פתח[\s-]?תקווה|רעננה",
    re.I,
)


@dataclass
class Job:
    title: str
    company: str
    url: str
    location: str = ""
    source: str = ""
    description: str = ""
    posted: str = ""
    # filled in later
    id: str = ""
    first_seen: str = ""
    score: int | None = None
    reason: str = ""
    category: str = ""
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            key = f"{norm(self.company)}|{norm(self.title)}|{norm(self.location)}"
            self.id = hashlib.sha1(key.encode()).hexdigest()[:16]

    def to_dict(self):
        d = asdict(self)
        d.pop("extra", None)
        return d


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9א-ת]+", "", (s or "").lower())


def strip_html(html: str) -> str:
    text = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html or "", flags=re.I)
    text = re.sub(r"<br\s*/?>|</p>|</li>|</div>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def in_israel(location: str) -> bool:
    return bool(ISRAEL_HINTS.search(location or ""))


def get(url, *, params=None, timeout=25, retries=2, **kw):
    """GET with small retry/backoff. Returns Response or None (never raises)."""
    for attempt in range(retries + 1):
        try:
            r = session.get(url, params=params, timeout=timeout, **kw)
            if r.status_code == 429 and attempt < retries:
                time.sleep(5 * (attempt + 1))
                continue
            return r
        except requests.RequestException as e:
            if attempt == retries:
                log.debug("GET %s failed: %s", url, e)
                return None
            time.sleep(2 * (attempt + 1))
    return None


def post(url, *, json=None, timeout=25, **kw):
    try:
        return session.post(url, json=json, timeout=timeout, **kw)
    except requests.RequestException as e:
        log.debug("POST %s failed: %s", url, e)
        return None
