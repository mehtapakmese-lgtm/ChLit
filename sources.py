"""Canlı akademik kaynaklardan arama ve doğrulama. Referanslar yalnızca buradan gelir."""
import os, re, difflib, requests
from bs4 import BeautifulSoup

MAIL = os.getenv("CONTACT_EMAIL", "")
UA = {"User-Agent": f"DAAD-CL-Assistant/0.1 (mailto:{MAIL})"}

# Alan filtresi: her aramaya zorunlu eklenir
DOMAIN_TERMS = [
    '"children\'s literature"', '"picturebook"', '"picture book"', '"young adult literature"',
    '"children\'s books"', '"Kinder- und Jugendliteratur"', '"Kinderliteratur"',
    '"Jugendliteratur"', '"juvenile literature"', '"children\'s fiction"',
]
DOMAIN_REGEX = re.compile(
    r"child|juvenile|picture ?book|young adult|youth lit|kinder|jugend|çocuk|bilderbuch|"
    r"fairy tale|märchen|masal|adolescent lit", re.I)
PRIORITY_JOURNALS = [
    "Children's Literature in Education", "International Research in Children's Literature",
    "Bookbird", "Jeunesse", "Children's Literature Association Quarterly",
    "Kinder- und Jugendliteraturforschung", "Journal of Children's Literature Studies",
    "Children's Literature", "Journal of Literary Education", "Neohelicon",
]

def _abstract(inv):
    if not inv: return ""
    pos = {}
    for w, idxs in inv.items():
        for i in idxs: pos[i] = w
    return " ".join(pos[i] for i in sorted(pos))

def search_works(query, year_from=2000, n=25, de_only=False, domain_filter=True):
    q = query.strip()
    if domain_filter:
        q = f"({q}) AND ({' OR '.join(DOMAIN_TERMS)})"
    flt = [f"from_publication_date:{year_from}-01-01"]
    if de_only: flt.append("institutions.country_code:DE")
    r = requests.get("https://api.openalex.org/works", headers=UA, timeout=30, params={
        "search": q, "filter": ",".join(flt), "per-page": n,
        "sort": "relevance_score:desc", "mailto": MAIL})
    r.raise_for_status()
    out = []
    for w in r.json().get("results", []):
        loc = (w.get("primary_location") or {}).get("source") or {}
        auths = w.get("authorships", [])
        item = {
            "openalex_id": w["id"],
            "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
            "title": w.get("title") or "",
            "year": w.get("publication_year"),
            "type": w.get("type"),
            "venue": loc.get("display_name") or "",
            "authors": [a["author"]["display_name"] for a in auths if a.get("author")],
            "affiliations": sorted({i["display_name"] + f" ({i.get('country_code','')})"
                                    for a in auths for i in a.get("institutions", [])}),
            "cited_by": w.get("cited_by_count", 0),
            "abstract": _abstract(w.get("abstract_inverted_index")),
            "verified": False, "verify_note": "",
        }
        blob = f"{item['title']} {item['venue']} {item['abstract']}"
        item["in_domain"] = bool(DOMAIN_REGEX.search(blob)) or item["venue"] in PRIORITY_JOURNALS
        out.append(item)
    return [x for x in out if x["in_domain"] and x["title"]] if domain_filter else out

def verify_crossref(item):
    """DOI'yi Crossref'te doğrular ve başlığı karşılaştırır."""
    if not item.get("doi"):
        item["verify_note"] = "DOI yok – elle doğrulayın (kitap/bölüm olabilir)."
        return item
    try:
        r = requests.get(f"https://api.crossref.org/works/{item['doi']}", headers=UA,
                         params={"mailto": MAIL}, timeout=20)
        if r.status_code != 200:
            item["verify_note"] = f"Crossref'te bulunamadı (HTTP {r.status_code})."
            return item
        m = r.json()["message"]
        cr_title = (m.get("title") or [""])[0]
        sim = difflib.SequenceMatcher(None, cr_title.lower(), item["title"].lower()).ratio()
        item["verified"] = sim > 0.85
        item["verify_note"] = f"Crossref başlık benzerliği: {sim:.2f}"
        item["volume"], item["issue"], item["pages"] = m.get("volume"), m.get("issue"), m.get("page")
        item["publisher"] = m.get("publisher")
    except Exception as e:
        item["verify_note"] = f"Doğrulama hatası: {e}"
    return item

def verify_isbn_book(title, author=""):
    """Kitaplar için Open Library ile künye kontrolü (DOI'si olmayanlar)."""
    r = requests.get("https://openlibrary.org/search.json", headers=UA, timeout=20,
                     params={"title": title, "author": author, "limit": 3})
    return [{"title": d.get("title"), "authors": d.get("author_name"), "year": d.get("first_publish_year"),
             "isbn": (d.get("isbn") or [None])[0], "publisher": (d.get("publisher") or [None])[0]}
            for d in r.json().get("docs", [])]

def institution_summary(items):
    """Almanya bağlantılı yazar/kurumları sayar (Aşama 6)."""
    from collections import Counter
    inst, auth = Counter(), Counter()
    for it in items:
        for a in it["affiliations"]:
            if a.endswith("(DE)"): inst[a] += 1
        if any(a.endswith("(DE)") for a in it["affiliations"]):
            for a in it["authors"][:3]: auth[a] += 1
    return inst.most_common(10), auth.most_common(10)

def fetch_page_text(url, limit=12000):
    """DAAD çağrı sayfası gibi güncel metinleri çeker."""
    r = requests.get(url, headers=UA, timeout=30); r.raise_for_status()
    s = BeautifulSoup(r.text, "html.parser")
    for t in s(["script", "style", "nav", "footer"]): t.decompose()
    return re.sub(r"\n{2,}", "\n", s.get_text("\n"))[:limit]

# --- Deterministik APA 7 biçimlendirme (LLM'e bırakılmaz) ---
def _apa_name(n):
    p = n.split()
    return f"{p[-1]}, " + " ".join(x[0] + "." for x in p[:-1]) if len(p) > 1 else n

def apa(it):
    a = [_apa_name(x) for x in it["authors"][:20]]
    au = (", ".join(a[:-1]) + ", & " + a[-1]) if len(a) > 1 else (a[0] if a else "")
    vol = f", {it['volume']}" if it.get("volume") else ""
    iss = f"({it['issue']})" if it.get("issue") else ""
    pg = f", {it['pages']}" if it.get("pages") else ""
    doi = f" https://doi.org/{it['doi']}" if it.get("doi") else ""
    return f"{au} ({it['year']}). {it['title']}. {it['venue']}{vol}{iss}{pg}.{doi}"
