#!/usr/bin/env python
"""
FS25 Unified Tool

- Majik_mapper (full, xml-only, remap, raw)
- PFK builder
- PMK builder
- PNK builder (stub for now)
- material_sync
"""

import os
import sys
import glob
import json
import hashlib
import argparse
import xml.etree.ElementTree as ET
import yaml
import re
from collections import defaultdict

# =============================================================================
# CONFIG / PATHS
# =============================================================================

def detect_script_dirs():
    script_dir = __file__.replace("\\", "/")
    script_dir = script_dir.rsplit("/", 1)[0]

    mod_dir = script_dir.rsplit("/", 1)[0]
    mods_root = mod_dir.rsplit("/", 1)[0]

    mod_name = mod_dir.rsplit("/", 1)[1]

    main_i3d_dir      = f"{mod_dir}/{mod_name}"
    file_sync_dir     = f"{mod_dir}/file_sync"
    material_sync_dir = f"{mod_dir}/material_sync"
    node_sync_dir     = f"{mod_dir}/node_sync"
    i3d_maps_dir      = f"{mod_dir}/i3dMaps"
    local_yaml_dir    = f"{mod_dir}/_assets/YAML"
    global_yaml_dir   = f"{mods_root}/_assets/YAML"
    global_mats_dir   = f"{mods_root}/_assets/mats"

    return {
        "script_dir": script_dir,
        "mod_dir": mod_dir,
        "mods_root": mods_root,
        "mod_name": mod_name,
        "main_i3d_dir": main_i3d_dir,
        "file_sync_dir": file_sync_dir,
        "material_sync_dir": material_sync_dir,
        "node_sync_dir": node_sync_dir,
        "i3d_maps_dir": i3d_maps_dir,
        "local_yaml_dir": local_yaml_dir,
        "global_yaml_dir": global_yaml_dir,
        "global_mats_dir": global_mats_dir,
    }

PATHS = detect_script_dirs()

GAME_DATA_ROOT = "D:/portable/GIANTS Software/Farming Simulator 2025/data"
mats = f"{PATHS['mod_dir']}/_assets/mats"
# =============================================================================
# SHARED UTILITIES
# =============================================================================

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

def resolve_path(filename):
    main_i3d_dir = PATHS["main_i3d_dir"]
    mod_dir = PATHS["mod_dir"]

    clean = filename.replace("\\", "/")

    # $data/
    if clean.startswith("$data/"):
        rel = clean[len("$data/"):]
        full = f"{GAME_DATA_ROOT}/{rel}"
        return full if os.path.exists(full) else None

    # $mats/
    if clean.startswith("$mats/"):
        rel = clean[len("$mats/"):]
        full = f"{mats}/{rel}"

        return full if os.path.exists(full) else None

    # Absolute path
    if os.path.isabs(clean):
        return clean if os.path.exists(clean) else None

    # Mod-local or relative
    full = f"{main_i3d_dir}/{clean}"
    return full if os.path.exists(full) else None

def find_i3d_files():
    files = []
    main_i3d_dir = PATHS["main_i3d_dir"].replace("\\", "/")
    file_sync_dir = PATHS["file_sync_dir"].replace("\\", "/")

    files.extend(glob.glob(f"{main_i3d_dir}/*.i3d"))
    files.extend(glob.glob(f"{file_sync_dir}/*.i3d"))

    return files

def parse_files_section(i3d_path):
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

# =============================================================================
# MAJIK_MAPPER
# =============================================================================

DEFAULT_CONFIG = {
    "exclude_if_contains": ["/", "\\", ">", "|", " ", "<", "=", ":"],
    "exclude_if_tag": ["i3dMapping", "l10n"],
    "exclude_if_attr": ["name", "title", "colorScale"],
    "max_length": 64
}

def load_config(config_path="config.json"):
    if not os.path.exists(config_path):
        return DEFAULT_CONFIG
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load {config_path}: {e}")
        print("Using built-in default filter config.")
        return DEFAULT_CONFIG
    cfg = DEFAULT_CONFIG.copy()
    cfg.update({k: v for k, v in data.items() if k in cfg})
    return cfg

def walk(node, path, results):
    name = node.attrib.get("name")
    if name:
        results.append((name, list(path)))
    children = list(node)
    for i, child in enumerate(children):
        walk(child, path + [i], results)

def compact_path(path):
    if not path:
        return "0>"
    root = path[0]
    rest = path[1:]
    if not rest:
        return f"{root}>"
    return f'{root}>' + "|".join(str(i) for i in rest)

def generate_all_mappings(i3d_file):
    tree = ET.parse(i3d_file)
    root = tree.getroot()
    scene = root.find("Scene")
    if scene is None:
        raise ValueError("No <Scene> section found in .i3d file")
    results = []
    for comp_index, child in enumerate(list(scene)):
        walk(child, [comp_index], results)
    return results

def build_name_index(mappings):
    index = defaultdict(list)
    for name, path in mappings:
        index[name].append(path)
    return index

def autodetect_file(ext, search_dir=None):
    if search_dir is None:
        search_dir = os.getcwd()
    candidates = [f for f in os.listdir(search_dir) if f.lower().endswith(ext)]
    if not candidates:
        return None
    return candidates[0]

def run_raw_i3d_mode(i3d_file, output_file):
    tree = ET.parse(i3d_file)
    root = tree.getroot()
    scene = root.find("Scene")
    if scene is None:
        raise ValueError("No <Scene> section found in .i3d file")

    with open(output_file, "w", encoding="utf-8") as f:
        def raw_walk(node, path):
            name = node.attrib.get("name")
            if name:
                f.write(f'<i3dMapping id="{name}" node="{compact_path(path)}"/>\n')
            for i, child in enumerate(list(node)):
                raw_walk(child, path + [i])

        for comp_index, child in enumerate(list(scene)):
            raw_walk(child, [comp_index])

    print(f"Done. Mode=RAW_I3D. Output written to {output_file}")

def extract_xml_names_xml_only(xml_file, config):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    names = set()
    exclude_if_contains = config.get("exclude_if_contains", [])
    exclude_if_tag = set(config.get("exclude_if_tag", []))
    exclude_if_attr = set(config.get("exclude_if_attr", []))
    max_length = config.get("max_length", 64)

    for elem in root.iter():
        tag_name = elem.tag
        if tag_name in exclude_if_tag:
            continue
        for attr_name, attr_val in elem.attrib.items():
            if attr_name in exclude_if_attr:
                continue
            val = attr_val.strip()
            if not val:
                continue
            if len(val) > max_length:
                continue
            if any(ch in val for ch in exclude_if_contains):
                continue
            names.add(val)
    return names

