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
    identity = {
        "shader": None,
        "parameters": {},
        "textures": {}
    }

    for attr, val in material_node.attrib.items():
        if attr in ("materialId", "name"):
            continue
        if attr == "customShaderId":
            identity["shader"] = pfk_lookup(val)
            continue
        identity["parameters"][attr] = normalize_value(val)

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
            identity["textures"][slot] = pfk
            continue

        if "value" in child.attrib:
            name = child.attrib.get("name")
            if name:
                identity["parameters"][name] = normalize_value(child.attrib["value"])
            continue

    if identity["shader"] is None:
        identity["shader"] = "NO_SHADER"

    return identity

def hash_pmk(identity_blob):
    serialized = json.dumps(identity_blob, sort_keys=True)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()[:4].upper()

def build_pmk_entry(material_node, identity_blob, pmk_hash):
    return {
        "PMK": pmk_hash,
        "shader": identity_blob["shader"],
        "parameters": identity_blob["parameters"],
        "textures": identity_blob["textures"],
        "materialName": material_node.attrib.get("name", "UNKNOWN")
    }

def process_material(material_node, pfk_lookup):
    identity = build_pmk_identity(material_node, pfk_lookup)
    pmk_hash = hash_pmk(identity)
    entry = build_pmk_entry(material_node, identity, pmk_hash)
    return pmk_hash, entry
