#!/usr/bin/env python3
"""
aurora_harvest.py - Automated acquisition of APK packages via Aurora Store on Android VM.

Workflow:
1. Navigates Aurora Store to the target package details page.
2. Taps 'Install' in Aurora Store.
3. Automatically confirms 'Install' in the Android Package Installer prompt.
4. Waits for installation confirmation and queries `pm path <pkg>`.
5. Pulls base and split APKs to host directory `apk/<target_name>/`.
6. IMMEDIATELY uninstalls the package from the VM via `pm uninstall <pkg>` to keep VM clean.
"""

import os
import sys
import time
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime

ADB_DEVICE = "emulator-5558"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APK_DIR = os.path.join(BASE_DIR, "apk")

def log(msg: str):
    now = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{now} {msg}", flush=True)

def adb_cmd(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    cmd = ["adb", "-s", ADB_DEVICE] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

def dump_ui() -> ET.Element | None:
    try:
        res = adb_cmd(["shell", "uiautomator", "dump", "/sdcard/ui_dump.xml"], timeout=10)
        if res.returncode != 0:
            return None
        res2 = adb_cmd(["shell", "cat", "/sdcard/ui_dump.xml"], timeout=10)
        if res2.returncode != 0 or not res2.stdout.strip():
            return None
        return ET.fromstring(res2.stdout)
    except Exception as e:
        log(f"UI dump error: {e}")
        return None

def find_node(root: ET.Element, text_match: str = None, res_id_match: str = None, pkg_match: str = None):
    if root is None:
        return None
    for el in root.iter("node"):
        txt = el.attrib.get("text", "")
        res = el.attrib.get("resource-id", "")
        pkg = el.attrib.get("package", "")
        
        t_ok = (text_match is None) or (text_match.lower() == txt.lower())
        r_ok = (res_id_match is None) or (res_id_match.lower() in res.lower())
        p_ok = (pkg_match is None) or (pkg_match.lower() in pkg.lower())
        
        if t_ok and r_ok and p_ok:
            return el
    return None

def parse_bounds(bounds_str: str) -> tuple[int, int]:
    # format: [left,top][right,bottom]
    # e.g.: [810,1312][978,1454]
    parts = bounds_str.replace("][", ",").replace("[", "").replace("]", "").split(",")
    left, top, right, bottom = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
    return (left + right) // 2, (top + bottom) // 2

def tap(x: int, y: int):
    adb_cmd(["shell", "input", "tap", str(x), str(y)])

def is_installed(package: str) -> bool:
    res = adb_cmd(["shell", "pm", "list", "packages", package])
    return f"package:{package}" in res.stdout

def uninstall(package: str):
    log(f"Enforcing clean VM state: Uninstalling {package}...")
    res = adb_cmd(["shell", "pm", "uninstall", package])
    log(f"Uninstall result: {res.stdout.strip() or res.stderr.strip()}")

def get_apk_paths(package: str) -> list[str]:
    res = adb_cmd(["shell", "pm", "path", package])
    paths = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            paths.append(line.replace("package:", "").strip())
    return paths

def harvest_package(pkg: str, name: str) -> bool:
    log(f"=== Starting harvest for '{name}' ({pkg}) ===")
    
    # 0. Clean prior state if already installed
    if is_installed(pkg):
        uninstall(pkg)

    target_dir = os.path.join(APK_DIR, name)
    os.makedirs(target_dir, exist_ok=True)
    
    # Check if base.apk or main apk already exists
    existing = [f for f in os.listdir(target_dir) if f.endswith(".apk")]
    if existing:
        log(f"Package '{name}' already has local APKs in {target_dir}: {existing}")
        return True

    # 1. Launch Aurora Store to package detail screen
    log(f"Opening Aurora Store details for {pkg}...")
    adb_cmd(["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", f"market://details?id={pkg}", "-p", "com.aurora.store"])
    time.sleep(3)

    # 2. Find and tap 'Install' button in Aurora Store
    installed_node = None
    for attempt in range(6):
        tree = dump_ui()
        install_btn = find_node(tree, text_match="Install", res_id_match="btn_primary_action")
        if install_btn is not None:
            cx, cy = parse_bounds(install_btn.attrib["bounds"])
            log(f"Found Aurora 'Install' button at ({cx}, {cy}). Tapping...")
            tap(cx, cy)
            break
        time.sleep(1.5)
    else:
        # Fallback coordinate if found on pixel 34
        log("Warning: Could not dynamically locate Aurora Install button, trying standard coords (806, 637)...")
        tap(806, 637)

    # 3. Wait for Package Installer confirmation prompt or download completion
    log(f"Waiting for download and Package Installer prompt for {pkg}...")
    start_time = time.time()
    
    while time.time() - start_time < 120:
        if is_installed(pkg):
            log(f"Package {pkg} is already installed!")
            break
            
        tree = dump_ui()
        if tree is not None:
            # Look for system PackageInstaller "Install" button
            pkg_installer_btn = find_node(tree, text_match="Install", pkg_match="packageinstaller")
            if pkg_installer_btn is not None:
                cx, cy = parse_bounds(pkg_installer_btn.attrib["bounds"])
                log(f"Found PackageInstaller confirmation dialog 'Install' at ({cx}, {cy}). Tapping...")
                tap(cx, cy)
                time.sleep(3)
                continue

            # Look for generic Install button if packageinstaller package differs
            install_nodes = [el for el in tree.iter("node") if el.attrib.get("text", "") == "Install"]
            for node in install_nodes:
                if "com.aurora.store" not in node.attrib.get("package", ""):
                    cx, cy = parse_bounds(node.attrib["bounds"])
                    log(f"Found system dialog 'Install' at ({cx}, {cy}). Tapping...")
                    tap(cx, cy)
                    time.sleep(3)
                    break
        time.sleep(2)

    # 4. Verify installation
    if not is_installed(pkg):
        log(f"ERROR: {pkg} failed to install within timeout.")
        return False

    log(f"SUCCESS: {pkg} is installed. Pulling APK files...")
    apk_paths = get_apk_paths(pkg)
    if not apk_paths:
        log(f"ERROR: Could not retrieve APK paths for {pkg}!")
        uninstall(pkg)
        return False

    for remote_path in apk_paths:
        fname = os.path.basename(remote_path)
        dest_path = os.path.join(target_dir, fname)
        log(f"Pulling {remote_path} -> {dest_path}")
        adb_cmd(["pull", remote_path, dest_path], timeout=60)

    # 5. IMMEDIATELY uninstall package to restore clean state
    uninstall(pkg)

    # 6. Verify VM is clean
    if is_installed(pkg):
        log(f"WARNING: {pkg} still reports installed after uninstall attempt!")
    else:
        log(f"Verified: {pkg} completely uninstalled. VM is clean.")

    log(f"=== Harvest complete for '{name}' ===")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <package_name> <folder_name>")
        sys.exit(1)
    
    pkg = sys.argv[1]
    name = sys.argv[2]
    success = harvest_package(pkg, name)
    sys.exit(0 if success else 1)
