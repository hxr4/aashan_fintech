from pathlib import Path
import re
import subprocess

inventory = Path('/tmp/manus-mcp/mcp_result_9168b15a-b2bf-4aa3-a512-966acaa1599a.json').read_text(encoding='utf-8')
out_dir = Path('/home/ubuntu/review_sources/referenced')
out_dir.mkdir(parents=True, exist_ok=True)
for match in re.finditer(r'- ([^\n]+?) \[(?:file|image)\] download: (https://[^\n]+)', inventory):
    name = match.group(1).strip().split(' (title:', 1)[0]
    url = match.group(2).strip()
    if not name.endswith(('.md', '.txt', '.docx')):
        continue
    destination = out_dir / name
    subprocess.run(['curl', '-L', '--fail', '--silent', '--show-error', url, '-o', str(destination)], check=True)
    print(destination)
