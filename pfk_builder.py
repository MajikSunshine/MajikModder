#!/usr/bin/env python
"""
PFK registry builder

- Script location: mods/<ModName>/file_sync
- Global PFk:      mods/_assets/YAML/pfk_global.yaml
- Local PFk:       mods/<ModName>/_assets/YAML/pfk.yaml

Scans:
- Main I3D:        ../<ModName>/MajikTruck/*.i3d
- Sync I3Ds:       ./*.i3d   (in file_sync)
"""

import os
import glob
import hashlib
import xml.etree.ElementTree as ET
import yaml  # PyYAML

# ---- CONFIG -----------------------------------------------------------------

# Detect script location (mods/<ModName>/file_sync)
script_dir = os.path.dirname(os.path.abspath(__file__))
print(f"[CFG] script_dir      = {script_dir}")

# Mod directory = parent of file_sync (mods/<ModName>)
mod_dir = os.path.dirname(script_dir)
print(f"[CFG] mod_dir         = {mod_dir}")

# mods root = parent of mod directory (mods/)
mods_root = os.path.dirname(mod_dir)
print(f"[CFG] mods_root       = {mods_root}")

# Local registry path (mods/<ModName>/_assets/YAML/pfk.yaml)
LOCAL_PFK_PATH = os.path.join(mod_dir, "_assets", "YAML", "pfk.yaml")
print(f"[CFG] LOCAL_PFK_PATH  = {LOCAL_PFK_PATH}")

# Global registry path (mods/_assets/YAML/pfk_global.yaml)
GLOBAL_PFK_PATH = os.path.join(mods_root, "_assets", "YAML", "pfk_global.yaml")
print(f"[CFG] GLOBAL_PFK_PATH = {GLOBAL_PFK_PATH}")

# Local PMK registry path (mods/<ModName>/_assets/YAML/pmk.yaml)
LOCAL_PMK_PATH = os.path.join(mod_dir, "_assets", "YAML", "pmk.yaml")
print(f"[CFG] LOCAL_PMK_PATH  = {LOCAL_PMK_PATH}")

# Global PMK registry path (mods/_assets/YAML/pmk_global.yaml)
GLOBAL_PMK_PATH = os.path.join(mods_root, "_assets", "YAML", "pmk_global.yaml")
print(f"[CFG] GLOBAL_PMK_PATH = {GLOBAL_PMK_PATH}")

# Main I3D directory (mods/<ModName>/<ModName>)
mod_name = os.path.basename(mod_dir)
MAIN_I3D_DIR = os.path.join(mod_dir, mod_name)
print(f"[CFG] MAIN_I3D_DIR    = {MAIN_I3D_DIR}")

# file_sync directory (script_dir)
FILE_SYNC_DIR = script_dir
print(f"[CFG] FILE_SYNC_DIR   = {FILE_SYNC_DIR}")

# FS25 game data root (for $data paths)
GAME_DATA_ROOT = r"D:\portable\GIANTS Software\Farming Simulator 2025\data"
print(f"[CFG] GAME_DATA_ROOT  = {GAME_DATA_ROOT}")

# ---- UTILITIES --------------------------------------------------------------

import hashlib
import json
import xml.etree.ElementTree as ET

def normalize_value(val):
    val = val.strip()
    if " " in val:
        parts = val.split()
        try:
            return [float(p) for p in parts]
        except ValueError:
            return val
    try:
        if "." in val:
            return float(val)
        return int(val)
    except ValueError:
        pass
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    return val

def build_pmk_identity(material_node, pfk_lookup):
    identity = {}

    # PARAMETERS FROM ATTRIBUTES
    for attr, val in material_node.attrib.items():
        if attr in ("materialId", "name"):
            continue
        if attr == "customShaderId":
            identity["shader"] = pfk_lookup(val)
            continue
        identity.setdefault("parameters", {})[attr] = normalize_value(val)

    # CHILD NODES
    for child in material_node:
        if "fileId" in child.attrib:
            file_id = child.attrib["fileId"]
            pfk = pfk_lookup(file_id)
            tag = child.tag.lower()
            if tag == "texture":
                slot = "diffuse"
            elif tag == "normalmap":
                slot = "normal"
            elif tag == "glossmap":
                slot = "gloss"
            elif tag == "custommap":
                slot = child.attrib.get("name", "custom")
            else:
                slot = tag
            identity.setdefault("textures", {})[slot] = pfk
            continue

        if "value" in child.attrib:
            name = child.attrib.get("name")
            if name:
                identity.setdefault("parameters", {})[name] = normalize_value(child.attrib["value"])
            continue

    return identity

