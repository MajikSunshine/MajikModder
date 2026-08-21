# MajikModder

---

# **MajikModder – FS25 Modding Toolkit**

A unified, developer‑grade toolkit for **Farming Simulator 25** mod creators. MajikModder combines the original **Majik_mapper** system with a full suite of material indexing, fingerprinting, node synchronization, and I3D repair utilities. The goal is simple: **make FS25 mod building faster, safer, and repeatable**, without the usual manual XML digging or error‑prone I3D editing.

---

## **What MajikModder Actually Does**

### **1. Maps and analyzes I3D files**
MajikModder can read, traverse, and summarize I3D structures, giving you a human‑friendly view of shapes, materials, nodes, and file references. This eliminates guesswork when diagnosing broken materials, missing textures, or mismatched node paths.

### **2. Builds material fingerprints (PFK/PMK)**
The toolkit generates unique fingerprints for materials across your mod and the GIANTS data folder. This lets you:

- detect duplicate materials  
- identify reused assets  
- track down mismatched or missing textures  
- build consistent material libraries for large mods  

It’s essentially a **material indexing system** for FS25.

### **3. Syncs materials between I3D files**
MajikModder can compare two I3D files and automatically copy or patch material definitions. This is ideal when:

- updating older mods  
- porting assets  
- repairing broken materials  
- merging multiple I3D sources  

It replaces hours of manual XML editing with a single automated pass.

### **4. Repairs common I3D issues**
The toolkit includes utilities to fix:

- broken `<Files filename="...">` entries  
- mismatched material paths  
- inconsistent node names  
- missing texture references  
- duplicated file entries  

These tools help stabilize mods that have been edited across Blender, GE, and external pipelines.

### **5. Scans GIANTS data for global references**
MajikModder can crawl the entire FS25 `data` directory to build a global fingerprint map. This allows your mod to:

- identify GIANTS‑provided materials  
- avoid collisions  
- reuse official assets safely  
- detect when a mod accidentally duplicates GIANTS content  

This is especially useful for large vehicle or map projects.

### **6. Provides structured utilities for mod building**
The toolkit includes workflow helpers for:

- node synchronization  
- material renaming  
- global dupe detection  
- raw I3D dumps  
- human‑readable summaries  
- automated mod‑building pipelines  

These utilities make MajikModder more than a script collection — it’s a **repeatable modding framework**.

---

## **Why This Exists**

FS25 modding involves a messy combination of:

- Blender exports  
- GE edits  
- XML patches  
- material inconsistencies  
- duplicated assets  
- broken I3D references  
- manual debugging  

MajikModder consolidates all the scattered tools into one unified system that:

- reads  
- analyzes  
- fingerprints  
- repairs  
- syncs  
- and builds  

your mod assets with consistency.

It’s designed for modders who want **automation**, **repeatability**, and **clarity** in their workflow.

---

## **Included Components**

- **Material Sync** – copy/patch materials between I3Ds  
- **PFK/PMK Builders** – material fingerprinting  
- **PNK Tools** – naming and material organization  
- **Node Sync** – structural alignment between I3Ds  
- **GIANTS Data Scanner** – global material fingerprint map  
- **I3D Repair Tools** – fix broken file references and paths  
- **Dupe Checkers** – detect duplicate materials and files  
- **Human‑Readable I3D Summary** – quick debugging view
- **Majik_mapper** – I3D mapping and analysis  

---

Majik_mapper (Integrated Component)
Deterministic. Forensic. Future‑proof.
Majik_mapper is the backbone of MajikModder’s I3D intelligence. It automatically rebuilds the <i3dMappings> section of any FS25 mod by walking the entire I3D scene tree and generating compact, stable GIANTS‑style node paths. This replaces hours of manual XML editing every time a modder moves, renames, or restructures objects in GE or Blender.

Inside MajikModder, Majik_mapper provides:
- Automatic mapping regeneration whenever your I3D changes
- Forensic‑grade node discovery for debugging broken mods
- Config‑driven filtering for XML‑only workflows
- Raw I3D dumps for deep inspection
- Deterministic output that never drifts or guesses

Majik_mapper ensures your mod’s XML always matches your I3D — no hand‑editing, no drift, no surprises. It’s the foundation that makes the rest of MajikModder’s material, node, and fingerprint systems reliable.  

---

## **Status**

Actively developed.  
Actively merged.  
Actively used for FS25 mod building.

---

