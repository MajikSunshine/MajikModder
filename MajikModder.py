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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Assume this lives in mods/<ModName>/file_sync or similar
    mod_dir = os.path.dirname(script_dir)
    mods_root = os.path.dirname(mod_dir)
    mod_name = os.path.basename(mod_dir)

    main_i3d_dir = os.path.join(mod_dir, mod_name)
    file_sync_dir = os.path.join(mod_dir, "file_sync")
    material_sync_dir = os.path.join(mod_dir, "material_sync")
    node_sync_dir = os.path.join(mod_dir, "node_sync")
    i3d_maps_dir = os.path.join(mod_dir, "i3dMaps")
    local_yaml_dir = os.path.join(mod_dir, "_assets", "YAML")
    global_yaml_dir = os.path.join(mods_root, "_assets", "YAML")

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
    }

PATHS = detect_script_dirs()

GAME_DATA_ROOT = r"D:\portable\GIANTS Software\Farming Simulator 2025\data"

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

    if filename.startswith("$data/") or filename.startswith("$data\\"):
        rel = filename[len("$data/"):] if filename.startswith("$data/") else filename[len("$data\\"):]
        rel = rel.replace("/", os.sep)
        abs_path = os.path.join(GAME_DATA_ROOT, rel)

        if abs_path.lower().endswith(".png") and not os.path.isfile(abs_path):
            dds_path = abs_path[:-4] + ".dds"
            if os.path.isfile(dds_path):
                print(f"[DEBUG] PNG fallback → DDS: {dds_path}")
                return dds_path, filename

        if os.path.isfile(abs_path):
            return abs_path, filename

        print(f"[WARN] $data file not found: {filename}")
        return None, filename

    abs_path = os.path.join(main_i3d_dir, filename.replace("/", os.sep))
    if os.path.isfile(abs_path):
        return abs_path, filename

    print(f"[WARN] Mod file not found: {filename}")
    return None, filename

def find_i3d_files():
    files = []
    main_i3d_dir = PATHS["main_i3d_dir"]
    file_sync_dir = PATHS["file_sync_dir"]
    files.extend(glob.glob(os.path.join(main_i3d_dir, "*.i3d")))
    files.extend(glob.glob(os.path.join(file_sync_dir, "*.i3d")))
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

GLOBAL_PFK_PATH = os.path.join(PATHS["global_yaml_dir"], "pfk_global.yaml")
LOCAL_PFK_PATH  = os.path.join(PATHS["local_yaml_dir"],  "pfk.yaml")

GLOBAL_PMK_PATH = os.path.join(PATHS["global_yaml_dir"], "pmk_global.yaml")
LOCAL_PMK_PATH  = os.path.join(PATHS["local_yaml_dir"],  "pmk.yaml")

# Add these for PNK:
GLOBAL_PNK_PATH = os.path.join(PATHS["global_yaml_dir"], "pnk_global.yaml")
LOCAL_PNK_PATH  = os.path.join(PATHS["local_yaml_dir"],  "pnk.yaml")

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

def pfk_lookup(file_id):
    if file_id not in fileid_to_pfk:
        raise KeyError(f"Unknown fileId {file_id} in PMK builder")
    return fileid_to_pfk[file_id]

def build_pmk_identity(material_node, pfk_lookup_func):
    identity = {}
    for attr, val in material_node.attrib.items():
        if attr in ("materialId", "name"):
            continue
        if attr == "customShaderId":
            identity["shader"] = pfk_lookup_func(val)
            continue
        identity.setdefault("parameters", {})[attr] = normalize_value(val)

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

def process_material(material_node, pfk_lookup_func):
    identity = build_pmk_identity(material_node, pfk_lookup_func)
    serialized = json.dumps(identity, sort_keys=True)
    sha = hashlib.sha1(serialized.encode("utf-8")).hexdigest()
    pmk_hash = hash_pmk(identity)
    entry = build_pmk_entry(material_node, identity, pmk_hash, sha)
    return pmk_hash, entry

