import sys
import json
import os
import subprocess
import time
import shutil
import tempfile
import zipfile

import requests

UA = {"User-Agent": "Mozilla/5.0"}


def download_with_retries(url: str, dest_path: str, retries: int = 5, timeout: int = 180):
    """
    Download a file completely using streaming.
    Retries automatically on failures.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)

            with requests.get(url, stream=True, timeout=timeout, headers=UA, allow_redirects=True) as r:
                r.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):  # 1 MB
                        if chunk:
                            f.write(chunk)

            # Treat very small downloads as failures (0-byte / HTML error pages / bad redirects)
            if os.path.getsize(dest_path) < 5 * 1024 * 1024:
                raise RuntimeError(
                    f"Downloaded file too small: {os.path.getsize(dest_path)} bytes"
                )

            return
        except Exception as e:
            last_err = e
            print(f"Download failed (attempt {attempt}/{retries}) for {url}: {e}")
            time.sleep(min(60, 2 ** attempt))

    raise RuntimeError(
        f"Failed to download after {retries} attempts: {url}\nLast error: {last_err}"
    )


def replace_update_binary(zip_path: str) -> None:
    """
    Replace META-INF/com/google/android/update-binary with a shell wrapper
    that forwards execution to /system/bin/updater.
    """
    with tempfile.TemporaryDirectory() as td:
        extract_dir = os.path.join(td, "extract")
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        ub_path = os.path.join(
            extract_dir, "META-INF", "com", "google", "android", "update-binary"
        )
        os.makedirs(os.path.dirname(ub_path), exist_ok=True)

        with open(ub_path, "w", encoding="utf-8") as f:
            f.write("#!/sbin/sh\n")
            f.write('exec /system/bin/updater "$@"\n')

        os.chmod(ub_path, 0o755)

        tmp_zip = zip_path + ".tmp"
        with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(extract_dir):
                for name in files:
                    full = os.path.join(root, name)
                    rel = os.path.relpath(full, extract_dir)
                    zf.write(full, rel)

        os.replace(tmp_zip, zip_path)


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

        # 1) Download the ZIP locally first to avoid remote range/stream issues
        local_zip = os.path.join(
            tmp, f"input_{safe_region}_{version}.zip".replace("/", "_")
        )
        print(f"[{region}] downloading to {local_zip}")
        download_with_retries(zip_url, local_zip)

        # 2) Build the flashable firmware from the local ZIP
        print(f"[{region}] building FW from local zip")
        subprocess.check_call([
            "xiaomi_flashable_firmware_creator",
            "-F",
            local_zip,
            "-o",
            tmp
        ])

        # 3) Move the generated ZIP to the output directory
        zips = sorted([f for f in os.listdir(tmp) if f.endswith(".zip")])
        if not zips:
            raise SystemExit(f"{region}: output zip not found")

        src = os.path.join(tmp, zips[0])
        dst = os.path.join(
            out_dir, f"FW_onyx_{safe_region}_{version}.zip".replace("/", "_")
        )
        os.replace(src, dst)

        # 4) Replace update-binary with the shell wrapper
        print(f"[{region}] post-processing update-binary")
        replace_update_binary(dst)

        print(f"[{region}] output: {dst}")

        # 5) Clean up temporary files
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"[{region}] cleaned temp folder")


if __name__ == "__main__":
    main()
