"""Extract the mail (not the JS editor) for standalone backend deployments.

Run from any directory: python backend/scripts/sync_proposal_template.py
"""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
source = (root / "nuevo html innblock.html").read_text(encoding="utf-8")
match = re.search(r'<script type="text/plain" id="plantilla">\s*(.*?)\s*</script>', source, re.S)
if not match:
    raise SystemExit("Missing Innblock email template")
target = root / "backend/app/services/emailing/templates/innblock.html"
target.write_text(match[1] + "\n", encoding="utf-8")
print(f"Updated {target}")
