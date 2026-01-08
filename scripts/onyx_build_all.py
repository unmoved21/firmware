import sys, json, os, subprocess, time, shutil
import requests

UA = {"User-Agent": "Mozilla/5.0"}

def download_with_retries(url: str, dest_path: str, retries: int = 5, timeout: int = 180):
    """
    Dosyayı tam indirir (stream). Kopmalarda retry yapar.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)

            with requests.get(url, stream=True, timeout=timeout, headers=UA, allow_redirects=True) as r:
                r.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):  # 1MB
                        if chunk:
                            f.write(chunk)

            # Çok küçük dosya indiyse başarısız say (0-byte / HTML indirimi vs.)
            if os.path.getsize(dest_path) < 5 * 1024 * 1024:
                raise RuntimeError(f"Downloaded file too small: {os.path.getsize(dest_path)} bytes")

            return
        except Exception as e:
            last_err = e
            print(f"Download failed (attempt {attempt}/{retries}) for {url}: {e}")
            time.sleep(min(60, 2 ** attempt))

    raise RuntimeError(f"Failed to download after {retries} attempts: {url}\nLast error: {last_err}")

def main():
    roms = json.loads(sys.argv[1])
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)

    for region, info in roms.items():
        zip_url = info["zip"]
        version = info["version"]

        print(f"[{region}] ROM: {zip_url}")

        safe_region = region.lower()
        tmp = os.path.join(out_dir, f"tmp_{region}")
        os.makedirs(tmp, exist_ok=True)

        # 1) ZIP'i önce lokal indir (remotezip/Range hatalarını ve kopmaları azaltır)
        local_zip = os.path.join(tmp, f"input_{safe_region}_{version}.zip".replace("/", "_"))
        print(f"[{region}] downloading to {local_zip}")
        download_with_retries(zip_url, local_zip)

        # 2) Lokal ZIP ile FW üret
        print(f"[{region}] building FW from local zip")
        subprocess.check_call([
            "xiaomi_flashable_firmware_creator",
            "-F",
            local_zip,
            "-o",
            tmp
        ])

        # 3) Çıktıyı out'a taşı
        zips = sorted([f for f in os.listdir(tmp) if f.endswith(".zip")])
        if not zips:
            raise SystemExit(f"{region}: output zip not found")

        src = os.path.join(tmp, zips[0])
        dst = os.path.join(out_dir, f"FW_onyx_{safe_region}_{version}.zip".replace("/", "_"))
        os.replace(src, dst)
        print(f"[{region}] output: {dst}")

        # 4) Disk boşalt: temp'i (ve indirdiğimiz zip'i) sil
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"[{region}] cleaned temp folder")

if __name__ == "__main__":
    main()