def build_pfks():
    global fileid_to_pfk
    global global_pfk
    global local_pfk

    global_reg = load_yaml(GLOBAL_PFK_PATH)
    local_reg = load_yaml(LOCAL_PFK_PATH)

    if "PFKRegistry" not in global_reg:
        global_reg["PFKRegistry"] = {}
    if "PFKRegistry" not in local_reg:
        local_reg["PFKRegistry"] = {}

    global_pfk = global_reg["PFKRegistry"]
    local_pfk = local_reg["PFKRegistry"]

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

    i3d_files = find_i3d_files()
    print(f"[INFO] Found {len(i3d_files)} I3D file(s) to scan.")
    seen_files = set()

    for i3d_path in i3d_files:
        rel_i3d = os.path.relpath(i3d_path, PATHS["mod_dir"])
        print(f"[INFO] Scanning I3D: {rel_i3d}")
        file_entries = parse_files_section(i3d_path)
        print(f"[DEBUG] parse_files_section returned {len(file_entries)} entries")
        for file_id, fname in file_entries:
            print(f"[DEBUG] Entry: file_id={file_id}, path='{fname}'")
            if fname in seen_files:
                print(f"[DEBUG] Skipped: '{fname}' already in seen_files")
                continue
            print(f"[DEBUG] New entry: '{fname}' not in seen_files")
            seen_files.add(fname)

            abs_path, logical_path = resolve_path(fname)
            if abs_path is None:
                continue

            sha = sha1_file(abs_path)

            if sha in sha_to_pfk:
                pfk = sha_to_pfk[sha]
                canonical_path = global_pfk.get(pfk, {}).get("path", logical_path)
                if logical_path.startswith("$data") and not canonical_path.startswith("$data"):
                    canonical_path = logical_path
                    global_pfk[pfk]["path"] = canonical_path
            else:
                pfk = pfk_from_sha1(sha)
                i = 0
                while pfk in global_pfk and global_pfk[pfk].get("sha1") != sha:
                    i += 1
                    if i + 4 > len(sha):
                        raise RuntimeError(f"PFk collision resolution failed for SHA {sha}")
                    pfk = sha[i:i+4].upper()
                sha_to_pfk[sha] = pfk
                canonical_path = logical_path

            global_pfk[pfk] = {
                "sha1": sha,
                "path": canonical_path,
            }
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

def build_pmks():
    global global_pmk
    global local_pmk

    print("[INFO] Building PMKs...")

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

    pmk_registry = {}

    i3d_files = find_i3d_files()
    for i3d_path in i3d_files:
        tree = ET.parse(i3d_path)
        root = tree.getroot()
        for mat in root.iter("Material"):
            pmk_hash, entry = process_material(mat, pfk_lookup)
            pmk_registry[pmk_hash] = entry
            local_pmk[pmk_hash] = entry
            global_pmk[pmk_hash] = entry
            print(f"[INFO] PMK {pmk_hash} for material {entry['materialName']}")

    save_yaml(LOCAL_PMK_PATH, local_reg)
    save_yaml(GLOBAL_PMK_PATH, global_reg)

    print(f"[INFO] Local PMK saved:  {LOCAL_PMK_PATH}")
    print(f"[INFO] Global PMK saved: {GLOBAL_PMK_PATH}")

# =============================================================================
# PNK (stub)
# =============================================================================

GLOBAL_PNK_PATH = os.path.join(PATHS["global_yaml_dir"], "pnk_global.yaml")
LOCAL_PNK_PATH = os.path.join(PATHS["local_yaml_dir"], "pnk.yaml")

def build_pnks():
    print("[INFO] Building PNKs...")

    # PFk + PMK must exist first
    if not os.path.isfile(LOCAL_PFK_PATH) or not os.path.isfile(LOCAL_PMK_PATH):
        print("[ERROR] PFk and PMK must be built before PNK.")
        return

    # Load existing registries
    global_reg = load_yaml(GLOBAL_PNK_PATH) if os.path.isfile(GLOBAL_PNK_PATH) else {"PNKRegistry": {}}
    local_reg  = load_yaml(LOCAL_PNK_PATH)  if os.path.isfile(LOCAL_PNK_PATH)  else {"PNKRegistry": {}}

    global_pnk = global_reg["PNKRegistry"]
    local_pnk  = local_reg["PNKRegistry"]

    # Scan main I3D
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

    # Walk nodes
    results = []
    for comp_index, child in enumerate(list(scene)):
        walk(child, [comp_index], results)

    # Build PNKs
    pnk_report_lines = []
    for name, path_list in results:
        identity = {
            "name": name,
            "path": compact_path(path_list),
        }

        serialized = json.dumps(identity, sort_keys=True)
        sha = hashlib.sha1(serialized.encode("utf-8")).hexdigest()
        pnk = sha[:4].upper()

        # Collision resolution
        i = 0
        while pnk in global_pnk and global_pnk[pnk].get("sha1") != sha:
            i += 1
            if i + 4 > len(sha):
                raise RuntimeError(f"PNK collision resolution failed for SHA {sha}")
            pnk = sha[i:i+4].upper()

        entry = {
            "name": name,
            "path": identity["path"],
            "sha1": sha
        }

        global_pnk[pnk] = entry
        local_pnk[pnk]  = entry

        pnk_report_lines.append(f"{pnk}  {name}  {identity['path']}")

    # Save registries
    save_yaml(GLOBAL_PNK_PATH, global_reg)
    save_yaml(LOCAL_PNK_PATH, local_reg)

    # Write report
    report_path = os.path.join(PATHS["node_sync_dir"], "pnk_report.txt")
    os.makedirs(PATHS["node_sync_dir"], exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(pnk_report_lines))

    print(f"[INFO] Local PNK saved:  {LOCAL_PNK_PATH}")
    print(f"[INFO] Global PNK saved: {GLOBAL_PNK_PATH}")
    print(f"[INFO] Report written:   {report_path}")

