import os, json, re, hashlib, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://mifirm.net"
ONYX_PAGE = "https://mifirm.net/model/onyx.ttt"
STATE_PATH = "state/onyx_last.txt"

# MiFirm region etiketleri -> normalize
REGION_MAP = {
    "China": "China",
    "Global": "Global",
    "EEA": "EEA",
    "Taiwan": "Taiwan",
    "Indo": "Indonesia",
    "Indian": "India",
    "Russian": "Russia",
}
MIFIRM_REGIONS = list(REGION_MAP.keys())

UA = {"User-Agent": "Mozilla/5.0"}

def fetch(url: str) -> str:
    r = requests.get(url, timeout=60, headers=UA)
    r.raise_for_status()
    return r.text

def clean(s: str) -> str:
    return " ".join((s or "").split())

def parse_value_after_label(lines: list[str], label: str) -> str | None:
    for i, line in enumerate(lines):
        if line == label:
            for j in range(i + 1, min(i + 10, len(lines))):
                if lines[j]:
                    return lines[j]
            return None
    return None

def url_alive(url: str) -> bool:
    try:
        r = requests.get(url, timeout=25, headers={**UA, "Range": "bytes=0-0"}, stream=True, allow_redirects=True)
        return r.status_code in (200, 206)
    except:
        return False

def extract_direct_zip(download_page_url: str) -> str:
    html = fetch(download_page_url)
    soup = BeautifulSoup(html, "lxml")

    # Direkt .zip link var mı?
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if href.lower().endswith(".zip"):
            return href if href.startswith("http") else urljoin(BASE, href)

    # HTML içinde zip geçiyor mu?
    m = re.search(r'https?://[^\s"\']+\.zip', html, re.I)
    if m:
        return m.group(0)

    # MIUI version + File name parse
    text = soup.get_text("\n", strip=True)
    lines = [clean(x) for x in text.splitlines() if clean(x)]

    version = parse_value_after_label(lines, "MIUI version")
    filename = parse_value_after_label(lines, "File name")
    if not version or not filename:
        raise RuntimeError(f"Cannot find MIUI version or File name in {download_page_url}")

    # bn.d.miui.com öncelikli + fallback
    candidates = [
        f"https://bn.d.miui.com/{version}/{filename}",
        f"https://bigota.d.miui.com/{version}/{filename}",
        f"https://hugeota.d.miui.com/{version}/{filename}",
    ]
    for u in candidates:
        if url_alive(u):
            return u

    # hiç olmazsa bn döndür
    return candidates[0]

def main():
    last_state = ""
    if os.path.exists(STATE_PATH):
        last_state = open(STATE_PATH, "r", encoding="utf-8").read().strip()

    html = fetch(ONYX_PAGE)
    soup = BeautifulSoup(html, "lxml")

    best = {}

    for h in soup.find_all(["h1","h2","h3","h4","h5"]):
        title = clean(h.get_text(" ", strip=True))
        if "zip stable" not in title.lower():
            continue

        region_tag = None
        tlow = title.lower()
        for r in MIFIRM_REGIONS:
            if r.lower() in tlow:
                region_tag = r
                break
        if not region_tag:
            continue

        table = h.find_next("table")
        if not table:
            continue

        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 6:
                continue

            version = clean(tds[0].get_text(" ", strip=True))
            updated_at = clean(tds[3].get_text(" ", strip=True))
            a = tds[-1].find("a", href=True)
            if not a:
                continue

            download_page_url = urljoin(BASE, a["href"].strip())

            prev = best.get(region_tag)
            if prev is None or (updated_at and updated_at > prev[0]):
                best[region_tag] = (updated_at, version, download_page_url)

    if not best:
        raise SystemExit("No ZIP Stable found on MiFirm")

    roms = {}
    summary_parts = []

    for mifirm_region, (updated_at, version, download_page_url) in best.items():
        region = REGION_MAP[mifirm_region]
        zip_url = extract_direct_zip(download_page_url)

        roms[region] = {
            "date": updated_at,
            "version": version,
            "zip": zip_url,
            "update": download_page_url,
        }
        summary_parts.append(f"{region}: {version} ({updated_at})")

    state_raw = json.dumps(roms, sort_keys=True)
    new_state = hashlib.sha256(state_raw.encode("utf-8")).hexdigest()
    has_update = (new_state != last_state)

    print(f"has_update={'true' if has_update else 'false'}")
    print(f"new_state={new_state}")
    print(f"release_tag=onyx-{new_state[:12]}")
    print(f"release_title=onyx firmware set")
    print(f"release_notes=Auto firmware set from MiFirm + bn.d.miui.com")
    print("roms_json=" + json.dumps(roms))
    print("summary=" + " | ".join(summary_parts))

if __name__ == "__main__":
    main()