def hash_pmk(identity_blob):
    serialized = json.dumps(identity_blob, sort_keys=True)
    sha = hashlib.sha1(serialized.encode("utf-8")).hexdigest()
    pmk = sha[0:4].upper()
    i = 0
    while pmk in global_pmk:
        existing_sha = global_pmk[pmk].get("sha1")
        if existing_sha == sha:
            return pmk
        i += 1
        if i + 4 > len(sha):
            raise RuntimeError(f"PMK collision resolution failed for SHA {sha}")
        pmk = sha[i:i+4].upper()
    return pmk

def build_pmk_entry(material_node, identity_blob, pmk_hash, sha):
    entry = {
        "materialName": material_node.attrib.get("name", "UNKNOWN"),
        "sha1": sha
    }
    if "shader" in identity_blob:
        entry["shader"] = identity_blob["shader"]
    if "textures" in identity_blob and identity_blob["textures"]:
        entry["textures"] = identity_blob["textures"]
    if "parameters" in identity_blob and identity_blob["parameters"]:
        entry["parameters"] = identity_blob["parameters"]
    return entry

def process_material(material_node, pfk_lookup):
    identity = build_pmk_identity(material_node, pfk_lookup)
    serialized = json.dumps(identity, sort_keys=True)
    sha = hashlib.sha1(serialized.encode("utf-8")).hexdigest()
    pmk_hash = hash_pmk(identity)
    entry = build_pmk_entry(material_node, identity, pmk_hash, sha)
    return pmk_hash, entry

def load_yaml(path):
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data

def save_yaml(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)

