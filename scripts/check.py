import os, json, re, hashlib, requests
from bs4 import BeautifulSoup

ONYX_PAGE = "https://xmfirmwareupdater.com/hyperos/onyx/"
STATE_PATH = "state/onyx_last.txt"

# Biz sadece bu bölgeleri istiyoruz (sayfada varsa alır)
WANTED = ["China", "EEA", "Global", "Indonesia", "India", "Russia", "Taiwan"]

def get_text(el):
    return " ".join(el.get_text(" ", strip=True).split())

def fetch(url):
    r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text

def extract_first_zip_mirror(update_url: str) -> str:
    html = fetch(update_url)
    # Sayfada genelde birden çok mirror var; direkt .zip linkini yakala
    # bs4 ile tüm <a href> çekiyoruz
    soup = BeautifulSoup(html, "lxml")
    for a in soup.select("a[href]"):
        href = a["href"].strip()
        if href.lower().endswith(".zip") and ("ota" in href.lower() or "full" in href.lower()):
            return href
    # fallback: regex
    m = re.search(r'https?://[^\s"\']+\.zip', html, re.I)
    if m:
        return m.group(0)
    raise RuntimeError(f"No .zip mirror found in update page: {update_url}")

def main():
    last_state = ""
    if os.path.exists(STATE_PATH):
        last_state = open(STATE_PATH, "r", encoding="utf-8").read().strip()

    html = fetch(ONYX_PAGE)
    soup = BeautifulSoup(html, "lxml")

    # tablo satırları
    rows = soup.select("table tbody tr")
    if not rows:
        # bazı temalarda table direkt tr olabilir
        rows = soup.select("tr")

    # region -> (date, version, update_page_url)
    best = {}

    for tr in rows:
        tds = tr.find_all(["td", "th"])
        if len(tds) < 8:
            continue

        device = get_text(tds[0])
        branch = get_text(tds[1])
        rom_type = get_text(tds[2])  # Fastboot / Recovery
        version = get_text(tds[3])
        date = get_text(tds[6])
        link_el = tds[7].find("a", href=True)
        if not link_el:
            continue

        if branch.lower() != "stable":
            continue
        if rom_type.lower() != "recovery":
            continue
        if "onyx" not in (device.lower() + " " + version.lower()):
            continue

        # region adı: Device kolonundan çek (China/EEA/Global/...)
        region = None
        for w in WANTED:
            if w.lower() in device.lower():
                region = w
                break
        if not region:
            continue

        update_url = link_el["href"]
        # aynı region için en yeni date’yi seç
        prev = best.get(region)
        if (prev is None) or (date and date > prev[0]):
            best[region] = (date, version, update_url)

    if not best:
        raise SystemExit("No stable recovery rows found on onyx page.")

    roms = {}
    summary_parts = []

    # Her region için direct zip çıkar
    for region, (date, version, update_url) in best.items():
        zip_url = extract_first_zip_mirror(update_url)
        roms[region] = {"date": date, "version": version, "zip": zip_url, "update": update_url}
        summary_parts.append(f"{region}: {version} ({date})")

    # state hash: rom zip linkleri + versiyonlar
    state_raw = json.dumps(roms, sort_keys=True)
    new_state = hashlib.sha256(state_raw.encode("utf-8")).hexdigest()
    has_update = (new_state != last_state)

    release_tag = f"onyx-{new_state[:12]}"
    release_title = "onyx firmware set"
    release_notes = "Auto-generated firmware set for onyx (stable recovery, multi-region)."

    # GitHub output (GITHUB_OUTPUT’e yazılıyor)
    print(f"has_update={'true' if has_update else 'false'}")
    print(f"new_state={new_state}")
    print(f"release_tag={release_tag}")
    print(f"release_title={release_title}")
    print(f"release_notes={release_notes}")
    print("roms_json=" + json.dumps(roms))
    print("summary=" + " | ".join(summary_parts))

if __name__ == "__main__":
    main()
