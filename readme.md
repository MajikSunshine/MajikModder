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

## 🧩 Why Majik_mapper Exists
Because FS modders deserve a tool that:

- never overwrites your work  
- never guesses  
- never hides evidence  
- never produces unstable paths  
- never forces you to hand‑edit 1,000+ mappings again  

Majik_mapper is deterministic, forensic, and built for long‑term survival across FS25, FS26, FS27, and beyond.

---

## 🧙‍♂️ Author
Created by **[MajikSunshine](https://github.com/MajikSunshine)**  
If you fork, modify, or extend this tool, please credit the original author — this mapper is part of FS modding history now.

---

## 📜 License
This project is licensed under the Apache License 2.0.  
You may obtain a copy of the License at:  
[http://www.apache.org/licenses/LICENSE-2.0](http://www.apache.org/licenses/LICENSE-2.0)

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  
See the License for the specific language governing permissions and limitations under the License.

---

## 🔧 Command‑Line Options (Complete)

```
i3d                 Optional .i3d file path (auto-detected if omitted)
--xml-only [XML]    XML-only mode (optional XML path, auto-detected if omitted)
--remap [XML]       XML-remap mode (optional XML path, auto-detected if omitted)
--raw-i3d           Raw I3D dump mode (DFS, no grouping)
-o, --output FILE   Output filename (default: i3d_mappings.xml)
--config FILE       Custom config.json (default: ./config.json)
```

**Mutual exclusion:**  
`--xml-only` and `--remap` cannot be used together.

**Auto‑detection:**  
- If no `.i3d` is provided, the first `.i3d` in the directory is used.  
- In XML‑only or remap mode, if no XML path is provided, the first `.xml` in the directory is used.
```