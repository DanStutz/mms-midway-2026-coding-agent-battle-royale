"""Dependency-free pre-publication checks. Prints locations, never matched values."""
import argparse
import os
from pathlib import Path
import re
import sys

EXCLUDED_DIRS={'.git','.arena','work','auth','jobs','runs','materials','.venv','venv','node_modules','__pycache__','.pytest_cache'}
PATTERNS={
    'provider key or token':re.compile(r'\b(?:sk-(?:ant-[a-z0-9]+-|proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16})\b'),
    'JWT':re.compile(r'\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b'),
    'private key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'literal credential':re.compile(r'''(?i)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password)["']?\s*[:=]\s*["']([A-Za-z0-9_+/.=-]{24,})["']'''),
    'personal absolute path':re.compile(r'''(?i)(?:[a-z]:[\\/]+Users[\\/]+[^\\/\s"']+|/(?:Users|home)/[^/\s"']+)'''),
    'filled Azure resource URL':re.compile(r'https://(?!your-resource\.|example\.)[a-z0-9-]+\.(?:openai\.azure\.com|services\.ai\.azure\.com)(?:/[^\s"<>]*)?',re.I),
}

def scan(root):
    findings=[];count=0
    for directory,dirs,files in os.walk(root):
        dirs[:]=[d for d in dirs if d not in EXCLUDED_DIRS]
        for name in files:
            p=Path(directory)/name;relative=p.relative_to(root).as_posix()
            if p.is_symlink():
                findings.append((relative,0,'symbolic link requires manual review'));continue
            if name in ('auth.json','credentials.json') or name=='.env' or name.startswith('.env.') and name!='.env.example' or p.suffix.lower() in {'.pem','.key','.pfx','.p12','.zip'}:
                findings.append((relative,0,'credential file or archive requires exclusion'));continue
            try:
                if p.stat().st_size>20_000_000:
                    findings.append((relative,0,'large file requires manual review'));continue
                data=p.read_bytes()
                if b'\0' in data:
                    findings.append((relative,0,'binary file requires manual review'));continue
                text=data.decode('utf-8')
            except (OSError,UnicodeDecodeError):
                findings.append((relative,0,'unreadable source requires manual review'));continue
            count+=1
            for category,pattern in PATTERNS.items():
                for match in pattern.finditer(text):
                    findings.append((relative,text.count('\n',0,match.start())+1,category))
    return count,sorted(set(findings))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',nargs='?',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args();root=args.root.resolve()
    if not root.is_dir():parser.error('Choose an existing source directory.')
    count,findings=scan(root)
    for path,line,category in findings:print(f'{path}:{line}: {category}')
    if findings:
        print(f'REVIEW REQUIRED: {len(findings)} findings in {count} scanned text files. No matched values printed.')
        return 1
    print(f'PASS: no findings for the configured patterns in {count} text files. Ignored runtime/dependency directories and Git history were not scanned.')
    return 0

if __name__=='__main__':sys.exit(main())
