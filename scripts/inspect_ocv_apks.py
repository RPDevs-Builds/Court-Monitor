#!/usr/bin/env python3
"""
Inspect decompiled/extracted OCV APK resources to extract:
- App Name & Label
- Internal Client ID (app_id: e.g. a26544113, a44944077, a54444705)
- App Client ID & App Client Secret
- Feed & Share endpoints
"""

import os
import subprocess
from pathlib import Path

AAPT = "/mnt/largedata/appdata/android-sdk/build-tools/34.0.0/aapt"
APK_DIR = Path("/home/llmuser/projects/court-monitor/apk")

def extract_strings_from_apk(apk_path):
    cmd = [AAPT, "dump", "--values", "resources", str(apk_path)]
    p = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
    out = p.stdout
    
    extracted = {}
    keys = ["app_id", "app_label", "app_name", "appClientId", "appClientSecret", "app_secret"]
    lines = out.splitlines()
    for idx, line in enumerate(lines):
        for k in keys:
            if f":string/{k}:" in line:
                for offset in range(1, 4):
                    if idx + offset < len(lines):
                        nxt = lines[idx + offset]
                        if "(string8)" in nxt or "(string16)" in nxt:
                            val = nxt.split(")")[-1].strip().strip('"')
                            extracted[k] = val
                            break
    return extracted

def inspect_all():
    results = {}
    for sub in sorted(APK_DIR.iterdir()):
        if not sub.is_dir():
            continue
        apks = list(sub.glob("*.apk"))
        main_apk = None
        for a in apks:
            if not a.name.startswith("config.") and not a.name.startswith("split_"):
                main_apk = a
                break
        if not main_apk and apks:
            main_apk = apks[0]
            
        if main_apk:
            meta = extract_strings_from_apk(main_apk)
            results[sub.name] = {
                "folder": str(sub),
                "main_apk": str(main_apk.name),
                "metadata": meta
            }
            app_id = meta.get("app_id")
            if app_id:
                results[sub.name]["share_url"] = f"https://apps.myocv.com/share/{app_id}"
                results[sub.name]["rtjb_feed_url"] = f"https://apps.myocv.com/feed/rtjb/{app_id}/Inmates"
                results[sub.name]["s3_base"] = f"https://s3.amazonaws.com/myocv/ocvapps/{app_id}/"
    return results

if __name__ == "__main__":
    import json
    data = inspect_all()
    print(json.dumps(data, indent=2))