def extract_ids_from_i3d_mappings(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    ids = []
    for elem in root.iter("i3dMapping"):
        id_val = elem.attrib.get("id")
        if id_val:
            ids.append(id_val)
    return ids

def write_output(output_file, selected_name_to_paths, mode_label):
    flat = []
    for name, paths in selected_name_to_paths.items():
        for p in paths:
            flat.append((name, compact_path(p)))

    with open(output_file, "w", encoding="utf-8") as f:
        for name, path_str in flat:
            f.write(f'<i3dMapping id="{name}" node="{path_str}"/>\n')

        duplicates = {name: paths for name, paths in selected_name_to_paths.items() if len(paths) > 1}
        if duplicates:
            f.write("\n<!-- WARNING: Duplicate node names detected ({}) [{}] -->\n"
                    .format(mode_label, len(duplicates)))
            sorted_dupes = sorted(duplicates.items(), key=lambda item: len(item[1]))
            for name, paths in sorted_dupes:
                f.write(f'<!-- "{name}" appears {len(paths)} times: -->\n')
                for p in paths:
                    f.write(f'<!--     {compact_path(p)} -->\n')

def run_majik_mapper_mode(mode):
    i3d_maps_dir = PATHS["i3d_maps_dir"]
    os.makedirs(i3d_maps_dir, exist_ok=True)
    os.chdir(i3d_maps_dir)

    i3d_file = autodetect_file(".i3d", search_dir=i3d_maps_dir)
    xml_file = autodetect_file(".xml", search_dir=i3d_maps_dir)

    if not i3d_file:
        print("Error: No .i3d file found in i3dMaps/")
        return

    config = load_config("config.json")

    if mode == "raw":
        run_raw_i3d_mode(i3d_file, "i3d_mappings.raw.txt")
        return

    all_mappings = generate_all_mappings(i3d_file)
    name_index = build_name_index(all_mappings)
    selected = {}

    if mode == "full":
        selected = name_index
        mode_label = "FULL_I3D"

    elif mode == "xml-only":
        if not xml_file:
            print("Error: XML-only mode requires an XML file in i3dMaps/")
            return
        xml_names = extract_xml_names_xml_only(xml_file, config)
        for name in xml_names:
            if name in name_index:
                selected[name] = name_index[name]
        mode_label = "XML_ONLY"

    elif mode == "remap":
        if not xml_file:
            print("Error: XML-remap mode requires an XML file in i3dMaps/")
            return
        ids = extract_ids_from_i3d_mappings(xml_file)
        for id_name in ids:
            if id_name in name_index:
                selected[id_name] = name_index[id_name]
        mode_label = "XML_REMAP"

    else:
        print(f"Unknown Majik_mapper mode: {mode}")
        return

    output_file = f"i3d_mappings.{mode}.txt"
    write_output(output_file, selected, mode_label)
    print(f"Done. Mode={mode_label}. Output written to {output_file}")

def run_majik_mapper():
    i3d_maps_dir = PATHS["i3d_maps_dir"]
    os.makedirs(i3d_maps_dir, exist_ok=True)
    os.chdir(i3d_maps_dir)

    parser = argparse.ArgumentParser(
        description="GIANTS I3D mapping generator (compact paths, multi-mode, config-driven).")
    parser.add_argument("i3d", nargs="?", help="Path to .i3d file (optional, auto-detected if omitted).")
    parser.add_argument("--xml-only", nargs="?", const=True,
                        help="XML-only mode: map names referenced in XML (excluding existing <i3dMapping> entries). "
                             "Optionally pass XML path, otherwise auto-detected.")
    parser.add_argument("--remap", nargs="?", const=True,
                        help="XML-remap mode: remap only IDs already in <i3dMappings>. "
                             "Optionally pass XML path, otherwise auto-detected.")
    parser.add_argument("-o", "--output", help="Output file name (default: i3d_mappings.xml).")
    parser.add_argument("--config", help="Path to config.json (default: ./config.json).")
    parser.add_argument("--raw-i3d", action="store_true",
                        help="Raw I3D dump: write each node in DFS order with no duplicate grouping.")

    args = parser.parse_args([])  # no CLI args from menu; we drive it interactively if needed

    mode_xml_only = args.xml_only is not None
    mode_remap = args.remap is not None

    if mode_xml_only and mode_remap:
        print("Error: --xml-only and --remap cannot be used together.")
        return

    config_path = args.config if args.config else "config.json"
    config = load_config(config_path)
    print(f"Using config: {config_path if os.path.exists(config_path) else 'built-in defaults'}")

    if args.i3d:
        i3d_file = args.i3d
    else:
        i3d_file = autodetect_file(".i3d", search_dir=i3d_maps_dir)
        if not i3d_file:
            print("Error: No .i3d files found in i3dMaps directory.")
            return
        print(f"Auto-detected .i3d file: {i3d_file}")

    xml_file = None
    if mode_xml_only:
        if isinstance(args.xml_only, str):
            xml_file = args.xml_only
        else:
            xml_file = autodetect_file(".xml", search_dir=i3d_maps_dir)
        if not xml_file:
            print("Error: XML-only mode requested but no .xml file specified or found.")
            return
        print(f"XML-only mode using XML file: {xml_file}")

    if mode_remap:
        if isinstance(args.remap, str):
            xml_file = args.remap
        else:
            xml_file = autodetect_file(".xml", search_dir=i3d_maps_dir)
        if not xml_file:
            print("Error: XML-remap mode requested but no .xml file specified or found.")
            return
        print(f"XML-remap mode using XML file: {xml_file}")

    output_file = args.output if args.output else "i3d_mappings.xml"

    if args.raw_i3d:
        run_raw_i3d_mode(i3d_file, output_file)
        return

    all_mappings = generate_all_mappings(i3d_file)
    name_index = build_name_index(all_mappings)
    selected_name_to_paths = {}

    if not mode_xml_only and not mode_remap:
        for name, paths in name_index.items():
            selected_name_to_paths[name] = paths
        mode_label = "FULL_I3D"

    elif mode_xml_only:
        xml_names = extract_xml_names_xml_only(xml_file, config)
        missing_in_i3d = []
        for name in sorted(xml_names):
            if name in name_index:
                selected_name_to_paths[name] = name_index[name]
            else:
                missing_in_i3d.append(name)
        mode_label = "XML_ONLY"
        if missing_in_i3d:
            print("Warning: The following XML-referenced names were not found in the I3D:")
            for n in missing_in_i3d:
                print(f"  - {n}")

    elif mode_remap:
        ids = extract_ids_from_i3d_mappings(xml_file)
        missing_in_i3d = []
        for id_name in ids:
            if id_name in name_index:
                selected_name_to_paths[id_name] = name_index[id_name]
            else:
                missing_in_i3d.append(id_name)
        mode_label = "XML_REMAP"
        if missing_in_i3d:
            print("Warning: The following IDs from <i3dMappings> were not found in the I3D:")
            for n in missing_in_i3d:
                print(f"  - {n}")

    write_output(output_file, selected_name_to_paths, mode_label)
    print(f"Done. Mode={mode_label}. Output written to {output_file}")

# =============================================================================
# PFK / PMK / PNK REGISTRY PATHS
# =============================================================================

GLOBAL_PFK_PATH = f"{PATHS['global_yaml_dir']}/pfk_global.yaml"
LOCAL_PFK_PATH  = f"{PATHS['local_yaml_dir']}/pfk.yaml"

GLOBAL_PMK_PATH = f"{PATHS['global_yaml_dir']}/pmk_global.yaml"
LOCAL_PMK_PATH  = f"{PATHS['local_yaml_dir']}/pmk.yaml"

# Add these for PNK:
GLOBAL_PNK_PATH = f"{PATHS['global_yaml_dir']}/pnk_global.yaml"
LOCAL_PNK_PATH  = f"{PATHS['local_yaml_dir']}/pnk.yaml"

# =============================================================================
# REGISTRY GLOBALS
# =============================================================================

global_pfk = {}
local_pfk  = {}

global_pmk = {}
local_pmk  = {}

# PFk lookup table for PMK builder
fileid_to_pfk = {}

# Add these for PNK:
global_pnk = {}
local_pnk  = {}

def choose_identity_path(paths):
    # Priority 1: GIANTS $data (prefer DDS over PNG)
    data_paths = [p for p in paths if p.startswith("$data")]
    if data_paths:
        # If both PNG and DDS exist, choose DDS
        dds_paths = [p for p in data_paths if p.lower().endswith(".dds")]
        if dds_paths:
            return dds_paths[0]
        return data_paths[0]

    # Priority 2: canonical materials
    mats_paths = [p for p in paths if p.startswith("$mats")]
    if mats_paths:
        return mats_paths[0]

    # Priority 3: local mod files
    return paths[0]

def pfk_lookup(file_id):
    if file_id not in fileid_to_pfk:
        raise KeyError(f"Unknown fileId {file_id} in PMK builder")
    return fileid_to_pfk[file_id]

def build_pmk_identity(material_node, pfk_lookup_func):
    identity = {"parameters": {}}  # always present

    # Material tag parameters (XMK parameters)
    for attr, val in material_node.attrib.items():
        if attr in ("materialId", "name"):
            continue
        if attr == "customShaderId":
            identity["shader"] = pfk_lookup_func(val)
            continue
        identity["parameters"][attr] = normalize_value(val)

    # Child tags: textures + CustomParameter tags
    for child in material_node:
        if "fileId" in child.attrib:
            file_id = child.attrib["fileId"]
            pfk = pfk_lookup_func(file_id)
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
                identity["parameters"][name] = normalize_value(child.attrib["value"])
            continue

    return identity

def hash_pmk(identity_blob):
    serialized = json.dumps(identity_blob, sort_keys=True)
    sha = hashlib.sha1(serialized.encode("utf-8")).hexdigest()
    pmk = sha[0:4].upper()

    print(f"[PMK] SHA={sha} initial PMK={pmk}")

    i = 0
    while pmk in global_pmk:
        existing_sha = global_pmk[pmk]["sha1"]

        if existing_sha == sha:
            print(f"[PMK] DUPLICATE IDENTITY → Reusing PMK {pmk}")
            return pmk

        print(f"[PMK] COLLISION: PMK {pmk} already used by SHA {existing_sha}")
        i += 1

        if i + 4 > len(sha):
            raise RuntimeError(f"PMK collision resolution failed for SHA {sha}")

        pmk = sha[i:i+4].upper()
        print(f"[PMK] Trying next window → PMK={pmk}")

    print(f"[PMK] NEW PMK GENERATED → {pmk}")
    return pmk

def build_pmk_entry(material_node, identity_blob, pmk_hash, sha, i3d_path):
    entry = {
        "materialName": material_node.attrib.get("name", "UNKNOWN"),
        "sha1": sha,
    }
    # Shader immediately after sha1
    if "shader" in identity_blob:
        entry["shader"] = identity_blob["shader"]
    # Textures above parameters
    if "textures" in identity_blob and identity_blob["textures"]:
        entry["textures"] = identity_blob["textures"]
    # Parameters after textures
    if "parameters" in identity_blob and identity_blob["parameters"]:
        entry["parameters"] = identity_blob["parameters"]
    # File paths last
    entry["filePaths"] = [i3d_path]

    return entry

def process_material(material_node, pfk_lookup_func, i3d_path):
    identity = build_pmk_identity(material_node, pfk_lookup_func)

    # Abort if ANY texture PFk is missing
    if "textures" in identity:
        for slot, pfk in identity["textures"].items():
            if pfk == "????":
                print(f"[ERROR] PMK aborted: missing PFk for texture slot '{slot}' in material '{material_node.attrib.get('name')}'")
                return None, None

    # Abort if shader PFk is missing
    if identity.get("shader") == "????":
        print(f"[ERROR] PMK aborted: missing shader PFk in material '{material_node.attrib.get('name')}'")
        return None, None

    serialized = json.dumps(identity, sort_keys=True)
    sha = hashlib.sha1(serialized.encode("utf-8")).hexdigest()

    pmk_hash = hash_pmk(identity)
    entry = build_pmk_entry(material_node, identity, pmk_hash, sha, i3d_path)

    return pmk_hash, entry

def build_pfks():
    global fileid_to_pfk
    global global_pfk
    global local_pfk

    # --- GLOBAL PFk SETUP ---
    global_reg = load_yaml(GLOBAL_PFK_PATH)
    global_pfk = global_reg.setdefault("PFKRegistry", {})

    # Build SHA→PFK lookup from GLOBAL registry
    sha_to_pfk = {}
    for pfk, info in global_pfk.items():
        sha = info.get("sha1")
        if sha:
            sha_to_pfk[sha] = pfk

    # --- LOCAL PFk SETUP ---
    local_pfk = {}  # fresh every run

    i3d_files = find_i3d_files()
    print(f"[INFO] Found {len(i3d_files)} I3D file(s) to scan.")

    # Duplicate-hunter tables
    hash_table = {}      # sha1 -> list of file records
    fileid_to_pfk = {}   # reset mapping for this run

    # -------------------------------------------------------------------------
    # SCAN ALL I3Ds
    # -------------------------------------------------------------------------
    for i3d_path in i3d_files:
        rel_i3d = os.path.relpath(i3d_path, PATHS["mod_dir"])
        print(f"[INFO] Scanning I3D: {rel_i3d}")

        file_entries = parse_files_section(i3d_path)

        for file_id, fname in file_entries:
            abs_path = resolve_path(fname)
            logical_path = fname

            if abs_path is None:
                print(f"[WARN] Cannot resolve path for '{fname}'")
                continue

            tex_path, sha = png_this(abs_path)

            if sha is None:
                print(f"[WARN] No PNG/DDS/XML found for '{fname}'")
                continue

            # IDENTICAL DUPLICATE DETECTION
            if sha in hash_table:
                hash_table[sha].append({
                    "fileId": file_id,
                    "filename": fname,
                    "i3d": rel_i3d,
                    "path": logical_path
                })
                print(f"[WARN] Duplicate detected: '{fname}' (fileId {file_id})")
                continue

            # FIRST TIME SEEING THIS FILE CONTENT
            hash_table[sha] = [{
                "fileId": file_id,
                "filename": fname,
                "i3d": rel_i3d,
                "path": logical_path
            }]

            # PFk generation
            if sha in sha_to_pfk:
                pfk = sha_to_pfk[sha]
            else:
                pfk = pfk_from_sha1(sha)
                i = 0
                while pfk in global_pfk and global_pfk[pfk].get("sha1") != sha:
                    i += 1
                    if i + 4 > len(sha):
                        raise RuntimeError(f"PFK collision resolution failed for SHA {sha}")
                    pfk = sha[i:i+4].upper()
                sha_to_pfk[sha] = pfk

            entry = global_pfk.setdefault(pfk, {"sha1": sha, "files": []})

            if entry["sha1"] != sha:
                raise RuntimeError(f"PFK {pfk} has conflicting SHA1 values!")

            # GLOBAL: only add if not already present
            if logical_path not in entry["files"]:
                entry["files"].append(logical_path)

            # LOCAL: same PFK, same uniqueness rule
            local_entry = local_pfk.setdefault(pfk, {"sha1": sha, "files": []})
            if logical_path not in local_entry["files"]:
                local_entry["files"].append(logical_path)

            fileid_to_pfk[file_id] = pfk

    # -------------------------------------------------------------------------
    # BUILD DUPLICATE REPORT
    # -------------------------------------------------------------------------
    has_dupes = False

    for sha, records in hash_table.items():
        if len(records) > 1:
            if not has_dupes:
                print("\n\n****************************************")
                print("***      DUPLICATE FILES DETECTED    ***")
                print("****************************************\n")
                has_dupes = True

            print(f"Hash: {sha}")
            print("Files:")
            for f in records:
                print(f"  fileId={f['fileId']} in {f['i3d']}")
                print(f"    Path: {f['path']}")
            print("------------------------")

    # -------------------------------------------------------------------------
    # HANDLE DUPLICATES
    # -------------------------------------------------------------------------
    if has_dupes:
        print("************************************************************")
        print("***   ⚠️  CRITICAL DUPLICATE TEXTURES — ACTION REQUIRED  ⚠️   ***")
        print("************************************************************")
        print("These files are BIT-IDENTICAL.")
        print("This WILL corrupt PFk/PMK generation.")
        print("Resolve these duplicates BEFORE running PMK.")
        print("************************************************************")
        return  # <-- END THE PFK BUILD IMMEDIATELY

    # -------------------------------------------------------------------------
    # NO DUPES — CONFIRM CONTINUE
    # -------------------------------------------------------------------------
    print("\n[INFO] No duplicate textures detected.")
    print("[INFO] PFk registry is clean.\n")

    print("1. Continue to PMK build")
    print("2. End PFk build")

    choice = input("> ").strip()

    if choice != "1":
        print("[INFO] PFk build ended by user choice.")
        return  # <-- STOP BEFORE PMK BUILD

    # -------------------------------------------------------------------------
    # SAVE REGISTRIES (PFK IS CLEAN)
    # -------------------------------------------------------------------------

    # --- REPAIR GLOBAL USING FINAL LOCAL PFk ---
    for pfk, info in local_pfk.items():
        if pfk not in global_pfk:
            global_pfk[pfk] = info
        else:
            g_files = global_pfk[pfk].setdefault("files", [])
            for f in info.get("files", []):
                if f not in g_files:
                    g_files.append(f)

    # Normalize all global PFk file lists
    for pfk, info in global_pfk.items():
        files = info.get("files", [])
        clean = sorted(set(f.replace("\\", "/") for f in files))
        info["files"] = clean

    # Normalize local PFk file lists
    for pfk, info in local_pfk.items():
        files = info.get("files", [])
        clean = sorted(set(f.replace("\\", "/") for f in files))
        info["files"] = clean

    save_yaml(GLOBAL_PFK_PATH, global_reg)
    save_yaml(LOCAL_PFK_PATH, {"PFKRegistry": local_pfk})

    print(f"[INFO] Global PFk saved: {GLOBAL_PFK_PATH}")
    print(f"[INFO] Local PFk saved:  {LOCAL_PFK_PATH}")

    # -------------------------------------------------------------------------
    # CONTINUE TO PMK BUILD
    # -------------------------------------------------------------------------
    build_pmks()

def build_pmks():
    global global_pmk
    global local_pmk

    print("[INFO] Building PMKs...")

    # ---------------------------------------------------------
    # GIANTS PMK SETUP (authoritative GIANTS fingerprints)
    # ---------------------------------------------------------
    if os.path.isfile(GIANTS_PMK_PATH):
        giants_reg = load_yaml(GIANTS_PMK_PATH)
        giants_pmk = giants_reg.get("PMKRegistry", {})
    else:
        giants_pmk = {}  # should never happen, but safe fallback

    # ---------------------------------------------------------
    # GLOBAL PMK SETUP (persistent)
    # ---------------------------------------------------------
    if os.path.isfile(GLOBAL_PMK_PATH):
        global_reg = load_yaml(GLOBAL_PMK_PATH)
    else:
        global_reg = {"PMKRegistry": {}}

    global_pmk = global_reg.setdefault("PMKRegistry", {})

    # ---------------------------------------------------------
    # LOCAL PMK SETUP (fresh every run)
    # ---------------------------------------------------------
    local_pmk = {}      # fresh, do NOT load old YAML
    pmk_registry = {}   # this run only

    # ---------------------------------------------------------
    # SCAN ALL I3Ds AND BUILD PMKs
    # ---------------------------------------------------------
    i3d_files = find_i3d_files()

    for i3d_path in i3d_files:
        tree = ET.parse(i3d_path)
        root = tree.getroot()

        for mat in root.iter("Material"):
            pmk_hash, entry = process_material(mat, pfk_lookup, i3d_path)
            if pmk_hash is None:
                continue

            # This run only
            pmk_registry[pmk_hash] = entry

            # Local PMK (fresh)
            local_pmk[pmk_hash] = entry

            print(f"[INFO] PMK {pmk_hash} for material {entry['materialName']}")

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------
    print("\n================ PMK SUMMARY ================")

    total_materials = 0
    for i3d_path in i3d_files:
        tree = ET.parse(i3d_path)
        root = tree.getroot()
        total_materials += len(list(root.iter("Material")))

    total_pmks = len(pmk_registry)

    print(f"Total materials processed: {total_materials}")
    print(f"Total PMKs generated:      {total_pmks}")

    # ---------------------------------------------------------
    # DETECT DUPLICATE SHA1 IDENTITIES
    # ---------------------------------------------------------
    seen_sha = {}
    duplicate_sha = []

    for pmk, entry in pmk_registry.items():
        sha = entry["sha1"]
        if sha in seen_sha:
            duplicate_sha.append((sha, pmk, seen_sha[sha]))
        else:
            seen_sha[sha] = pmk

    # ---------------------------------------------------------
    # DETECT DUPLICATE PMK HASHES
    # ---------------------------------------------------------
    seen_pmk = set()
    duplicate_pmk = []

    for pmk in pmk_registry.keys():
        if pmk in seen_pmk:
            duplicate_pmk.append(pmk)
        else:
            seen_pmk.add(pmk)

    print("==============================================\n")

    # ---------------------------------------------------------
    # HANDLE DUPLICATES (FATAL ERROR)
    # ---------------------------------------------------------
    if duplicate_sha or duplicate_pmk:
        print("\n************************************************************")
        print("***   ⚠️  CRITICAL PMK DUPLICATES — ACTION REQUIRED  ⚠️   ***")
        print("************************************************************")
        if duplicate_sha:
            print("Duplicate SHA1 identities detected:")
            for sha, pmk1, pmk2 in duplicate_sha:
                print(f"SHA {sha} → PMKs {pmk1} and {pmk2}")
        if duplicate_pmk:
            print("\nDuplicate PMK hashes detected:")
            for pmk in duplicate_pmk:
                print(f"PMK {pmk} appears more than once.")
        print("\nPMK generation aborted. Fix these issues and rerun.")
        print("************************************************************\n")
        return  # <-- STOP IMMEDIATELY, DO NOT SAVE ANYTHING

    # ---------------------------------------------------------
    # NO DUPES — MERGE LOCAL → GLOBAL
    # ---------------------------------------------------------
    for pmk_hash, entry in local_pmk.items():

        # 1. GIANTS PMK?  (skip logging globally)
        if pmk_hash in giants_pmk:
            continue

        # 2. Already known mod material?  (skip logging globally)
        if pmk_hash in global_pmk:
            # merge filePaths only
            g_paths = global_pmk[pmk_hash].setdefault("filePaths", [])
            for p in entry.get("filePaths", []):
                if p not in g_paths:
                    g_paths.append(p)
            continue

        # 3. NEW mod-origin material → add to global PMK
        global_pmk[pmk_hash] = entry

        # 4. Merge filePaths only (dedupe)
        paths = global_pmk[pmk_hash].setdefault("filePaths", [])
        for p in entry.get("filePaths", []):
            if p not in paths:
                paths.append(p)
    
    # Normalize filePaths only
    for pmk, info in global_pmk.items():
        paths = info.get("filePaths", [])
        if isinstance(paths, list):
            info["filePaths"] = sorted(set(p.replace("\\", "/") for p in paths))

    # ---------------------------------------------------------
    # SAVE REGISTRIES
    # ---------------------------------------------------------
    save_yaml(LOCAL_PMK_PATH, {"PMKRegistry": local_pmk})
    save_yaml(GLOBAL_PMK_PATH, global_reg)

    print(f"[INFO] Local PMK saved:  {LOCAL_PMK_PATH}")
    print(f"[INFO] Global PMK saved: {GLOBAL_PMK_PATH}")

    return

# =============================================================================
# PNK v2 builder (permanent random IDs + slotCount + PMKs)
# =============================================================================

import secrets

def build_pnks_v2():
    print("[INFO] Building PNK v2...")

    # Load existing registries
    global_reg = load_yaml(GLOBAL_PNK_PATH)
    local_reg  = load_yaml(LOCAL_PNK_PATH)

    if "PNKRegistry" not in global_reg:
        global_reg["PNKRegistry"] = {}
    if "PNKRegistry" not in local_reg:
        local_reg["PNKRegistry"] = {}

    gpnk = global_reg["PNKRegistry"]
    lpnk = local_reg["PNKRegistry"]

    # Locate main I3D
    main_i3d_dir = PATHS["main_i3d_dir"]
    i3d_files = glob.glob(os.path.join(main_i3d_dir, "*.i3d"))
    if not i3d_files:
        print("[ERROR] No main I3D found.")
        return

    i3d_path = i3d_files[0]
    tree = ET.parse(i3d_path)
    root = tree.getroot()
    scene = root.find("Scene")
    if scene is None:
        print("[ERROR] No <Scene> in I3D.")
        return

    # -------------------------------------------------------------------------
    # Pass 1: collect all nodes with their paths
    # -------------------------------------------------------------------------
    records = []

    def walk(node, path):
        records.append({"node": node, "path": path})
        children = list(node)
        for index, child in enumerate(children):
            walk(child, path + [index])

    walk(scene, [])

    # -------------------------------------------------------------------------
    # Pass 2: assign PNKs (short) + permanent IDs (long)
    # -------------------------------------------------------------------------
    path_to_pnk = {}
    pnk_report_lines = []

    for rec in records:
        node = rec["node"]
        path = rec["path"]

        name = node.attrib.get("name", "")
        path_str = compact_path(path)

        # Determine slotCount + PMKs
        mat_ids = node.attrib.get("materialIds", "")
        if mat_ids.strip():
            raw_list = mat_ids.split(",")
            slot_count = len(raw_list)

            # PMKs are 4-digit hex, not materialIds
            pmks = []
            for mid in raw_list:
                mid = mid.strip()
                pmk = pmk_lookup(mid)  # <-- your PMK lookup function
                pmks.append(pmk)
        else:
            slot_count = 0
            pmks = []

        # Try to find an existing entry by name+path
        existing_pnk = None
        for pnk_key, entry in gpnk.items():
            if entry.get("name") == name and entry.get("path") == path_str:
                existing_pnk = pnk_key
                break

        # If no existing PNK, generate new permanent ID + short PNK
        if existing_pnk:
            pnk = existing_pnk
            id40 = gpnk[pnk]["id"]
        else:
            id40 = secrets.token_hex(20).upper()   # permanent 160-bit ID
            pnk = id40[:4]                         # short label

            # Collision sliding window
            i = 0
            while pnk in gpnk:
                i += 1
                pnk = id40[i:i+4]

        entry = {
            "id": id40,
            "name": name,
            "path": path_str,
            "slotCount": slot_count,
            "materials": pmks,
        }

        gpnk[pnk] = entry
        lpnk[pnk] = entry

        path_to_pnk[tuple(path)] = pnk
        pnk_report_lines.append(f"{pnk}  {name}  {path_str}  slots={slot_count}")

    # -------------------------------------------------------------------------
    # Pass 3: fill parent/children PNK references
    # -------------------------------------------------------------------------
    for rec in records:
        path = rec["path"]
        this_pnk = path_to_pnk[tuple(path)]

        # Parent PNK
        parent_pnk = None
        if path:
            parent_pnk = path_to_pnk.get(tuple(path[:-1]))

        # Children PNKs
        children_pnks = []
        for child_rec in records:
            child_path = child_rec["path"]
            if child_path[:-1] == path:
                child_pnk = path_to_pnk[tuple(child_path)]
                children_pnks.append(child_pnk)

        # Update entry
        entry = gpnk[this_pnk]
        entry["parent"] = parent_pnk
        entry["children"] = children_pnks

        lpnk[this_pnk]["parent"]   = parent_pnk
        lpnk[this_pnk]["children"] = children_pnks

    # -------------------------------------------------------------------------
    # Save registries and report
    # -------------------------------------------------------------------------
    save_yaml(GLOBAL_PNK_PATH, global_reg)
    save_yaml(LOCAL_PNK_PATH, local_reg)

    report_path = os.path.join(PATHS["node_sync_dir"], "pnk_report_v2.txt")
    os.makedirs(PATHS["node_sync_dir"], exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(pnk_report_lines))

    print(f"[INFO] Local PNK v2 saved:  {LOCAL_PNK_PATH}")
    print(f"[INFO] Global PNK v2 saved: {GLOBAL_PNK_PATH}")
    print(f"[INFO] Report written:      {report_path}")

# =============================================================================
# MATERIAL_SYNC
# =============================================================================

OLD_FILE = os.path.join(PATHS["material_sync_dir"], "old.i3d")
NEW_FILE = os.path.join(PATHS["material_sync_dir"], "new.i3d")
OUT_FILE = os.path.join(PATHS["material_sync_dir"], "patched.i3d")

def extract_alpha_core(name: str) -> str:
    positions = [i for i, c in enumerate(name) if c.isalpha()]
    if not positions:
        return ""
    return name[positions[0]:positions[-1] + 1]

def build_material_map(old_path: str) -> dict:
    materials_by_core = {}
    shape_re = re.compile(r'<Shape\b[^>]*>')
    name_re = re.compile(r'name="([^"]+)"')
    mat_re = re.compile(r'materialIds="([^"]+)"')

    with open(old_path, "r", encoding="utf-8") as f:
        for line in f:
            if "<Shape" not in line:
                continue
            if not shape_re.search(line):
                continue
            name_match = name_re.search(line)
            mat_match = mat_re.search(line)
            if not name_match or not mat_match:
                continue
            raw_name = name_match.group(1)
            core = extract_alpha_core(raw_name)
            if not core:
                continue
            materials_by_core[core] = mat_match.group(1)
    return materials_by_core

def patch_new_file(new_path: str, out_path: str, materials_by_core: dict):
    shape_re = re.compile(r'<Shape\b[^>]*>')
    name_re = re.compile(r'name="([^"]+)"')
    mat_re = re.compile(r'materialIds="([^"]*)"')

    in_scene = False

    with open(new_path, "r", encoding="utf-8") as fin, \
         open(out_path, "w", encoding="utf-8") as fout:

        for line in fin:
            stripped = line.lstrip()
            if "<Scene" in stripped:
                in_scene = True
            if "</Scene" in stripped:
                in_scene = False

            if in_scene and "<Shape" in stripped and shape_re.search(stripped):
                name_match = name_re.search(stripped)
                if name_match:
                    raw_name = name_match.group(1)
                    core = extract_alpha_core(raw_name)
                    if core and core in materials_by_core:
                        old_mat_ids = materials_by_core[core]
                        if mat_re.search(stripped):
                            def repl(m):
                                return f'materialIds="{old_mat_ids}"'
                            stripped = mat_re.sub(repl, stripped)
                            line = line[:len(line) - len(line.lstrip())] + stripped
            fout.write(line)

def run_material_sync():
    print("Building material map from", OLD_FILE)
    materials_by_core = build_material_map(OLD_FILE)
    print(f"Found {len(materials_by_core)} shape material mappings.")
    print("Patching", NEW_FILE, "->", OUT_FILE)
    patch_new_file(NEW_FILE, OUT_FILE, materials_by_core)
    print("Done. Output written to", OUT_FILE)
    # --- Collect and print all materialIds used in patched.i3d only ---
    import re

    material_set = set()

    with open(OUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            m = re.search(r'materialIds="([^"]+)"', line)
            if m:
                ids = m.group(1).split(',')
                for mid in ids:
                    mid = mid.strip()
                    if mid:
                        material_set.add(mid)

    print("\nMaterials referenced in patched.i3d:")
    for mid in sorted(material_set, key=lambda x: int(x)):
        print(mid)
    print(f"\nTotal materials: {len(material_set)}\n")

# ------------------------------------------------------------
# MATERIAL RENAMER USING PMK SUFFIX "__AB12"  (FIXED VERSION)
# ------------------------------------------------------------

def rename_materials_with_pmk():
    print("\n=== MATERIAL RENAME USING PMK SUFFIX ===")

    # --------------------------------------------------------
    # Verify PFK + PMK existence
    # --------------------------------------------------------
    local_pfk = os.path.join(PATHS["local_yaml_dir"], "pfk.yaml")
    global_pfk = os.path.join(PATHS["global_yaml_dir"], "pfk_global.yaml")
    local_pmk = os.path.join(PATHS["local_yaml_dir"], "pmk.yaml")
    global_pmk = os.path.join(PATHS["global_yaml_dir"], "pmk_global.yaml")

    missing = []
    if not os.path.isfile(local_pfk): missing.append(local_pfk)
    if not os.path.isfile(global_pfk): missing.append(global_pfk)
    if not os.path.isfile(local_pmk): missing.append(local_pmk)
    if not os.path.isfile(global_pmk): missing.append(global_pmk)

    if missing:
        print("[ERROR] Cannot rename materials — missing required YAML:")
        for m in missing:
            print("   -", m)
        print("Run PFK + PMK builders first.")
        return

    # --------------------------------------------------------
    # Load PMK registry (local overrides global)
    # --------------------------------------------------------
    pmk_registry = {}

    def load_yaml(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except:
            return {}

    global_pmk_data = load_yaml(global_pmk)
    local_pmk_data  = load_yaml(local_pmk)

    # Merge global + local
    if "PMKRegistry" in global_pmk_data:
        pmk_registry.update(global_pmk_data["PMKRegistry"])
    if "PMKRegistry" in local_pmk_data:
        pmk_registry.update(local_pmk_data["PMKRegistry"])

    print(f"[INFO] Loaded {len(pmk_registry)} PMK entries.")

    # --------------------------------------------------------
    # Locate main I3D
    # --------------------------------------------------------
    main_i3d_dir = PATHS["main_i3d_dir"]
    i3d_files = glob.glob(os.path.join(main_i3d_dir, "*.i3d"))

    if not i3d_files:
        print("[ERROR] No main I3D found in:", main_i3d_dir)
        return

    main_i3d = i3d_files[0]
    print("[INFO] Renaming materials in:", main_i3d)

    # --------------------------------------------------------
    # Parse I3D
    # --------------------------------------------------------
    tree = ET.parse(main_i3d)
    root = tree.getroot()

    materials = root.findall(".//Material")
    print(f"[INFO] Found {len(materials)} materials.")

    rename_count = 0
    skip_count = 0

    # --------------------------------------------------------
    # Rename each material
    # --------------------------------------------------------
    for mat in materials:
        old_name = mat.get("name", "").strip()

        if not old_name:
            print("[WARN] Material has no name — skipped.")
            skip_count += 1
            continue

        # ----------------------------------------------------
        # PMK lookup by materialName (CORRECT)
        # ----------------------------------------------------
        pmk = None
        for pmk_key, info in pmk_registry.items():
            if info.get("materialName", "") == old_name:
                pmk = pmk_key
                break

        if not pmk:
            print(f"[WARN] No PMK for material '{old_name}' — skipped.")
            skip_count += 1
            continue

        # ----------------------------------------------------
        # Build new name: oldName__PMK
        # ----------------------------------------------------
        new_name = f"{old_name}__{pmk}"

        # Apply rename
        mat.set("name", new_name)
        rename_count += 1

    # --------------------------------------------------------
    # Save patched I3D
    # --------------------------------------------------------
    tree.write(main_i3d, encoding="utf-8", xml_declaration=True)
    print(f"[SUCCESS] Renamed {rename_count} materials. Skipped {skip_count}.")

def scan_giants_data_folder():
    print("\n=== SCAN GIANTS DATA FOLDER (GLOBAL PFK BUILDER) ===")

    data_root = GAME_DATA_ROOT
    if not os.path.isdir(data_root):
        print(f"[ERROR] GAME_DATA_ROOT does not exist: {data_root}")
        return

    # Load existing global PFk registry
    global_reg = load_yaml(GLOBAL_PFK_PATH)
    if "PFKRegistry" not in global_reg:
        global_reg["PFKRegistry"] = {}
    global_pfk = global_reg["PFKRegistry"]

    sha_to_pfk = {info.get("sha1"): pfk for pfk, info in global_pfk.items() if "sha1" in info}

    # Duplicate detection table
    hash_table = defaultdict(list)

    print(f"[INFO] Traversing GIANTS data folder: {data_root}")
    count = 0

    for root, dirs, files in os.walk(data_root):
        for fname in files:

            abs_path = f"{root}/{fname}"
            rel_path = abs_path[len(data_root)+1:]
            logical_path = f"$data/{rel_path}"

            # -------------------------------
            # CORRECT FILTER ORDER
            # -------------------------------
            lower = fname.lower()

            if not (
                lower.endswith((".dds", ".png")) or
                (lower.endswith(".xml") and "/shaders/" in logical_path.lower())
            ):
                continue

            count += 1
            if count % 2000 == 0:
                print(f"[INFO] Processed {count} files...")

            try:
                sha = sha1_file(abs_path)
            except Exception as e:
                print(f"[WARN] Failed to hash {abs_path}: {e}")
                continue

            # Duplicate detection
            hash_table[sha].append(logical_path)

            # PFk assignment
            if sha in sha_to_pfk:
                pfk = sha_to_pfk[sha]
            else:
                pfk = pfk_from_sha1(sha)
                i = 0
                while pfk in global_pfk and global_pfk[pfk].get("sha1") != sha:
                    i += 1
                    if i + 4 > len(sha):
                        raise RuntimeError(f"PFk collision resolution failed for SHA {sha}")
                    pfk = sha[i:i+4].upper()
                sha_to_pfk[sha] = pfk

            # NEW FORMAT: accumulate all file paths
            entry = global_pfk.setdefault(pfk, {"sha1": sha, "files": []})

            # Safety check
            if entry["sha1"] != sha:
                raise RuntimeError(f"PFK {pfk} has conflicting SHA1 values!")

            # Add this file path
            entry["files"].append(logical_path)

    save_yaml(GLOBAL_PFK_PATH, global_reg)

    print(f"[INFO] Global PFk updated: {GLOBAL_PFK_PATH}")
    print(f"[INFO] Unique SHA1 count: {len(sha_to_pfk)}")
    print("[DONE] GIANTS data folder scan complete.\n")

def scan_mats_folder():
    print("\n=== SCAN CUSTOM MATS FOLDER (GLOBAL PFK BUILDER) ===")

    mats_root = PATHS["global_mats_dir"]
    if not os.path.isdir(mats_root):
        print(f"[ERROR] Mats folder does not exist: {os.path.abspath(mats_root)}")
        return

    # Load existing global PFk registry
    global_reg = load_yaml(GLOBAL_PFK_PATH)
    if "PFKRegistry" not in global_reg:
        global_reg["PFKRegistry"] = {}
    global_pfk = global_reg["PFKRegistry"]

    # SHA → PFk lookup
    sha_to_pfk = {
        info.get("sha1"): pfk
        for pfk, info in global_pfk.items()
        if "sha1" in info
    }

    hash_table = defaultdict(list)

    print(f"[INFO] Traversing mats folder: {mats_root}")

    for root, dirs, files in os.walk(mats_root):
        for fname in files:
            if not fname.lower().endswith((".dds", ".png")):
                continue

            abs_path = f"{root}/{fname}"
            rel_path = abs_path[len(mats_root)+1:]
            logical_path = f"$mats/{rel_path}"

            try:
                sha = sha1_file(abs_path)
            except Exception as e:
                print(f"[WARN] Failed to hash {abs_path}: {e}")
                continue

            hash_table[sha].append(logical_path)

            # Existing PFk?
            if sha in sha_to_pfk:
                pfk = sha_to_pfk[sha]
                entry = global_pfk.get(pfk)

                # If entry is old format, convert it
                if "path" in entry:
                    old_path = entry["path"]
                    entry["files"] = [old_path]
                    del entry["path"]

                existing_paths = entry["files"]

                # Do NOT override $data
                if any(p.startswith("$data") for p in existing_paths):
                    pass

                # Override mod paths
                elif any(p.startswith("mods/") or p.startswith("$mod") for p in existing_paths):
                    print(f"[INFO] Overriding mod path with mats: {existing_paths} -> {logical_path}")
                    entry["files"] = [logical_path]

                # Replace anything else weird
                else:
                    print(f"[INFO] Replacing non-data path with mats: {existing_paths} -> {logical_path}")
                    entry["files"] = [logical_path]

            else:
                # New PFk
                pfk = pfk_from_sha1(sha)
                i = 0
                while pfk in global_pfk and global_pfk[pfk].get("sha1") != sha:
                    i += 1
                    if i + 4 > len(sha):
                        raise RuntimeError(f"PFk collision resolution failed for SHA {sha}")
                    pfk = sha[i:i+4].upper()

                sha_to_pfk[sha] = pfk

                global_pfk[pfk] = {
                    "sha1": sha,
                    "files": [logical_path]
                }

    save_yaml(GLOBAL_PFK_PATH, global_reg)

    print(f"[INFO] Mats PFk updated: {GLOBAL_PFK_PATH}")
    print("[DONE] Mats folder scan complete.\n")

# =============================================================================
# GIANTS PMK GLOBAL BUILDER
# =============================================================================

GIANTS_PMK_PATH = os.path.join(PATHS["global_yaml_dir"], "pmk_giants.yaml")
GIANTS_DUPES_PATH = os.path.join(PATHS["global_yaml_dir"], "pfk_data_dupes.txt")

def load_dupe_map(dupe_file_path):
    dupe_map = defaultdict(list)

    if not os.path.isfile(dupe_file_path):
        return dupe_map

    with open(dupe_file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if line.startswith("$"):
                line = line.replace("\\", "/")
                base = stem(line)
                dupe_map[base].append(line)

    return dupe_map

def build_giants_pmks():
    """
    Scan GIANTS $data I3Ds, resolve fileIds to PFks using global PFk + dupes,
    build PMKs, and write pmk_giants.yaml (PMKRegistry).
    """
    print("\n=== BUILD GIANTS PMK GLOBAL ===")

    data_root = GAME_DATA_ROOT
    if not os.path.isdir(data_root):
        print(f"[ERROR] GAME_DATA_ROOT does not exist: {data_root}")
        return

    # Load global PFk registry (REQUIRED)
    global_pfk_reg = load_yaml(GLOBAL_PFK_PATH)
    if "PFKRegistry" not in global_pfk_reg:
        print(f"[FATAL] Global PFKRegistry missing: {GLOBAL_PFK_PATH}")
        print("[FATAL] Cannot continue GIANTS scan without global PFKs.")
        return  # Hard stop — no point scanning anything

    global_pfk = global_pfk_reg["PFKRegistry"]

    # Load existing GIANTS PMK registry (optional)
    giants_pmk_reg = load_yaml(GIANTS_PMK_PATH)
    if "PMKRegistry" not in giants_pmk_reg:
        giants_pmk_reg["PMKRegistry"] = {}
    giants_pmk = giants_pmk_reg["PMKRegistry"]

    # Load dupes (optional but helpful)
    dupe_map = load_dupe_map(GIANTS_DUPES_PATH)

    # Collect all GIANTS I3Ds
    giants_i3d_files = []
    for root, dirs, files in os.walk(data_root):
        for fname in files:
            if fname.lower().endswith(".i3d"):
                giants_i3d_files.append(f"{root}/{fname}")

    print(f"[INFO] Found {len(giants_i3d_files)} GIANTS I3D file(s).")

    total_materials = 0
    total_pmks = 0

    for i3d_path in giants_i3d_files:
        rel_i3d = os.path.relpath(i3d_path, data_root)
        print(f"[INFO] Scanning GIANTS I3D: $data/{rel_i3d}")

        file_entries = parse_files_section(i3d_path)
        fileid_to_pfk_local = {}

        for file_id, fname in file_entries:

            abs_path = resolve_path(fname)
            logical_path = fname
            lookup_path = abs_path


            pfk = lookup_pfk_by_sha(lookup_path, global_pfk)

            if pfk is None:
                print(f"[WARN] No PFk for '{fname}' in $data/{rel_i3d}")
                continue

            fileid_to_pfk_local[file_id] = pfk

        def safe_pfk_lookup(fid):
            return fileid_to_pfk_local.get(fid, "????")

        # Parse materials
        tree = ET.parse(i3d_path)
        root = tree.getroot()

        for mat in root.iter("Material"):
            total_materials += 1
            pmk_hash, entry = process_material(mat, safe_pfk_lookup, i3d_path)

            # NEW BEHAVIOR: skip broken PMKs, continue scanning
            if pmk_hash is None:
                continue

            # If this PMK already exists with same sha1, reuse
            if pmk_hash in giants_pmk:
                existing_sha = giants_pmk[pmk_hash].get("sha1")
                if existing_sha == entry["sha1"]:
                    # Deduped file path logging
                    paths = giants_pmk[pmk_hash].setdefault("filePaths", [])
                    if i3d_path not in paths:
                        paths.append(i3d_path)

                    print(f"[INFO] GIANTS PMK {pmk_hash} already exists for {entry['materialName']} — added path: {i3d_path}")
                    continue


            giants_pmk[pmk_hash] = entry
            total_pmks += 1
            print(f"[INFO] GIANTS PMK {pmk_hash} for material {entry['materialName']}")

    print("\n================ GIANTS PMK SUMMARY ================")
    print(f"Total GIANTS materials scanned: {total_materials}")
    print(f"Total GIANTS PMKs added:       {total_pmks}")
    print("====================================================\n")

    # Save GIANTS PMK registry
    save_yaml(GIANTS_PMK_PATH, giants_pmk_reg)
    print(f"[INFO] GIANTS PMK saved: {GIANTS_PMK_PATH}")

# =============================================================================
# I3D SUMMARY TOOL (Human‑Readable, PMK Extracted From Name)
# =============================================================================

def summarize_i3d_human(i3d_path):
    print(f"\n=== I3D SUMMARY (Human View): {i3d_path} ===\n")

    # Parse I3D
    tree = ET.parse(i3d_path)
    root = tree.getroot()

    # ------------------------------------------------------------
    # FILES SECTION
    # ------------------------------------------------------------
    print("<Files>")

    file_entries = parse_files_section(i3d_path)

    for file_id, fname in file_entries:
        # Resolve path for display only
        abs_path, logical_path = resolve_path(fname)

        # NEW: PFk lookup ONLY by fileId
        pfk = fileid_to_pfk.get(file_id, "????")

        print(f"  {file_id} → {pfk}")

    print("</Files>\n")

    # ------------------------------------------------------------
    # MATERIALS SECTION
    # ------------------------------------------------------------
    print("<Materials>")

    for mat in root.iter("Material"):
        mat_name = mat.attrib.get("name", "").strip()
        mat_id   = mat.attrib.get("materialId", "").strip()

        # Extract PMK from name: "foo__AB12" → "AB12"
        pmk = "????"
        if "__" in mat_name:
            suffix = mat_name.split("__")[-1]
            if len(suffix) == 4 and suffix.isalnum():
                pmk = suffix.upper()

        print(f"  {mat_name}, {mat_id}, {pmk}")

    print("</Materials>\n")

    # ------------------------------------------------------------
    # SCENE SECTION
    # ------------------------------------------------------------
    print("<Scene>")

    scene = root.find("Scene")
    if scene is None:
        print("  [ERROR] No <Scene> found.")
        return

    def walk(node, path):
        name = node.attrib.get("name", "")
        mat_ids = node.attrib.get("materialIds", "")

        if mat_ids:
            pmks = []
            for mid in mat_ids.split(","):
                mid = mid.strip()

                # PMK lookup by materialName suffix ONLY
                pmk = "????"
                mat_node = root.find(f".//Material[@id='{mid}']")
                if mat_node is not None:
                    mat_name = mat_node.attrib.get("name", "")
                    if "__" in mat_name:
                        suffix = mat_name.split("__")[-1]
                        if len(suffix) == 4 and suffix.isalnum():
                            pmk = suffix.upper()

                pmks.append(pmk)

            pmk_list = ", ".join(pmks)
            print(f"  {name}, {pmk_list}")
        else:
            print(f"  {name}, ()")

        for i, child in enumerate(list(node)):
            walk(child, path + [i])

    walk(scene, [])

    print("</Scene>\n")

def rewrite_material_ids(i3d_in: str, i3d_out: str, pmk_registry: dict):
    """
    Reads an I3D file where materialIds may contain PMKs (4-hex-digit),
    resolves them to actual materialIds using pmk_registry,
    and writes the corrected I3D file.
    """

    shape_re = re.compile(r'<Shape\b[^>]*>')
    mat_re   = re.compile(r'materialIds="([^"]*)"')

    in_scene = False

    with open(i3d_in, "r", encoding="utf-8") as fin, \
         open(i3d_out, "w", encoding="utf-8") as fout:

        for line in fin:
            stripped = line.lstrip()

            # Track <Scene> boundaries
            if "<Scene" in stripped:
                in_scene = True
            if "</Scene" in stripped:
                in_scene = False

            # Only modify <Shape> lines inside <Scene>
            if in_scene and "<Shape" in stripped and shape_re.search(stripped):

                mat_match = mat_re.search(stripped)
                if mat_match:
                    raw = mat_match.group(1).strip()

                    # Split materialIds
                    parts = [p.strip() for p in raw.split(",") if p.strip()]

                    resolved = []
                    for p in parts:
                        # Detect PMK (4 hex chars)
                        if len(p) == 4 and all(c in "0123456789ABCDEFabcdef" for c in p):
                            # Resolve PMK → materialId
                            if p in pmk_registry:
                                resolved.append(str(pmk_registry[p]["materialId"]))
                            else:
                                print(f"[WARN] Unknown PMK {p}, leaving unchanged.")
                                resolved.append(p)
                        else:
                            # Already a materialId
                            resolved.append(p)

                    new_mat_ids = ",".join(resolved)

                    # Replace in line
                    def repl(m):
                        return f'materialIds="{new_mat_ids}"'

                    stripped = mat_re.sub(repl, stripped)
                    line = line[:len(line) - len(line.lstrip())] + stripped

            fout.write(line)

def rewrite_i3d_paths(i3d_path):
    """
    Rewrites <Files> entries inside an I3D using canonical PFk paths.
    - $data paths remain $data
    - $mats paths are rewritten to textures/ (GE-friendly cheat)
    - mod-local canonical paths remain unchanged
    """

    # Load PFk registry and dupe map
    global_reg = load_yaml(GLOBAL_PFK_PATH)
    global_pfk = global_reg.get("PFKRegistry", {})

    # Load the I3D XML
    try:
        tree = ET.parse(i3d_path)
    except Exception as e:
        print(f"[ERROR] Failed to parse I3D '{i3d_path}': {e}")
        return

    root = tree.getroot()
    files_node = root.find("Files")

    if files_node is None:
        print(f"[ERROR] I3D has no <Files> section: {i3d_path}")
        return

    # Iterate through <Files> entries
    for file_node in files_node:
        i3d_files_filename = file_node.attrib.get("filename")

        # Resolve the filename to full path
        resolved_full_path = resolve_path(i3d_files_filename)
        if resolved_full_path is None:
            print(f"[WARN] Cannot resolve '{i3d_files_filename}' — skipping.")
            continue  # DO NOT abort the entire rewrite

        # PFk lookup (stem-only)
        pfk = lookup_pfk_stem_only(resolved_full_path, global_pfk)
        if not pfk:
            continue

        pfk_info = global_pfk.get(pfk)
        if not pfk_info:
            continue

        canonical_pfks_path = pfk_info.get("path")

        # -------------------------------------------------------------
        # APPLY $mats → textures/ REWRITE
        # -------------------------------------------------------------
        if canonical_pfks_path.startswith("$mats/"):
            # GE cannot understand "$mats"
            i3d_rewrite_path = "textures/" + canonical_pfks_path.split("/", 1)[1]
        else:
            i3d_rewrite_path = canonical_pfks_path

        # Rewrite the I3D filename attribute
        file_node.set("filename", i3d_rewrite_path)

    # Save the modified I3D
    tree.write(i3d_path)
    print(f"[OK] Rewrote paths in main I3D: {i3d_path}")

# -------------------------------------------------------------------------
# REPAIR I3D PATHS (STANDALONE TOOL)
# -------------------------------------------------------------------------

def repair_i3d_paths():
    """
    Standalone utility to repair <File filename="..."> entries in ONLY the main I3D file.
    Uses rewrite_i3d_paths() to apply canonical PFK paths and the $mats→textures
    Giants Editor compatibility rewrite. Does NOT modify PFK registries.
    Abort if more than one I3D is found in main_i3d_dir.
    """
    main_i3d_dir = PATHS["main_i3d_dir"].replace("\\", "/")
    main_i3ds = glob.glob(f"{main_i3d_dir}/*.i3d")

    if not main_i3ds:
        print("[ERROR] No main I3D found in main_i3d_dir.")
        return

    if len(main_i3ds) > 1:
        print("[ERROR] Multiple I3D files found in main_i3d_dir. Aborting to avoid rewriting the wrong file.")
        for p in main_i3ds:
            print(f" - {p}")
        return

    # Exactly one I3D → safe to rewrite
    rewrite_i3d_paths(main_i3ds[0])

def check_filename_uniqueness():
    """
    For each filename that maps to multiple PFKs,
    list all paths where that filename occurs.
    Uses PFK global + dupes file only.
    """

    global_reg = load_yaml(GLOBAL_PFK_PATH)
    pfk_global = global_reg.get("PFKRegistry", {})

    # filename -> { pfk -> [paths...] }
    filename_map = {}

    # -------------------------------------------------------------
    # PASS 1: PFK GLOBAL
    # -------------------------------------------------------------
    for pfk, info in pfk_global.items():
        for p in info.get("files", []):
            p = p.replace("\\", "/")
            filename = p.rsplit("/", 1)[-1]

            filename_map.setdefault(filename, {})
            filename_map[filename].setdefault(pfk, []).append(p)

    # -------------------------------------------------------------
    # REPORT
    # -------------------------------------------------------------
    print("\n=== FILENAME DUPLICATE LOCATION REPORT (PFK-based) ===")

    # Only filenames with multiple PFKs
    collisions = [
        (fn, pfk_dict)
        for fn, pfk_dict in filename_map.items()
        if len(pfk_dict) > 1
    ]

    print(f"Total filenames with multiple PFKs: {len(collisions)}\n")

    # Sort by severity (most PFKs first)
    collisions.sort(key=lambda x: len(x[1]), reverse=True)

    for filename, pfk_dict in collisions:
        print(f"{filename} ({len(pfk_dict)} PFKs):")
        for pfk, paths in pfk_dict.items():
            print(f"  PFK {pfk}:")
            for p in paths:
                print(f"    {p}")
        print()

def report_pathname_uniqueness():
    """
    Checks whether any full pathname maps to multiple PFKs.
    This should never happen because paths are unique.
    Uses PFK global + dupes file only.
    """

    global_reg = load_yaml(GLOBAL_PFK_PATH)
    pfk_global = global_reg.get("PFKRegistry", {})


    # pathname -> set of PFKs
    pathname_map = {}

    # -------------------------------------------------------------
    # PASS 1: PFK GLOBAL
    # -------------------------------------------------------------
    for pfk, info in pfk_global.items():
        for p in info.get("files", []):
            p_clean = p.replace("\\", "/")

            if p_clean not in pathname_map:
                pathname_map[p_clean] = set()

            pathname_map[p_clean].add(pfk)

    # -------------------------------------------------------------
    # REPORT
    # -------------------------------------------------------------
    print("\n=== PATHNAME UNIQUENESS REPORT (PFK-based) ===")

    collisions = [
        (path, pfk_set)
        for path, pfk_set in pathname_map.items()
        if len(pfk_set) > 1
    ]

    print(f"Total pathnames checked: {len(pathname_map)}")
    print(f"Pathnames with multiple PFKs: {len(collisions)}\n")

    if collisions:
        print("--- COLLISIONS DETECTED ---")
        for path, pfk_set in collisions:
            print(f"{path}: {pfk_set}")
    else:
        print("All pathnames map to exactly one PFK. No collisions.")

def stem(path):
    """Return filename without extension (GIANTS-style)."""
    path = path.replace("\\", "/")
    filename = path.rsplit("/", 1)[-1]
    return filename.split(".", 1)[0].lower()

def lookup_pfk_stem_only(name_or_path, local_pfk, global_pfk):
    """
    Lookup PFk by stem-only, preferring local PFk registry first,
    then falling back to global PFk registry.
    """

    # Normalize and extract stem (filename without extension)
    clean = name_or_path.replace("\\", "/")
    target = clean.rsplit("/", 1)[-1].split(".", 1)[0].lower()

    # -------------------------------------------------------------
    # 1. LOCAL PFk lookup (mod-local assets)
    # -------------------------------------------------------------
    for pfk, info in local_pfk.items():
        for f in info.get("files", []):
            f_clean = f.replace("\\", "/")
            f_stem = f_clean.rsplit("/", 1)[-1].split(".", 1)[0].lower()
            if f_stem == target:
                return pfk

    # -------------------------------------------------------------
    # 2. GLOBAL PFk lookup (GIANTS + mod-local alternates)
    # -------------------------------------------------------------
    for pfk, info in global_pfk.items():
        for f in info.get("files", []):
            f_clean = f.replace("\\", "/")
            f_stem = f_clean.rsplit("/", 1)[-1].split(".", 1)[0].lower()
            if f_stem == target:
                return pfk

    # -------------------------------------------------------------
    # No match
    # -------------------------------------------------------------
    return None

def lookup_pfk_by_base_filename(name_or_path, global_pfk):
    # Normalize and extract base filename (no extension)
    clean = name_or_path.replace("\\", "/")
    base = clean.rsplit("/", 1)[-1].split(".", 1)[0].lower()

    # Search PFk registry
    for pfk, info in global_pfk.items():
        for f in info.get("files", []):
            f_clean = f.replace("\\", "/")
            f_base = f_clean.rsplit("/", 1)[-1].split(".", 1)[0].lower()
            if f_base == base:
                return pfk

    return None

def lookup_pfk_by_path_no_ext(path, global_pfk):
    # Normalize and remove extension
    clean = path.replace("\\", "/").lower()
    base_path = clean.rsplit(".", 1)[0]

    for pfk, info in global_pfk.items():
        for f in info.get("files", []):
            f_clean = f.replace("\\", "/").lower()
            f_base = f_clean.rsplit(".", 1)[0]

            if f_base == base_path:
                return pfk

    return None

def lookup_pfk_by_sha(path, global_pfk):
    # Compute SHA using your PNG/DDS logic
    _, sha1 = png_this(path)

    # If SHA cannot be computed, THAT is worth warning about
    if not isinstance(sha1, str):
        print(f"[SHA WARN] Cannot compute SHA for '{path}'")
        return None

    # Walk PFk registry
    for pfk, info in global_pfk.items():
        pfk_sha = info.get("sha1")
        if isinstance(pfk_sha, str) and pfk_sha == sha1:
            return pfk

    # No PFk match — but do NOT warn here
    return None

def png_this(abs_path, prefer_dds=False, prefer_i3d=False, force_dds=False):
    # XML fast-path
    if abs_path.lower().endswith(".xml"):
        if os.path.isfile(abs_path):
            return abs_path, sha1_file(abs_path).lower()
        return None, None

    # Split extension
    stem, ext = os.path.splitext(abs_path)

    png_path = stem + ".png"
    dds_path = stem + ".dds"

    png_sha = sha1_file(png_path).lower() if os.path.isfile(png_path) else None
    dds_sha = sha1_file(dds_path).lower() if os.path.isfile(dds_path) else None

    # Force DDS
    if force_dds and dds_sha:
        return dds_path, dds_sha

    # DDS wins if PNG missing
    if dds_sha and not png_sha:
        return dds_path, dds_sha

    # PNG wins if DDS missing
    if png_sha and not dds_sha:
        return png_path, png_sha

    # Both exist and match
    if png_sha and dds_sha and png_sha == dds_sha:
        return dds_path, dds_sha

    # Conflict
    if png_sha and dds_sha and png_sha != dds_sha:
        if prefer_dds:
            return dds_path, dds_sha
        if prefer_i3d:
            return (png_path, png_sha) if ext.lower() == ".png" else (dds_path, dds_sha)
        return None, None

    # Nothing found
    return None, None

def extract_suffix(name: str):
    """
    Extracts a 4-hex-digit suffix from a name.
    Example: 'chrome__7D11' → '7D11'
    Example: 'leftFender_A3F9' → 'A3F9'
    """
    name = name.strip()
    m = re.search(r'([0-9A-Fa-f]{4})$', name)
    return m.group(1).upper() if m else None

def extract_core_name(name: str):
    """
    Removes Blender prefix, PMK/PNK suffix, and junk.
    Returns the descriptive core name.
    """
    name = name.strip()

    # Remove Blender prefix: "010.020.030-"
    name = re.sub(r'^\d+(\.\d+)*[-_]', '', name)

    # Remove PMK/PNK suffix: "__AB12" or "_AB12"
    name = re.sub(r'[_-]{1,2}[0-9A-Fa-f]{4}$', '', name)

    return name.strip()

def resolve_identity(name: str, registry: dict):
    """
    Returns (identity_key, core_name).
    identity_key = PMK or PNK key.
    core_name = descriptive name without prefix/suffix.
    """

    suffix = extract_suffix(name)
    core = extract_core_name(name)

    # 1. Try suffix match
    if suffix and suffix in registry:
        return suffix, core

    # 2. Try core name match
    for key, info in registry.items():
        if info.get("materialName", "") == core or info.get("nodeName", "") == core:
            return key, core

    return None, core

def update_registry_name_if_changed(identity_key: str, core_name: str, registry: dict, name_field: str):
    """
    Updates registry[name_field] if modder changed descriptive name.
    name_field = 'materialName' or 'nodeName'
    """

    stored = registry[identity_key].get(name_field, "")
    if stored != core_name:
        registry[identity_key][name_field] = core_name
        print(f"[INFO] Updated registry {identity_key} {name_field} → '{core_name}'")

def rename_materials_with_pmk():
    print("\n=== MATERIAL RENAME USING PMK SUFFIX ===")

    # Load PMK registry (same as your existing code)
    pmk_registry = load_pmk_registry()

    # Locate main I3D
    main_i3d = find_main_i3d()
    tree = ET.parse(main_i3d)
    root = tree.getroot()

    materials = root.findall(".//Material")

    for mat in materials:
        raw_name = mat.get("name", "").strip()
        if not raw_name:
            continue

        identity_key, core_name = resolve_identity(raw_name, pmk_registry)
        if not identity_key:
            print(f"[WARN] No PMK identity for '{raw_name}'")
            continue

        # Update registry if descriptive name changed
        update_registry_name_if_changed(identity_key, core_name, pmk_registry, "materialName")

        # Build new name with suffix
        new_name = f"{core_name}__{identity_key}"

        mat.set("name", new_name)

    tree.write(main_i3d, encoding="utf-8", xml_declaration=True)

def rename_nodes_with_pnk():
    print("\n=== NODE RENAME USING PNK SUFFIX ===")

    pnk_registry = load_pnk_registry()

    main_i3d = find_main_i3d()
    tree = ET.parse(main_i3d)
    root = tree.getroot()

    shapes = root.findall(".//Shape")

    for shp in shapes:
        raw_name = shp.get("name", "").strip()
        if not raw_name:
            continue

        identity_key, core_name = resolve_identity(raw_name, pnk_registry)
        if not identity_key:
            print(f"[WARN] No PNK identity for '{raw_name}'")
            continue

        update_registry_name_if_changed(identity_key, core_name, pnk_registry, "nodeName")

        new_name = f"{core_name}_{identity_key}"

        shp.set("name", new_name)

    tree.write(main_i3d, encoding="utf-8", xml_declaration=True)

# =============================================================================
# MENU / MAIN
# =============================================================================

# -------------------------------------------------------------------------
# MENU OPTION DESCRIPTIONS
# -------------------------------------------------------------------------

# 1. Majik_mapper (FULL I3D)
#    Runs Majik_mapper in full mode. Parses entire I3D, rewrites nodes,
#    remaps materials, and applies all mapping logic.

# 2. Majik_mapper (XML-only)
#    Runs Majik_mapper without touching geometry. Only XML sections are
#    processed and remapped.

# 3. Majik_mapper (XML-remap)
#    Remaps XML-only sections using existing mapping rules. No geometry
#    parsing, no raw dump.

# 4. Majik_mapper (RAW dump)
#    Dumps raw I3D node and material data for debugging. No remapping.

# 5. Clone Hunter (PFK Builder)
#    Scans all I3Ds, fingerprints every file, assigns PFK identities,
#    canonicalizes paths, detects duplicates, and updates PFk registries.

# 6. Build PMKs
#    Generates PMK (material fingerprint) files for the mod. Requires
#    canonical PFK registry.

# 7. Build PNKs v2
#    Generates PNK identity files using the v2 pipeline. Replaces all
#    legacy PMK/PNK logic. This is the correct, modern builder.

# 8. Material Sync
#    Syncs material definitions between I3D and XML. Ensures consistent
#    material naming, slot usage, and texture references.

# 9. Node Sync
#    Syncs node names, transforms, and hierarchy between I3D and XML.

# 10. Rename Materials Using PNK Suffix
#    Renames materials in the I3D using PNK suffixes for consistency
#    with the v2 identity system.

# 11. Scan GIANTS Data Folder (PFK Global Builder)
#     Scans GIANTS $data folder, fingerprints all DDS/PNG files and shaders,
#      updates the global PFk registry, and detects duplicates.

# 12. Scan Mats Folder (update global PFk)
#     Scans your custom $mats folder, fingerprints files, and updates
#     the global PFk registry.

# 13. Build GIANTS PMKs (Global GIANTS Material Fingerprint)
#     Builds PMKs for GIANTS materials using the global PFk registry.
#     (Legacy support — still useful for GIANTS assets.)

# 14. Summarize I3D (Human View)
#     Prints a human-readable summary of the I3D: materials, textures,
#     PFK identities, and resolved canonical paths.

# 15. Repair I3D <Files filename= values>
#     Rewrites <File filename="..."> entries using canonical PFK paths.
#     Converts $mats → textures/ for Giants Editor compatibility.
#     Does NOT modify PFk registries.

# 16. Check dupes by file name
#     Reports duplicate PFk/PNK/PMK entries that share the same filename.

# 17. Check dupes by path
#     Reports duplicate PFk/PNK/PMK entries that share the same canonical path.

# 18. Exit
#     Quit the tool.


def menu():
    while True:
        print("\n=== FS25 Unified Tool ===")
        print("1. Majik_mapper (FULL I3D)")
        print("2. Majik_mapper (XML-only)")
        print("3. Majik_mapper (XML-remap)")
        print("4. Majik_mapper (RAW dump)")
        print("5. Clone Hunter (PFK Builder)")
        print("6. Build PMKs")
        print("7. Build PNKs v2")
        print("8. Material Sync")
        print("9. Node Sync")
        print("10. Rename Materials Using PNK Suffix")
        print("11. Mat-Man GIANTS $data chomper (PFK Global Builder)")
        print("12. Scan Mats Folder (update global PFk)")
        print("13. Build GIANTS PMKs (Global GIANTS Material Fingerprint)")
        print("14. Summarize I3D (Human View)")
        print("15. Repair I3D <Files filename=\"...\"> values")
        print("16. Check dupes by file name")
        print("17. Check dupes by path")
        print("18. Exit")

        choice = input("Select option: ").strip()

        try:
            if choice == "1":
                run_majik_mapper_mode("full")
            elif choice == "2":
                run_majik_mapper_mode("xml-only")
            elif choice == "3":
                run_majik_mapper_mode("remap")
            elif choice == "4":
                run_majik_mapper_mode("raw")
            elif choice == "5":
                build_pfks()
            elif choice == "6":
                build_pmks()
            elif choice == "7":
                build_pnks_v2()
            elif choice == "8":
                run_material_sync()
            elif choice == "9":
                node_sync()
            elif choice == "10":
                rename_materials_with_pnk()
            elif choice == "11":
                scan_giants_data_folder()
            elif choice == "12":
                scan_mats_folder()
            elif choice == "13":
                build_giants_pmks()
            elif choice == "14":
                i3d_files = find_i3d_files()
                if not i3d_files:
                    print("[ERROR] No I3D files found.")
                else:
                    summarize_i3d_human(i3d_files[0])
            elif choice == "15":
                print("[INFO] Repairing I3D paths...")
                repair_i3d_paths()
                print("[INFO] I3D path repair complete.")
            elif choice == "16":
                check_filename_uniqueness()
            elif choice == "17":
                report_pathname_uniqueness()
            elif choice == "18":
                break
            else:
                print("Invalid option.")
        except Exception as e:
            print(f"[ERROR] {e}")

if __name__ == "__main__":
    menu()
