"""Regenerate printer_cases.json from printer_cases.txt using the real cmaple (dev tool).

Each line of printer_cases.txt is one Maple statement; all run in one session, in order.
"""
import json
import pathlib
import subprocess

HERE = pathlib.Path(__file__).parent
CMAPLE = "D:/Maple/Installed/bin.X86_64_WINDOWS/cmaple.exe"
SEP = "@@@"

cases = [l.rstrip("\n") for l in (HERE / "printer_cases.txt").read_text().splitlines() if l.strip()]
src = "interface(prettyprint=0, screenwidth=infinity):\n" + "".join(
    f'{c};\nprintf("{SEP}\\n");\n' for c in cases)
work = HERE.parent / "out"
work.mkdir(exist_ok=True)
(work / "printer_cases.mpl").write_text(src)
out = subprocess.run([CMAPLE, "-q", str(work / "printer_cases.mpl")], capture_output=True,
                     text=True, timeout=300).stdout
chunks = out.split(SEP + "\n")
pairs = [[c, ch.strip()] for c, ch in zip(cases, chunks)]
(HERE / "printer_cases.json").write_text(json.dumps(pairs, indent=1))
print(f"{len(pairs)} cases written")
