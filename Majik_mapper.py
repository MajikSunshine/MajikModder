import xml.etree.ElementTree as ET
import os
import sys
import argparse
import json
from collections import defaultdict


# -------------------------
# Config handling
# -------------------------

DEFAULT_CONFIG = {
    "exclude_if_contains": ["/", "\\", ">", "|", " ", "<", "=", ":"],
    "exclude_if_tag": ["i3dMapping", "l10n"],
    "exclude_if_attr": ["name", "title", "colorScale"],
    "max_length": 64
}


def load_config(config_path="config.json"):
    """
    Load filters from config.json if present.
    Fall back to DEFAULT_CONFIG if missing or invalid.
    """
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


# -------------------------
# Core I3D mapping logic
# -------------------------

def walk(node, path, results):
    """Walk the I3D tree and collect (name, path_list)."""
    name = node.attrib.get("name")
    if name:
        results.append((name, list(path)))

    children = list(node)
    for i, child in enumerate(children):
        walk(child, path + [i], results)

def compact_path(path):
    """
    Convert a list like [0,1,7,3] into GIANTS compact style:
    [0]       -> "0>"
    [0,0]     -> "0>0"
    [0,6,0,0] -> "0>6|0|0"
    [1]       -> "1>"
    [1,2]     -> "1>2"
    """
    if not path:
        # Shouldn't normally happen if we always start with a component index,
        # but keep a safe default.
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

    # Each direct child of <Scene> is a "component root":
    # component 0 -> 0>
    # component 1 -> 1>
    for comp_index, child in enumerate(list(scene)):
        walk(child, [comp_index], results)

    return results  # list of (name, path_list)

def build_name_index(mappings):
    """
    Build name -> list[path_list] index from full mappings.
    """
    index = defaultdict(list)
    for name, path in mappings:
        index[name].append(path)
    return index


def autodetect_file(ext):
    candidates = [f for f in os.listdir('.') if f.lower().endswith(ext)]
    if not candidates:
        return None
    return candidates[0]

def run_raw_i3d_mode(i3d_file, output_file):
    """
    Raw I3D dump:
    - Walk the I3D tree
    - Write each mapping in DFS order
    - No grouping, no duplicate detection, no warnings
    """
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

        # Each direct child of <Scene> is a component root
        for comp_index, child in enumerate(list(scene)):
            raw_walk(child, [comp_index])

    print(f"Done. Mode=RAW_I3D. Output written to {output_file}")

# -------------------------
# XML helpers (config-driven)
# -------------------------

def extract_xml_names_xml_only(xml_file, config):
    """
    XML-only mode:
    - Parse XML
    - Ignore any <i3dMapping> elements entirely (from config.exclude_if_tag)
    - Collect attribute values from other elements
    - Filter using config rules
    """
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

            # Contains any excluded character?
            if any(ch in val for ch in exclude_if_contains):
                continue

            names.add(val)

    return names


def extract_ids_from_i3d_mappings(xml_file):
    """
    XML-remap mode:
    - Parse XML
    - Collect all id="..." from <i3dMapping> elements
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()

    ids = []
    for elem in root.iter("i3dMapping"):
        id_val = elem.attrib.get("id")
        if id_val:
            ids.append(id_val)
    return ids


# -------------------------
# Output
# -------------------------

def write_output(output_file, selected_name_to_paths, mode_label):
    """
    Write mappings and duplicate warnings using compact paths.
    selected_name_to_paths: dict name -> list[path_list]
    """
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


# -------------------------
# Main
# -------------------------

def main():
    parser = argparse.ArgumentParser(description="GIANTS I3D mapping generator (compact paths, multi-mode, config-driven).")
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

    args = parser.parse_args()

    mode_xml_only = args.xml_only is not None
    mode_remap = args.remap is not None

    if mode_xml_only and mode_remap:
        print("Error: --xml-only and --remap cannot be used together.")
        sys.exit(1)

    # Load config
    config_path = args.config if args.config else "config.json"
    config = load_config(config_path)
    print(f"Using config: {config_path if os.path.exists(config_path) else 'built-in defaults'}")

    # Auto-detect I3D if not provided
    if args.i3d:
        i3d_file = args.i3d
    else:
        i3d_file = autodetect_file(".i3d")
        if not i3d_file:
            print("Error: No .i3d files found in this directory.")
            sys.exit(1)
        print(f"Auto-detected .i3d file: {i3d_file}")

    # Auto-detect XML if needed
    xml_file = None
    if mode_xml_only:
        if isinstance(args.xml_only, str):
            xml_file = args.xml_only
        else:
            xml_file = autodetect_file(".xml")
        if not xml_file:
            print("Error: XML-only mode requested but no .xml file specified or found.")
            sys.exit(1)
        print(f"XML-only mode using XML file: {xml_file}")

    if mode_remap:
        if isinstance(args.remap, str):
            xml_file = args.remap
        else:
            xml_file = autodetect_file(".xml")
        if not xml_file:
            print("Error: XML-remap mode requested but no .xml file specified or found.")
            sys.exit(1)
        print(f"XML-remap mode using XML file: {xml_file}")

    output_file = args.output if args.output else "i3d_mappings.xml"

    if args.raw_i3d:
        run_raw_i3d_mode(i3d_file, output_file)
        return
    
    # Build full mapping index from I3D
    all_mappings = generate_all_mappings(i3d_file)
    name_index = build_name_index(all_mappings)

    selected_name_to_paths = {}

    if not mode_xml_only and not mode_remap:
        # Mode 1: full I3D mapping
        for name, paths in name_index.items():
            selected_name_to_paths[name] = paths
        mode_label = "FULL_I3D"

    elif mode_xml_only:
        # Mode 2: XML-only (config-driven filters)
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
        # Mode 3: XML-remap
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


if __name__ == "__main__":
    main()