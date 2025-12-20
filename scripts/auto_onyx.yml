import sys, json, os, subprocess

def main():
    roms = json.loads(sys.argv[1])
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)

    for region, info in roms.items():
        zip_url = info["zip"]
        version = info["version"]

        print(f"[{region}] building FW from {zip_url}")
        tmp = os.path.join(out_dir, f"tmp_{region}")
        os.makedirs(tmp, exist_ok=True)

        # -F normal firmware
        subprocess.check_call([
            "xiaomi_flashable_firmware_creator",
            "-F",
            zip_url,
            "-o",
            tmp
        ])

        zips = sorted([f for f in os.listdir(tmp) if f.endswith(".zip")])
        if not zips:
            raise SystemExit(f"{region}: output zip not found")

        src = os.path.join(tmp, zips[0])
        safe_region = region.lower()
        dst = os.path.join(out_dir, f"FW_onyx_{safe_region}_{version}.zip".replace("/", "_"))
        os.replace(src, dst)

if __name__ == "__main__":
    main()
