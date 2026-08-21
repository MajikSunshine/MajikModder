import re

OLD_FILE = "old.i3d"
NEW_FILE = "new.i3d"
OUT_FILE = "patched.i3d"


def extract_alpha_core(name: str) -> str:
    """
    Extract substring between first and last alphabetic characters.
    Returns "" if no alphabetic characters exist.
    """
    positions = [i for i, c in enumerate(name) if c.isalpha()]
    if not positions:
        return ""
    return name[positions[0]:positions[-1] + 1]


def build_material_map(old_path: str) -> dict:
    """
    Scan old.i3d, build:
        core_name -> materialIds string
    Only looks at <Shape ...> lines.
    """
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
    """
    Read new.i3d, write patched.i3d.
    Only modifies materialIds on <Shape ...> lines inside <Scene>.
    """
    shape_re = re.compile(r'<Shape\b[^>]*>')
    name_re = re.compile(r'name="([^"]+)"')
    mat_re = re.compile(r'materialIds="([^"]*)"')

    in_scene = False

    with open(new_path, "r", encoding="utf-8") as fin, \
         open(out_path, "w", encoding="utf-8") as fout:

        for line in fin:
            stripped = line.lstrip()

            # Track whether we're inside <Scene> ... </Scene>
            if "<Scene" in stripped:
                in_scene = True
            if "</Scene" in stripped:
                in_scene = False

            # Only touch <Shape> lines inside <Scene>
            if in_scene and "<Shape" in stripped and shape_re.search(stripped):
                name_match = name_re.search(stripped)
                if name_match:
                    raw_name = name_match.group(1)
                    core = extract_alpha_core(raw_name)

                    if core and core in materials_by_core:
                        old_mat_ids = materials_by_core[core]

                        # If materialIds exists, replace its value
                        if mat_re.search(stripped):
                            def repl(m):
                                return f'materialIds="{old_mat_ids}"'
                            stripped = mat_re.sub(repl, stripped)
                            # Rebuild line with original leading whitespace
                            line = line[:len(line) - len(line.lstrip())] + stripped

            fout.write(line)


def main():
    print("Building material map from", OLD_FILE)
    materials_by_core = build_material_map(OLD_FILE)
    print(f"Found {len(materials_by_core)} shape material mappings.")

    print("Patching", NEW_FILE, "->", OUT_FILE)
    patch_new_file(NEW_FILE, OUT_FILE, materials_by_core)

    print("Done. Output written to", OUT_FILE)


if __name__ == "__main__":
    main()
