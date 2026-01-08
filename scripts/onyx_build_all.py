import sys, json, os, subprocess, time
import requests

UA = {"User-Agent": "Mozilla/5.0"}

def download_with_retries(url: str, dest_path: str, retries: int = 5, timeout: int = 120):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)

            with requests.get(url, stream=True, timeout=timeout, headers=UA, allow_redirects=True) as r:
                r.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)

            if os.path.getsize(dest_path) < 5 * 1024 * 1024:
                raise RuntimeError(f"Downloaded file too small ({os.path.getsize(dest_path)} bytes)")

            return
        except Exception as e:
            last_err = e
            print(f"Download failed {attempt}/{retries} for {url}: {e}")
            time.sleep(min(60, 2 ** attempt))

    raise RuntimeError(f"Failed to download: {url}\nLast error: {last_err}")

def main():
    roms = json.loads(sys.argv[1])
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)

    for region, info in roms.items():
        zip_url = info["zip"]
        version = info["version"]

        safe_region = region.lower()
        tmp = os.path.join(out_dir, f"tmp_{region}")
        os.makedirs(tmp, exist_ok=True)

        local_zip = os.path.join(tmp, f"input_{safe_region}_{version}.zip".replace("/", "_"))
        print(f"[{region}] downloading ROM: {zip_url}")
        download_with_retries(zip_url, local_zip)

        print(f"[{region}] building FW from local file")
        subprocess.check_call([
            "xiaomi_flashable_firmware_creator",
            "-F",
            local_zip,
            "-o",
            tmp
        ])

        generated = sorted([f for f in os.listdir(tmp) if f.endswith(".zip")])
        if not generated:
            raise RuntimeError(f"{region}: no output zip found")

        src = os.path.join(tmp, generated[0])
        dst = os.path.join(out_dir, f"FW_onyx_{safe_region}_{version}.zip".replace("/", "_"))
        os.replace(src, dst)

if __name__ == "__main__":
    main()
