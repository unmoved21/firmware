import os, json, re, hashlib, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://xmfirmwareupdater.com"
ONYX_PAGE = "https://xmfirmwareupdater.com/hyperos/onyx/"
STATE_PATH = "state/onyx_last.txt"

WANTED = ["China", "EEA", "Global", "Indonesia", "India", "Russia", "Taiwan"]

def fetch(url):
    r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text

def clean(s: str) -> str:
    return " ".join((s or "").split())

def extract_first_zip_mirror(update_url: str) -> str:
    html = fetch(update_url)
    soup = BeautifulSoup(html, "lxml")

    # 1) .zip linklerini direkt yakala
    for a in soup.select("a[href]"):
        href = a["href"].strip()
        if href.lower().endswith(".zip"):
            return href

    # 2) fallback regex
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

    table = soup.find("table")
    if not table:
        raise SystemExit("No table found on onyx page.")

    best = {}  # region -> (date, version, update_url)

    for tr in table.find_all("tr"):
        # td + th birlikte
        cells = tr.find_all(["td", "th"])
        if len(cells) < 8:
            continue

        texts = [clean(c.get_text(" ", strip=True)) for c in cells[:8]]

        device = texts[0]
        branch = texts[1]      # Stable / Stable Beta
        rom_type = texts[2]    # Fastboot / Recovery
        version = texts[3]     # OSx.x.x.x...
        date = texts[6]

        a = cells[7].find("a", href=True)
        if not a:
            continue

        # Sadece Stable + Recovery
        if "stable" not in branch.lower():
            continue
        if "beta" in branch.lower():
            continue
        if rom_type.lower() != "recovery":
            continue

        # Region tespiti: device isminden
        region = None
        dlow = device.lower()
        for w in WANTED:
            if w.lower() in dlow:
                region = w
                break
        if not region:
            continue

        update_url = urljoin(BASE, a["href"].strip())

        prev = best.get(region)
        if prev is None or (date and date > prev[0]):
            best[region] = (date, version, update_url)

    if not best:
        raise SystemExit("No stable recovery rows found on onyx page.")

    roms = {}
    summary_parts = []

    for region, (date, version, update_url) in best.items():
        zip_url = extract_first_zip_mirror(update_url)
        roms[region] = {"date": date, "version": version, "zip": zip_url, "update": update_url}
        summary_parts.append(f"{region}: {version} ({date})")

    state_raw = json.dumps(roms, sort_keys=True)
    new_state = hashlib.sha256(state_raw.encode("utf-8")).hexdigest()
    has_update = (new_state != last_state)

    release_tag = f"onyx-{new_state[:12]}"
    release_title = "onyx firmware set"
    release_notes = "Auto-generated firmware set for onyx (stable recovery, multi-region)."

    # GitHub Actions outputs (GITHUB_OUTPUT’e append ediliyor)
    print(f"has_update={'true' if has_update else 'false'}")
    print(f"new_state={new_state}")
    print(f"release_tag={release_tag}")
    print(f"release_title={release_title}")
    print(f"release_notes={release_notes}")
    print("roms_json=" + json.dumps(roms))
    print("summary=" + " | ".join(summary_parts))

if __name__ == "__main__":
    main()