def sha1_file(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def pfk_from_sha1(sha1_hex):
    return sha1_hex[:4].upper()

def find_i3d_files():
    files = []
    files.extend(glob.glob(os.path.join(MAIN_I3D_DIR, "*.i3d")))
    files.extend(glob.glob(os.path.join(FILE_SYNC_DIR, "*.i3d")))
    return files

def parse_files_section(i3d_path):
    """Return list of (fileId, filename) from the I3D <Files> section."""
    tree = ET.parse(i3d_path)
    root = tree.getroot()
    files_node = root.find("Files")

    results = []
    if files_node is None:
        return results

    for f in files_node:
        file_id = f.attrib.get("fileId")
        filename = f.attrib.get("filename")
        if file_id and filename:
            results.append((file_id, filename))
    return results


def pfk_lookup(file_id):
    if file_id not in fileid_to_pfk:
        raise KeyError(f"Unknown fileId {file_id} in PMK builder")
    return fileid_to_pfk[file_id]

def build_pmks():
    global global_pmk
    global local_pmk
    print("[INFO] Building PMKs...")

    # Load existing registries (if they exist)
    if os.path.isfile(GLOBAL_PMK_PATH):
        global_reg = load_yaml(GLOBAL_PMK_PATH)
    else:
        global_reg = {"PMKRegistry": {}}

    if os.path.isfile(LOCAL_PMK_PATH):
        local_reg = load_yaml(LOCAL_PMK_PATH)
    else:
        local_reg = {"PMKRegistry": {}}

    global_pmk = global_reg["PMKRegistry"]
    local_pmk = local_reg["PMKRegistry"]

    pmk_registry = {}  # fresh build for this mod

    i3d_files = find_i3d_files()
    for i3d_path in i3d_files:
        tree = ET.parse(i3d_path)
        root = tree.getroot()

        for mat in root.iter("Material"):
            pmk_hash, entry = process_material(mat, pfk_lookup)

            pmk_registry[pmk_hash] = entry
            local_pmk[pmk_hash] = entry  # mod-local registry
            global_pmk[pmk_hash] = entry  # global registry

            print(f"[INFO] PMK {pmk_hash} for material {entry['materialName']}")

    # Save updated registries
    save_yaml(LOCAL_PMK_PATH, local_reg)
    save_yaml(GLOBAL_PMK_PATH, global_reg)

    print(f"[INFO] Local PMK saved:  {LOCAL_PMK_PATH}")
    print(f"[INFO] Global PMK saved: {GLOBAL_PMK_PATH}")

def resolve_path(filename):

    # --- $DATA FILES ---
    if filename.startswith("$data/") or filename.startswith("$data\\"):
        rel = filename[len("$data/"):] if filename.startswith("$data/") else filename[len("$data\\"):]
        rel = rel.replace("/", os.sep)
        abs_path = os.path.join(GAME_DATA_ROOT, rel)

        # PNG → DDS fallback
        if abs_path.lower().endswith(".png") and not os.path.isfile(abs_path):
            dds_path = abs_path[:-4] + ".dds"
            if os.path.isfile(dds_path):
                print(f"[DEBUG] PNG fallback → DDS: {dds_path}")
                return dds_path, filename

        if os.path.isfile(abs_path):
            return abs_path, filename

        print(f"[WARN] $data file not found: {filename}")
        return None, filename

    # --- MOD-LOCAL FILES ---
    abs_path = os.path.join(MAIN_I3D_DIR, filename.replace("/", os.sep))
    if os.path.isfile(abs_path):
        return abs_path, filename

    print(f"[WARN] Mod file not found: {filename}")
    return None, filename

# ---- MAIN LOGIC -------------------------------------------------------------

def build_pfks():
    global fileid_to_pfk
    global global_pfk
    global local_pfk
    # Load registries
    global_reg = load_yaml(GLOBAL_PFK_PATH)
    local_reg = load_yaml(LOCAL_PFK_PATH)

    if "PFKRegistry" not in global_reg:
        global_reg["PFKRegistry"] = {}
    if "PFKRegistry" not in local_reg:
        local_reg["PFKRegistry"] = {}

    global_pfk = global_reg["PFKRegistry"]
    local_pfk = local_reg["PFKRegistry"]

    # Reverse index: sha1 -> pfk (from global first, then local)
    sha_to_pfk = {}
    fileid_to_pfk = {}

    for pfk, info in global_pfk.items():
        sha = info.get("sha1")
        if sha:
            sha_to_pfk[sha] = pfk
    for pfk, info in local_pfk.items():
        sha = info.get("sha1")
        if sha and sha not in sha_to_pfk:
            sha_to_pfk[sha] = pfk

    fileid_to_pfk = {}

    i3d_files = find_i3d_files()
    print(f"[INFO] Found {len(i3d_files)} I3D file(s) to scan.")
    seen_files = set()

    for i3d_path in i3d_files:
        rel_i3d = os.path.relpath(i3d_path, mod_dir)
        print(f"[INFO] Scanning I3D: {rel_i3d}")
        file_entries = parse_files_section(i3d_path)
        print(f"[DEBUG] parse_files_section returned {len(file_entries)} entries")
        for file_id, fname in file_entries:

            # Debug: show the raw entry we are about to process
            print(f"[DEBUG] Entry: file_id={file_id}, path='{fname}'")

            if fname in seen_files:
                # Debug: show that this entry is being skipped
                print(f"[DEBUG] Skipped: '{fname}' already in seen_files")
                continue

            # Debug: show that this entry is NEW and will be processed
            print(f"[DEBUG] New entry: '{fname}' not in seen_files")

            seen_files.add(fname)

            abs_path, logical_path = resolve_path(fname)
            if abs_path is None:
                continue

            sha = sha1_file(abs_path)

            # Determine PFk and canonical path
            if sha in sha_to_pfk:
                # SHA already known → reuse its PFk
                pfk = sha_to_pfk[sha]

                # Get canonical path (fallback to logical_path)
                canonical_path = global_pfk.get(pfk, {}).get("path", logical_path)

                # Prefer $data path globally if encountered now
                if logical_path.startswith("$data") and not canonical_path.startswith("$data"):
                    canonical_path = logical_path
                    global_pfk[pfk]["path"] = canonical_path

            else:
                # First time seeing this SHA → generate PFk
                pfk = pfk_from_sha1(sha)

                # Collision resolution: walk forward through SHA hex
                i = 0
                while pfk in global_pfk and global_pfk[pfk].get("sha1") != sha:
                    i += 1
                    if i + 4 > len(sha):
                        raise RuntimeError(f"PFk collision resolution failed for SHA {sha}")
                    pfk = sha[i:i+4].upper()

                # Store PFk for this SHA
                sha_to_pfk[sha] = pfk

                # Canonical path is simply the logical path for new PFks
                canonical_path = logical_path

            # Update global registry (canonical path)
            global_pfk[pfk] = {
                "sha1": sha,
                "path": canonical_path,
            }

            # Update local registry (mod's actual path)
            local_pfk[pfk] = {
                "sha1": sha,
                "path": logical_path,
            }
            fileid_to_pfk[file_id] = pfk

            print(f"[INFO] PFk {pfk} -> sha1 {sha[:8]}... | global: {canonical_path} | local: {logical_path}")

    save_yaml(GLOBAL_PFK_PATH, global_reg)
    save_yaml(LOCAL_PFK_PATH, local_reg)

    print(f"[INFO] Global PFk saved: {GLOBAL_PFK_PATH}")
    print(f"[INFO] Local PFk saved:  {LOCAL_PFK_PATH}")


def menu():
    while True:
        print("\n=== FS25 Mod Pipeline ===")
        print("1. Build PFKs")
        print("2. Build PMKs")
        print("3. Exit")

        choice = input("Select option: ").strip()

        if choice == "1":
            build_pfks()
        elif choice == "2":
            build_pmks()
        elif choice == "3":
            break
        else:
            print("Invalid option.")

if __name__ == "__main__":
    menu()

