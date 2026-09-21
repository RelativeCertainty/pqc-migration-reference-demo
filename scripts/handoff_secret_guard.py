"""Metadata-only precommit guard; no secret values or matched text is emitted.

This limited guard is not a replacement for the destination's approved scanner.
It examines selected source/document bytes and XML members of Office files.
"""
from pathlib import Path
import json
import re
import subprocess
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    'private-key-material': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{80,}'),
    'github-token': re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,})\b'),
    'aws-access-key': re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'google-api-key': re.compile(rb'\bAIza[A-Za-z0-9_-]{35}\b'),
    'slack-token': re.compile(rb'\bxox[baprs]-[A-Za-z0-9-]{20,}\b'),
}

def main():
    files = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    findings = []
    for name in filter(None,files):
        path = ROOT/name
        if any(p in {'.env','node_modules','bin','obj','private-runtime','fixture-custody'} for p in path.relative_to(ROOT).parts) or path.suffix in {'.db','.key','.pfx','.p12'}:
            findings.append({'file':name,'rule':'forbidden-runtime-path'})
        chunks = [path.read_bytes()]
        if path.suffix in {'.xlsx','.docx','.pptx'}:
            with ZipFile(path) as archive:
                chunks += [archive.read(n) for n in archive.namelist() if n.endswith(('.xml','.rels'))]
        for rule, pattern in RULES.items():
            if any(pattern.search(data) for data in chunks):
                findings.append({'file':name,'rule':rule})
    print(json.dumps({'files':len(list(filter(None,files))),'findings':findings,
                      'scope':'limited token/key-pattern and forbidden-path guard; not comprehensive secret detection'}))
    return int(bool(findings))

if __name__ == '__main__':
    sys.exit(main())
