import os, json, re, hashlib, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://mifirm.net"
ONYX_PAGE = "https://mifirm.net/model/onyx.ttt"
STATE_PATH = "state/onyx_last.txt"

# MiFirm tarafındaki etiketler -> bizim sabit region isimlerimiz
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

def fetch(url: str) -> str:
    r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text

def clean(s: str) -> str:
    return " ".join((s or "").split())

def extract_direct_zip(download_page_url: str) -> str:
    """
    MiFirm /downloadzip/<id> sayfasından direkt .zip URL'sini yakala.
    (HTML içinde link ya da script içinde URL olarak geçebiliyor -> soup + regex)
    """
    html = fetch(download_page_url)

    soup = BeautifulSoup(html, "lxml")
    for a in soup.select("a[href]"):
        href = a["href"].strip()
        if href.lower().endswith(".zip"):
            return href if href.startswith("http") else urljoin(BASE, href)

    m = re.search(r'https?://[^\s"\']+\.zip', html, re.I)
    if m:
        return m.group(0)

    raise RuntimeError(f"No direct .zip link found in: {download_page_url}")

def main():
    last_state = ""
    if os.path.exists(STATE_PATH):
        last_state = open(STATE_PATH, "r", encoding="utf-8").read().strip()

    html = fetch(ONYX_PAGE)
    soup = BeautifulSoup(html, "lxml")

    # MiFirm sayfasında başlıklar şu formatta:
    # "#### Redmi Turbo 4 Pro ZIP Stable <Region>"
    # Biz sadece "ZIP Stable" başlıklarını alacağız.
    best = {}  # mifirm_region -> (updated_at, version, download_page_url)

    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
        title = clean(h.get_text(" ", strip=True))
        tlow = title.lower()

        if "zip stable" not in tlow:
            continue

        mifirm_region = None
        for r in MIFIRM_REGIONS:
            if r.lower() in tlow:
                mifirm_region = r
                break
        if not mifirm_region:
            continue

        table = h.find_next("table")
        if not table:
            continue

        # Satırlar: MIUI version | Android version | File size | Update at | Downloaded | Download
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 6:
                continue

            version = clean(tds[0].get_text(" ", strip=True))
            updated_at = clean(tds[3].get_text(" ", strip=True))  # "YYYY-MM-DD HH:MM:SS"
            a = tds[-1].find("a", href=True)
            if not a:
                continue

            download_page_url = urljoin(BASE, a["href"].strip())

            prev = best.get(mifirm_region)
            # Bu timestamp formatı string compare ile doğru sıralanıyor
            if prev is None or (updated_at and updated_at > prev[0]):
                best[mifirm_region] = (updated_at, version, download_page_url)

    if not best:
        raise SystemExit("No ZIP Stable rows found on MiFirm onyx page (layout may have changed).")

    # Normalize edilmiş region isimleriyle roms_json üret
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

    release_tag = f"onyx-{new_state[:12]}"
    release_title = "onyx firmware set"
    release_notes = "Auto-generated firmware set for onyx (ZIP stable, multi-region) from MiFirm."

    print(f"has_update={'true' if has_update else 'false'}")
    print(f"new_state={new_state}")
    print(f"release_tag={release_tag}")
    print(f"release_title={release_title}")
    print(f"release_notes={release_notes}")
    print("roms_json=" + json.dumps(roms))
    print("summary=" + " | ".join(summary_parts))

if __name__ == "__main__":
    main()
