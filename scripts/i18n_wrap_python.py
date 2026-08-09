#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrap Chinese strings in Python code with gettext/gettext_lazy via token positions."""
import argparse
import io
import os
import re
import tokenize
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIRS = [BASE_DIR / "clubs", BASE_DIR / "CManager"]
SKIP_DIRS = {"migrations", "tests", "venv", "__pycache__", "static", "templates", "locale"}
SKIP_FILES = {"i18n_extra.py", "i18n_wrap_python.py", "i18n_wrap_templates.py"}

HAS_CHINESE = re.compile(r"[\u4e00-\u9fff]")


def get_string_value(token_string):
    try:
        value = eval(token_string)
    except Exception:
        return None
    if isinstance(value, bytes):
        return None
    return value


def wrap_literal(token_string, wrapper):
    value = get_string_value(token_string)
    if value is None:
        return token_string
    if "'" in value:
        quote = '"'
        escaped = value.replace('"', '\\"')
    else:
        quote = "'"
        escaped = value
    prefix = ""
    lower = token_string.lower()
    if lower.startswith(("rb", "br", "ur")):
        prefix = token_string[:2].lower()
    elif lower.startswith(("r", "u", "b", "f")):
        prefix = token_string[0].lower()
    return f"{wrapper}({prefix}{quote}{escaped}{quote})"


def _contains_sequence(strings, seq):
    if not seq:
        return False
    for i in range(len(strings) - len(seq) + 1):
        if strings[i:i + len(seq)] == list(seq):
            return True
    return False


def detect_context(tokens, idx):
    meaningful = []
    j = idx - 1
    while j >= 0 and len(meaningful) < 12:
        tok = tokens[j]
        if tok.type in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT, tokenize.ENDMARKER, tokenize.ENCODING):
            j -= 1
            continue
        meaningful.insert(0, tok)
        j -= 1

    strings = [t.string for t in meaningful]

    # Already translated: never wrap gettext/gettext_lazy calls again.
    if len(strings) >= 2 and strings[-1] == "(" and strings[-2] in {
        "_", "gettext", "gettext_lazy", "gettext_noop", "ngettext", "pgettext",
    }:
        return None

    if (_contains_sequence(strings, ("messages", ".", "success", "(")) or
        _contains_sequence(strings, ("messages", ".", "error", "(")) or
        _contains_sequence(strings, ("messages", ".", "warning", "(")) or
        _contains_sequence(strings, ("messages", ".", "info", "("))):
        return "_"

    if _contains_sequence(strings, ("ValidationError", "(")):
        return "_"

    if _contains_sequence(strings, ("PermissionDenied", "(")):
        return "_"

    if _contains_sequence(strings, ("verbose_name", "=")):
        return "gettext_lazy"

    if _contains_sequence(strings, ("help_text", "=")):
        return "gettext_lazy"

    if _contains_sequence(strings, ("{", ":")):
        for i in range(len(strings) - 1):
            if strings[i] == "{" and strings[i + 1] != "":
                for k in range(i + 2, len(strings)):
                    if strings[k] == ":":
                        key = strings[i + 1:k]
                        key_str = "".join(key).lower()
                        if "message" in key_str or "error" in key_str or "detail" in key_str:
                            return "_"
                        break

    return None


def _offset_for_pos(content_lines, pos):
    line, col = pos
    offset = sum(len(l) for l in content_lines[:line - 1])
    return offset + col


def merge_adjacent_strings(tokens):
    merged = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok.type != tokenize.STRING:
            merged.append(tok)
            i += 1
            continue
        group = [tok]
        j = i + 1
        while j < n:
            nt = tokens[j]
            if nt.type in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT):
                j += 1
                continue
            if nt.type == tokenize.STRING:
                group.append(nt)
                j += 1
                continue
            break
        if len(group) == 1:
            merged.append(tok)
        else:
            combined_value = "".join(get_string_value(t.string) or "" for t in group)
            combined_lit = repr(combined_value)
            merged.append(tokenize.TokenInfo(
                type=tok.type,
                string=combined_lit,
                start=tok.start,
                end=group[-1].end,
                line=tok.line,
            ))
        i = j
    return merged


def process_file(path, dry_run=False):
    content = path.read_text(encoding="utf-8")
    original = content
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(content).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError) as e:
        print(f"  SKIP {path.relative_to(BASE_DIR)}: {e}")
        return False

    tokens = merge_adjacent_strings(tokens)
    content_lines = content.splitlines(keepends=True)
    if content_lines and not content_lines[-1].endswith("\n"):
        content_lines[-1] += "\n"

    replacements = []
    needs_gettext = False
    needs_gettext_lazy = False

    for i, tok in enumerate(tokens):
        if tok.type != tokenize.STRING:
            continue
        if tok.string.startswith((chr(34)+chr(34)+chr(34), chr(39)+chr(39)+chr(39))):
            continue
        value = get_string_value(tok.string)
        if not value or not HAS_CHINESE.search(value):
            continue
        ctx = detect_context(tokens, i)
        if ctx == "_":
            new_str = wrap_literal(tok.string, "_")
            needs_gettext = True
        elif ctx == "gettext_lazy":
            new_str = wrap_literal(tok.string, "gettext_lazy")
            needs_gettext_lazy = True
        else:
            continue
        start_off = _offset_for_pos(content_lines, tok.start)
        end_off = _offset_for_pos(content_lines, tok.end)
        replacements.append((start_off, end_off, new_str))

    if not replacements and not needs_gettext and not needs_gettext_lazy:
        return False

    replacements.sort(key=lambda x: x[0], reverse=True)
    for start, end, new_str in replacements:
        content = content[:start] + new_str + content[end:]

    if needs_gettext or needs_gettext_lazy:
        imports = []
        if needs_gettext:
            imports.append("from django.utils.translation import gettext as _")
        if needs_gettext_lazy:
            imports.append("from django.utils.translation import gettext_lazy")
        content = add_imports(content, imports)

    changed = content != original
    if changed and not dry_run:
        path.write_text(content, encoding="utf-8")
    return changed


def add_imports(content, imports):
    lines = content.splitlines()
    insert_idx = 0
    paren_depth = 0
    in_import_block = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(("import ", "from ")):
            in_import_block = True
            paren_depth = line.count("(") - line.count(")")
            if paren_depth == 0:
                insert_idx = idx + 1
            continue
        if in_import_block:
            paren_depth += line.count("(") - line.count(")")
            if paren_depth == 0 and stripped.startswith(("import ", "from ")):
                insert_idx = idx + 1
            elif paren_depth == 0 and not stripped.startswith(("import ", "from ")):
                if insert_idx == 0:
                    insert_idx = idx
                break
            continue
    if insert_idx == 0:
        insert_idx = 0
    for imp in imports:
        if imp in content:
            continue
        lines.insert(insert_idx, imp)
        insert_idx += 1
    result = "\n".join(lines)
    if content.endswith("\n"):
        result += "\n"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    changed_files = []
    for app_dir in APP_DIRS:
        for root, dirs, files in os.walk(app_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in files:
                if not name.endswith(".py") or name in SKIP_FILES:
                    continue
                path = Path(root) / name
                if process_file(path, dry_run=args.dry_run):
                    changed_files.append(str(path.relative_to(BASE_DIR)))

    print(f"Changed files: {len(changed_files)}")
    for f in changed_files:
        print(f"  {f}")


if __name__ == "__main__":
    main()