import os
import glob
import json
import hashlib
import xml.etree.ElementTree as ET

# =============================================================================
# PNK v2 – registry paths and globals
# =============================================================================

GLOBAL_PNK_PATH = os.path.join(PATHS["global_yaml_dir"], "pnk_global.yaml")
LOCAL_PNK_PATH  = os.path.join(PATHS["local_yaml_dir"],  "pnk.yaml")

global_pnk = {}
local_pnk  = {}

# =============================================================================
# Helpers
# =============================================================================

def compact_path(path_list):
    if not path_list:
        return ">"
    return "|".join(str(i) for i in path_list) + ">"

def load_yaml(path):
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        import yaml
        return yaml.safe_load(f) or {}

def save_yaml(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        import yaml
        yaml.safe_dump(data, f, sort_keys=True)

# =============================================================================
# PNK v2 builder
# =============================================================================

def build_pnks_v2():
    print("[INFO] Building PNK v2...")

    # Load existing registries
    global_reg = load_yaml(GLOBAL_PNK_PATH)
    local_reg  = load_yaml(LOCAL_PNK_PATH)

    if "PNKRegistry" not in global_reg:
        global_reg["PNKRegistry"] = {}
    if "PNKRegistry" not in local_reg:
        local_reg["PNKRegistry"] = {}

    global_pnk = global_reg["PNKRegistry"]
    local_pnk  = local_reg["PNKRegistry"]

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
    # Pass 2: assign PNKs (stable identity) and build path→PNK map
    # -------------------------------------------------------------------------
    path_to_pnk = {}
    pnk_report_lines = []

    for rec in records:
        node = rec["node"]
        path = rec["path"]

        name = node.attrib.get("name", "")
        path_str = compact_path(path)

        identity_min = {
            "name": name,
            "path": path_str,
        }

        serialized = json.dumps(identity_min, sort_keys=True)
        sha = hashlib.sha1(serialized.encode("utf-8")).hexdigest()
        pnk = sha[:4].upper()

        # Collision resolution
        i = 0
        while pnk in global_pnk and global_pnk[pnk].get("sha1") != sha:
            i += 1
            if i + 4 > len(sha):
                raise RuntimeError(f"PNK collision resolution failed for SHA {sha}")
            pnk = sha[i:i+4].upper()

        entry = {
            "name": name,
            "path": path_str,
            "sha1": sha,
        }

        global_pnk[pnk] = entry
        local_pnk[pnk]  = entry

        path_to_pnk[tuple(path)] = pnk
        pnk_report_lines.append(f"{pnk}  {name}  {path_str}")

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
        entry = global_pnk[this_pnk]
        entry["parent"] = parent_pnk
        entry["children"] = children_pnks

        local_pnk[this_pnk]["parent"]   = parent_pnk
        local_pnk[this_pnk]["children"] = children_pnks

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

# =============================================================================
# MENU / MAIN
# =============================================================================

def menu():
    while True:
        print("\n=== FS25 Unified Tool ===")
        print("1. Majik_mapper (FULL I3D)")
        print("2. Majik_mapper (XML-only)")
        print("3. Majik_mapper (XML-remap)")
        print("4. Majik_mapper (RAW dump)")
        print("5. Build PFKs")
        print("6. Build PMKs")
        print("7. Build PNKs (stub)")
        print("8. Material Sync")
        print("9. Exit")

        choice = input("Select option: ").strip()

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
            break
        else:
            print("Invalid option.")

if __name__ == "__main__":
    menu()
