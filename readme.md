# **Majik_mapper**
### *Deterministic. Forensic. Future‑proof.*
A next‑generation I3D node‑mapping tool for Farming Simulator modders.  
Created by **[MajikSunshine](https://github.com/MajikSunshine)**.

---

## ⭐ Overview
**Majik_mapper** is a compact‑path, config‑driven, multi‑mode mapping engine designed to eliminate the pain of maintaining `<i3dMapping>` sections in Farming Simulator mods.
It walks your `.i3d` scene tree deterministically and outputs clean, compact GIANTS‑style node paths — with zero guesswork, zero drift, and zero surprises.
This is the mapper GIANTS *should* have shipped.

---

## 🚀 Features

### **✔ Always outputs compact GIANTS paths**
No debug format. No exceptions.  
Every path looks like:
0>10|0|0|0|0|5|0

### **✔ Three operational modes**

#### **1. Full I3D Mapping (default)**
Maps *every* named node in the `.i3d`.  
Perfect for audits, debugging, and forensic analysis.
python Majik_mapper.py truck.i3d

#### **2. XML‑Only Mode (`--xml-only`)**
Maps only the node names referenced in your XML **outside** of existing `<i3dMapping>` entries.
python Majik_mapper.py --xml-only vehicle.xml
Ideal for generating mappings for new systems without touching existing ones.

#### **3. XML‑Remap Mode (`--remap`)**
Reads your existing `<i3dMappings>` block and regenerates *only those* mappings.
python Majik_mapper.py --remap vehicle.xml
This is the “I moved stuff in GE — update my mappings” button.

---

## 🧠 Config‑Driven Filters (`config.json`)
Majik_mapper uses a simple JSON config file to control how XML‑only mode filters attribute values:
```json
{
  "exclude_if_contains": ["/", "\\", ">", "|", " ", "<", "=", ":"],
  "exclude_if_tag": ["i3dMapping", "l10n"],
  "exclude_if_attr": ["name", "title", "colorScale"],
  "max_length": 64
}
```

Why this matters
Filters evolve without touching the script
Future FS versions won’t break the tool
Modders can tune strictness
You can ship filter packs for different workflows
If config.json is missing or invalid, Majik_mapper falls back to safe defaults.
⚠ Duplicate Detection
If a node name appears multiple times in the I3D, Majik_mapper reports it:
<!-- "hydraulicRod" appears 3 times: -->
<!--     0>10|0|3|1 -->
<!--     0>10|0|3|4 -->
<!--     0>10|0|3|7 -->
Sorted by rarity so the weird ones surface first.

📦 Output
All modes write to:
i3d_mappings.xml
Unless overridden with:
-o my_output.xml

🛠 Requirements
Python 3.8+
A .i3d file
Optional: an XML file containing <i3dMappings> or node references
Optional: config.json for custom filters

🧩 Why Majik_mapper Exists
Because FS modders deserve a tool that:
never overwrites your work
never guesses
never hides evidence
never produces unstable paths
never forces you to hand‑edit 1,000 lines of mappings again
Majik_mapper is deterministic, forensic, and built for long‑term survival across FS25, FS26, FS27, and beyond.

🧙‍♂️ Author
Created by MajikSunshineGitHub: https://github.com/MajikSunshine
If you fork, modify, or extend this tool, please credit the original author — this mapper is part of FS modding history now.

📜 License
This project is licensed under the Apache License 2.0.
You may obtain a copy of the License at:
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
