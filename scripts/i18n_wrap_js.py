#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrap Chinese strings in static JS files with gettext()."""
import argparse
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
JS_DIR = BASE_DIR / "static" / "js"
SKIP_FILES = {"i18n_wrap_js.py"}

HAS_CHINESE = re.compile(r"[\u4e00-\u9fff]")


def wrap_js(js_text):
    result = []
    i = 0
    n = len(js_text)
    while i < n:
        ch = js_text[i]
        # Comments
        if ch == "/" and i + 1 < n:
            if js_text[i + 1] == "/":
                end = js_text.find("\n", i)
                if end == -1:
                    end = n
                result.append(js_text[i:end])
                i = end
                continue
            if js_text[i + 1] == "*":
                end = js_text.find("*/", i)
                if end == -1:
                    end = n
                else:
                    end += 2
                result.append(js_text[i:end])
                i = end
                continue
        # Strings
        if ch in ('"', "'", "`"):
            quote = ch
            start = i
            i += 1
            buf = []
            while i < n:
                c = js_text[i]
                if c == "\\" and i + 1 < n:
                    buf.append(js_text[i:i+2])
                    i += 2
                    continue
                if c == quote:
                    i += 1
                    break
                buf.append(c)
                i += 1
            string = "".join(buf)
            original = js_text[start:i]
            if HAS_CHINESE.search(string) and not should_skip(js_text, start):
                result.append(wrap_one(string, quote))
            else:
                result.append(original)
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def should_skip(text, start):
    # Skip object keys: { 'key': ...
    j = start - 1
    while j >= 0 and text[j] in " \t\n\r":
        j -= 1
    if j >= 0 and text[j] in "{,":
        k = start + 1
        # skip the string itself
        while k < len(text) and text[k] != text[start]:
            if text[k] == "\\":
                k += 2
            else:
                k += 1
        k += 1
        while k < len(text) and text[k] in " \t\n\r":
            k += 1
        if k < len(text) and text[k] == ":":
            return True
    # Skip case labels
    before = text[max(0, start - 50):start]
    if re.search(r"\bcase\s+$", before):
        return True
    # Skip ===/== comparisons
    if re.search(r"==?\s+$", before):
        return True
    return False


def wrap_one(string, quote):
    if quote == "`":
        parts = re.split(r"(\$\{[^}]*\})", string)
        out = []
        for part in parts:
            if re.match(r"\$\{.*\}", part):
                inner = part[2:-1]
                out.append(f" + ({inner}) + ")
            elif HAS_CHINESE.search(part):
                esc = part.replace("\\", "\\\\").replace("'", "\\'")
                out.append(f"gettext('{esc}')")
            elif part:
                out.append(f"'{part.replace('\\', '\\\\').replace(chr(39), '\\\\' + chr(39))}'")
        s = "".join(out)
        s = re.sub(r"^\s*\+\s*|\s*\+\s*$", "", s)
        s = re.sub(r"\+\s*\+", "+", s)
        return s
    else:
        esc = string.replace("\\", "\\\\").replace("'", "\\'")
        return f"gettext('{esc}')"


def process_file(path, dry_run=False):
    content = path.read_text(encoding="utf-8")
    wrapped = wrap_js(content)
    changed = wrapped != content
    if changed and not dry_run:
        path.write_text(wrapped, encoding="utf-8")
    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    changed = []
    for root, dirs, files in os.walk(JS_DIR):
        dirs[:] = [d for d in dirs if d not in {"node_modules", "vendor"}]
        for name in files:
            if not name.endswith(".js") or name in SKIP_FILES:
                continue
            path = Path(root) / name
            if process_file(path, dry_run=args.dry_run):
                changed.append(str(path.relative_to(BASE_DIR)))

    print(f"Changed JS files: {len(changed)}")
    for f in changed:
        print(f"  {f}")


if __name__ == "__main__":
    main()
