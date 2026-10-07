#!/usr/bin/env python3
"""Render docs/QUICKSTART.md as a printable PDF (build/EPS249_NEXT_QuickStart.pdf).

  python3 tools/mkguide.py [OUT.pdf]

Needs the Python "markdown" package and Chromium (CHROME=path, default the
Playwright one in /opt/pw-browsers).
"""
import glob
import os
import subprocess
import sys
import tempfile

import markdown

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "docs", "QUICKSTART.md")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build", "EPS249_NEXT_QuickStart.pdf")

CSS = """
@page { size: Letter; margin: 16mm 16mm 18mm 16mm;
        @bottom-center { content: counter(page); } }
:root { --ink: #1d2126; --muted: #5b6470; --rule: #d5dae0; --accent: #2b5d8a;
        --tint: #f1f4f7; }
body { font-family: "DejaVu Sans", sans-serif; font-size: 9.6pt; line-height: 1.45;
       color: var(--ink); margin: 0; }
h1 { font-size: 19pt; margin: 0 0 4pt; color: var(--accent); letter-spacing: -0.2pt; }
h1 + p { color: var(--muted); margin-top: 0; }
h2 { font-size: 12.5pt; color: var(--accent); margin: 16pt 0 5pt; padding-bottom: 3pt;
     border-bottom: 1.2pt solid var(--accent); break-after: avoid; }
h2 + * { break-before: avoid; }
p, li { orphans: 3; widows: 3; }
ul, ol { padding-left: 16pt; margin: 4pt 0 6pt; }
li { margin: 2pt 0; }
li > ul { margin: 2pt 0; }
strong { color: #000; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.6pt; background: var(--tint);
       padding: 0.5pt 3pt; border-radius: 2pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 8pt; font-size: 9pt;
        break-inside: avoid; }
th { text-align: left; background: var(--accent); color: #fff; font-weight: 600;
     padding: 4pt 6pt; }
td { padding: 4pt 6pt; border-bottom: 0.6pt solid var(--rule); vertical-align: top; }
tr:nth-child(even) td { background: var(--tint); }
a { color: var(--accent); text-decoration: none; }
.section { break-inside: avoid-page; }
"""


def main():
    md = open(SRC, encoding="utf-8").read()
    body = markdown.markdown(md, extensions=["tables", "sane_lists"])
    html = (f"<!doctype html><html><head><meta charset='utf-8'><title>EPS Custom OS: Quick start"
            f"</title><style>{CSS}</style></head><body>{body}</body></html>")
    chrome = os.environ.get("CHROME") or sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))[-1]
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "guide.html")
        open(page, "w", encoding="utf-8").write(html)
        subprocess.run([chrome, "--headless", "--no-sandbox", "--disable-gpu",
                        "--no-pdf-header-footer", f"--print-to-pdf={os.path.abspath(OUT)}",
                        "file://" + page], check=True, capture_output=True)
    print(OUT)


if __name__ == "__main__":
    main()
