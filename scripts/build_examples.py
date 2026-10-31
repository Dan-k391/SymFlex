"""Build public/examples.json (the "Course examples" browser) from corpus/cases.

Falls back to corpus/raw for sources that have no cleaned cases yet. Output:
[{"source", "title", "items": [{"id", "title", "context", "kind": "mpl"|"pde", "code"}]}]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES, RAW = ROOT / "corpus" / "cases", ROOT / "corpus" / "raw"
OUT = ROOT / "public" / "examples.json"

# Corpus bookkeeping headers that are not useful to students.
HEADER = re.compile(r"^\s*(#|\{)\s*(SOURCE|DEPENDS|NOTE|EXPECT\w*|SKIP\w*)\s*:(.*?)\}?\s*$", re.I)


TOPICS = {"kinematics": "Kinematics", "nonlinear": "Nonlinear ODEs", "damped": "Damped & driven oscillators",
          "rigidbody": "Rigid body kinetics", "energy_lagrange": "Energy & Lagrange"}


def group_title(source: str) -> str:
    m = re.fullmatch(r"lab(\d+)", source)
    if m:
        return f"Lab {m[1]}"
    m = re.fullmatch(r"notes(\d+)_(.*)", source)
    if m:
        return f"Notes {m[1]}: {TOPICS.get(m[2], m[2].replace('_', ' ').title())}"
    return source


def natural_key(s: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def split_header(text: str):
    """Strip leading corpus header lines; return (code, source_description)."""
    lines = text.replace("\r\n", "\n").split("\n")
    desc = ""
    while lines and (m := HEADER.match(lines[0])):
        if m[2].upper() == "SOURCE":
            desc = m[3].strip()
        lines.pop(0)
    return "\n".join(lines).strip() + "\n", desc


def title_from(desc: str, stem: str) -> str:
    # "lab1 block 10 (para 313) - fsolve for when T2 first passes 5 kN" -> "fsolve for when ..."
    t = desc.split(" - ", 1)[1] if " - " in desc else ""
    t = t.strip().rstrip(":. ").strip("() ").strip()
    if len(t) > 90:
        t = t[:87].rsplit(" ", 1)[0] + "..."
    num = re.search(r"(\d+|img\d+)$", stem)
    label = f"#{num[1]}" if num else stem
    return f"{label} {t}".strip() if t else f"Example {label}"


def build():
    raw_index = {}
    if (RAW / "index.json").exists():
        for e in json.loads((RAW / "index.json").read_text(encoding="utf-8")):
            raw_index[e["id"]] = e
    sources = sorted({p.name for d in (CASES, RAW) if d.exists() for p in d.iterdir() if p.is_dir()}, key=natural_key)
    groups = []
    for source in sources:
        files = sorted((CASES / source).glob("*.mpl")) + sorted((CASES / source).glob("*.pde")) if (CASES / source).exists() else []
        from_raw = not files
        if from_raw:
            files = sorted((RAW / source).glob("*.mpl")) + sorted((RAW / source).glob("*.pde"))
        items = []
        for f in sorted(files, key=lambda p: natural_key(p.stem)):
            code, desc = split_header(f.read_text(encoding="utf-8", errors="replace"))
            if not code.strip():
                continue
            nn = f.stem.split("_")[-1] if not from_raw else f.stem
            raw = raw_index.get(f"{source}/{nn}{f.suffix}", {})
            context = (raw.get("context") or "").strip()
            items.append({
                "id": f"{source}/{f.stem}",
                "title": title_from(desc or f"x - {context}", f.stem),
                "context": context,
                "kind": f.suffix[1:],
                "code": code,
            })
        if items:
            groups.append({"source": source, "title": group_title(source), "items": items})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(groups, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"build_examples: {sum(len(g['items']) for g in groups)} examples in {len(groups)} groups -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(build())
