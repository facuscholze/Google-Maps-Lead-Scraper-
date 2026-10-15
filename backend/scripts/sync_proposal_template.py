"""Preserve the original brand email, untouched (Fase 8 / D8.5).

`nuevo html mail.html` (repo root) is the ONLY mail template source of truth.
This script copies it byte-identically into the backend package so Docker
builds ship the pristine reference next to the derived working template:

    nuevo html mail.html  →  backend/app/services/emailing/templates/email/innblock_original.html

It NEVER rewrites `templates/innblock.html`: that rendering template diverges
by design (dynamic slots {{apertura}}/{{firmaSocios}}, web-selling copy,
evidence-anchored sections — see email_html.py docstring + DECISIONS.md).

Run from any directory: python backend/scripts/sync_proposal_template.py
"""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[2]
source = root / "nuevo html mail.html"
target = root / "backend/app/services/emailing/templates/email/innblock_original.html"

if not source.is_file():
    raise SystemExit(f"Missing original template: {source}")

target.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source, target)  # byte-identical — "keep original intact"
print(f"Original preserved at {target}")
