#!/usr/bin/env python3
"""Count lines of code in the repository.

Usage: python tools/count_lines.py [path]

This script walks the given path (current directory by default), skips
common binary and VCS directories, and counts non-empty lines per file
grouped by file extension and by language (guess from extension).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

# Map common extensions to language names
EXT_LANG = {
    '.py': 'Python',
    '.js': 'JavaScript',
    '.ts': 'TypeScript',
    '.java': 'Java',
    '.c': 'C',
    '.cpp': 'C++',
    '.cc': 'C++',
    '.cxx': 'C++',
    '.h': 'C/C++ Header',
    '.hpp': 'C++ Header',
    '.cs': 'C#',
    '.go': 'Go',
    '.rb': 'Ruby',
    '.php': 'PHP',
    '.html': 'HTML',
    '.htm': 'HTML',
    '.css': 'CSS',
    '.scss': 'SCSS',
    '.md': 'Markdown',
    '.json': 'JSON',
    '.xml': 'XML',
    '.yml': 'YAML',
    '.yaml': 'YAML',
    '.sh': 'Shell',
    '.ps1': 'PowerShell',
    '.bat': 'Batch',
    '.rs': 'Rust',
    '.swift': 'Swift',
    '.kt': 'Kotlin',
    '.kts': 'Kotlin',
    '.gradle': 'Groovy',
    '.make': 'Makefile',
    'Makefile': 'Makefile',
    '.Dockerfile': 'Dockerfile',
    '.dockerfile': 'Dockerfile',
    '.sql': 'SQL',
    '.ipynb': 'Jupyter Notebook',
}

# Directories to skip
SKIP_DIRS = {
    '.git', '.hg', '.svn', '__pycache__', 'node_modules', 'venv', 'env', '.venv', '.aws-sam', 'dist', 'build', '.idea', '.vscode', '.tox', '.pytest_cache', 'site-packages', 'bin', 'obj', 'target', '.gradle', '.pytest_cache'
}

# File names (without extension) to treat specially
SPECIAL_FILES = {
    'Dockerfile': 'Dockerfile',
    'Makefile': 'Makefile',
}


def is_binary_file(path: Path) -> bool:
    """Quick check whether a file is binary by reading initial bytes."""
    try:
        with path.open('rb') as f:
            chunk = f.read(1024)
            if b"\0" in chunk:
                return True
    except Exception:
        return True
    return False


def iter_code_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        # filter dirnames in-place to avoid walking into them
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith('.')]
        for name in filenames:
            # skip hidden files
            if name.startswith('.'):
                continue
            p = Path(dirpath) / name
            yield p


def count_lines_in_file(path: Path) -> Tuple[int, int]:
    """Return (total_lines, non_empty_lines) for a file."""
    try:
        # treat notebook separately later (we'll approximate by counting cells)
        if path.suffix == '.ipynb':
            # count lines by treating as text
            text = path.read_text(encoding='utf-8', errors='ignore')
            total = text.count('\n') + 1 if text else 0
            non_empty = sum(1 for line in text.splitlines() if line.strip())
            return total, non_empty

        if is_binary_file(path):
            return 0, 0

        with path.open('r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception:
        return 0, 0

    total = len(lines)
    non_empty = sum(1 for line in lines if line.strip())
    return total, non_empty


def detect_lang(path: Path) -> str:
    name = path.name
    if name in SPECIAL_FILES:
        return SPECIAL_FILES[name]
    ext = path.suffix.lower()
    if ext in EXT_LANG:
        return EXT_LANG[ext]
    # fallback: use extension as language
    if ext:
        return ext.lstrip('.')
    return 'Unknown'


def format_int(n: int) -> str:
    return f"{n:,}"


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Count lines of code in a project')
    parser.add_argument('path', nargs='?', default='.', help='Root path to scan')
    parser.add_argument('--include-empty', action='store_true', help='Count empty lines as code')
    parser.add_argument('--show-top', type=int, default=20, help='Show top N languages')
    args = parser.parse_args(argv)

    root = Path(args.path)
    if not root.exists():
        print('Path does not exist:', root)
        return 2

    per_lang: Dict[str, Dict[str, int]] = defaultdict(lambda: {'files': 0, 'lines': 0, 'non_empty': 0})
    total_files = 0
    total_lines = 0
    total_non_empty = 0

    for path in iter_code_files(root):
        total, non_empty = count_lines_in_file(path)
        if total == 0:
            continue
        lang = detect_lang(path)
        per_lang[lang]['files'] += 1
        per_lang[lang]['lines'] += total
        per_lang[lang]['non_empty'] += non_empty
        total_files += 1
        total_lines += total
        total_non_empty += non_empty

    print('\nScan root:', root)
    print('Files counted:', total_files)
    print('Total lines:', format_int(total_lines))
    print('Total non-empty lines:', format_int(total_non_empty))

    print('\nBy language:')
    # sort by lines desc
    items = sorted(per_lang.items(), key=lambda kv: kv[1]['lines'], reverse=True)
    for lang, data in items[: args.show_top]:
        lines = data['lines']
        non_empty = data['non_empty']
        print(f"- {lang}: {format_int(lines)} lines ({format_int(non_empty)} non-empty) in {data['files']} files")

    if len(items) > args.show_top:
        others = sum(d['lines'] for _, d in items[args.show_top:])
        print(f"- Other: {format_int(others)} lines")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
