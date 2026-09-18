#!/usr/bin/env python3
"""
harvest_all_ohio.py - Batch harvest Ohio OCV packages via Aurora Store.

Enforces strict VM hygiene: immediately uninstalls each app after APKs are backed up.
Extracts strings and resources with `jadx -s` for rapid credential analysis.
"""

import os
import sys
import time
import subprocess
from datetime import datetime
from aurora_harvest import harvest_package, log

TARGETS = [
    {"pkg": "com.ocv.madisonCounyOHSheriff", "name": "madison"},
    {"pkg": "com.ocv.a1290", "name": "geauga"},
    {"pkg": "com.ocv.hardincountysheriffoh", "name": "hardin"},
    {"pkg": "com.ocv.hockingcountyohsheriff", "name": "hocking"},
    {"pkg": "com.ocv.holmescoohsheriff", "name": "holmes"},
    {"pkg": "com.ocv.senecacountysheriffoh", "name": "seneca"},
    {"pkg": "com.ocv.a1116", "name": "trumbull"},
    {"pkg": "com.ocv.a1153", "name": "van_wert"},
    {"pkg": "com.ocv.a883", "name": "sandusky"},
    {"pkg": "com.ocv.a1434", "name": "ashland"},
    {"pkg": "com.ocv.a1598", "name": "ashtabula"},
    {"pkg": "com.ocvapps.columbianacountysheriffoh", "name": "columbiana"},
    {"pkg": "com.ocv.a1610", "name": "defiance"},
    {"pkg": "com.ocv.a1503", "name": "hancock"},
    {"pkg": "com.ocv.a1380", "name": "jefferson"},
    {"pkg": "com.ocv.a1573", "name": "putnam"},
    {"pkg": "com.ocv.a1502", "name": "tuscarawas"},
    {"pkg": "com.ocv.plainohpd", "name": "plain_city"}
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APK_DIR = os.path.join(BASE_DIR, "apk")

def decompile_resources(name: str):
    target_dir = os.path.join(APK_DIR, name)
    decomp_dir = os.path.join(target_dir, "decompiled")
    
    # Find base apk
    base_apk = os.path.join(target_dir, "base.apk")
    if not os.path.exists(base_apk):
        for f in os.listdir(target_dir):
            if f.endswith(".apk") and not f.startswith("config.") and not f.startswith("split_"):
                base_apk = os.path.join(target_dir, f)
                break
                
    if not os.path.exists(base_apk):
        log(f"No base APK found to decompile in {target_dir}")
        return

    if os.path.exists(decomp_dir) and os.path.exists(os.path.join(decomp_dir, "resources")):
        log(f"Resources already decompiled for {name}")
        return

    log(f"Decompiling resources with jadx -s for '{name}'...")
    cmd = ["jadx", "-s", "-d", decomp_dir, base_apk]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 or os.path.exists(os.path.join(decomp_dir, "resources")):
        log(f"Successfully extracted resources for '{name}'")
    else:
        log(f"jadx warning/error for '{name}': {res.stderr[:200]}")

def run_batch():
    total = len(TARGETS)
    log(f"Starting batch harvest of {total} Ohio OCV packages via Aurora Store...")
    
    successes = []
    failures = []
    
    for idx, target in enumerate(TARGETS, 1):
        pkg = target["pkg"]
        name = target["name"]
        log(f"[{idx}/{total}] Processing {name} ({pkg})...")
        
        try:
            ok = harvest_package(pkg, name)
            if ok:
                successes.append(name)
                # Rapidly extract resources
                decompile_resources(name)
            else:
                failures.append((name, pkg))
        except Exception as e:
            log(f"Exception during harvest of {name}: {e}")
            failures.append((name, pkg))
            
        time.sleep(2)
        
    log(f"=== BATCH COMPLETE ===")
    log(f"Successes ({len(successes)}): {', '.join(successes)}")
    if failures:
        log(f"Failures ({len(failures)}): {failures}")

if __name__ == "__main__":
    run_batch()
