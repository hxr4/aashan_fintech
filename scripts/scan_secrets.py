"""Fail the build when a credential-shaped string appears in tracked source."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "reference", "consumables", ".pytest_cache"}
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".pdf", ".woff2", ".ico", ".db", ".xlsx"}

PATTERNS = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("jwt_like", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("supabase_service_key", re.compile(r"sb_secret_[A-Za-z0-9_-]{20,}")),
    ("slack_token", re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}")),
    # Env-file syntax only: uppercase key, no spaces around '=', credential-shaped value.
    # Deliberately case-sensitive so ordinary Python like `token_payload = response.json()`
    # is not mistaken for a secret.
    ("env_style_assignment", re.compile(
        r"^[A-Z][A-Z0-9_]*(SECRET|PASSWORD|API_KEY|APIKEY|TOKEN|SERVICE_ROLE|PRIVATE_KEY)[A-Z0-9_]*"
        r"=[A-Za-z0-9_\-/+=.]{12,}$"
    )),
    ("generic_assignment", re.compile(
        r"(?i)\b(client_secret|api_key|apikey|secret_key|service_role_key|password|passwd|token)\b"
        r"\s*[:=]\s*[\"'][A-Za-z0-9_\-/+=]{16,}[\"']"
    )),
]

# Values that are obviously not credentials. A real secret does not announce
# itself as a fixture, and every test constant in this repo is prefixed so the
# guard stays meaningful rather than being switched off per file.
ALLOW = re.compile(
    r"(?i)(your[-_ ]?|example|placeholder|changeme|dummy|xxx+|\.\.\.|<[a-z_]+>|os\.getenv|settings\.|"
    r"getenv\(|redacted|\btest-[a-z0-9-]*(secret|token|key)|(secret|token|key)[-_]?test\b|"
    r"fake[-_]?|sample[-_]?|part-2-test-secret)"
)


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
        names = [n for n in out.split("\0") if n]
        return [ROOT / n for n in names]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [p for p in ROOT.rglob("*") if p.is_file()]


def scan() -> int:
    findings: list[str] = []
    for path in tracked_files():
        if not path.is_file():
            continue
        if set(path.relative_to(ROOT).parts) & SKIP_DIRS or path.suffix.lower() in SKIP_SUFFIX:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if ALLOW.search(line):
                continue
            for label, pattern in PATTERNS:
                if pattern.search(line):
                    findings.append(f"{path.relative_to(ROOT)}:{number}: possible {label}")
    for finding in findings:
        print(finding, file=sys.stderr)
    if findings:
        print(f"\n{len(findings)} possible secret(s) in tracked files.", file=sys.stderr)
        return 1
    print("secret scan clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(scan())
