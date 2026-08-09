#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Django 模板自动 i18n 包裹脚本。
"""
import argparse
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
EXTRA_FILE = BASE_DIR / "clubs" / "i18n_extra.py"

TRANSLATE_ATTRS = {
    "placeholder", "title", "aria-label", "alt", "label",
    "data-label", "data-office-file-name", "data-title",
}

RE_DVAR_DEFAULT = re.compile(r'\|default\s*:\s*"([^"]+)"')


def has_chinese(s):
    return bool(re.search(r"[\u4e00-\u9fff]", s))


def tokenize(content):
    tokens = []
    i = 0
    n = len(content)
    while i < n:
        if content.startswith("{%", i):
            j = content.find("%}", i + 2)
            if j == -1:
                tokens.append(("text", content[i:]))
                break
            j += 2
            tag_inner = content[i + 2:j - 2].strip()
            tag_name = tag_inner.split(None, 1)[0].lower() if tag_inner else ""
            if tag_name in ("comment", "verbatim"):
                end_tag = f"{{% end{tag_name} %}}"
                k = content.find(end_tag, j)
                if k == -1:
                    tokens.append(("raw", content[i:]))
                    break
                k += len(end_tag)
                tokens.append(("raw", content[i:k]))
                i = k
                continue
            else:
                tokens.append(("dtag", content[i:j]))
                i = j
                continue
        if content.startswith("{{", i):
            j = content.find("}}", i + 2)
            if j == -1:
                tokens.append(("text", content[i:]))
                break
            j += 2
            tokens.append(("dvar", content[i:j]))
            i = j
            continue
        if content.startswith("<!--", i):
            j = content.find("-->", i + 4)
            if j == -1:
                tokens.append(("comment", content[i:]))
                break
            j += 3
            tokens.append(("comment", content[i:j]))
            i = j
            continue
        if content[i] == "<":
            m = re.match(r"<([a-zA-Z][\w\-]*)", content[i:])
            if m:
                tag_name = m.group(1).lower()
                if tag_name in ("script", "style", "pre", "textarea"):
                    tag_end = find_tag_end(content, i)
                    if tag_end != -1:
                        tokens.append(("htag", content[i:tag_end]))
                        i = tag_end
                        end_tag = f"</{tag_name}>"
                        j = content.lower().find(end_tag, i)
                        if j == -1:
                            tokens.append(("raw", content[i:]))
                            break
                        tokens.append(("raw", content[i:j]))
                        tokens.append(("htag", content[j:j + len(end_tag)]))
                        i = j + len(end_tag)
                        continue
            tag_end = find_tag_end(content, i)
            if tag_end != -1:
                tokens.append(("htag", content[i:tag_end]))
                i = tag_end
                continue
        j = i
        while j < n and content[j] not in "<{":
            j += 1
        if j > i:
            tokens.append(("text", content[i:j]))
            i = j
        else:
            tokens.append(("text", content[i]))
            i += 1
    return tokens


def find_tag_end(content, start):
    if content[start] != "<":
        return -1
    i = start + 1
    n = len(content)
    in_quote = None
    while i < n:
        ch = content[i]
        if content.startswith("{%", i):
            j = content.find("%}", i)
            if j == -1:
                return -1
            i = j + 2
            continue
        if content.startswith("{{", i):
            j = content.find("}}", i)
            if j == -1:
                return -1
            i = j + 2
            continue
        if in_quote:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == in_quote:
                in_quote = None
            i += 1
            continue
        if ch in ('"', "'"):
            in_quote = ch
            i += 1
            continue
        if ch == ">":
            return i + 1
        i += 1
    return -1


def _skip_django_block(s, i):
    n = len(s)
    if s.startswith("{%", i):
        j = s.find("%}", i)
        return j + 2 if j != -1 else n
    if s.startswith("{{", i):
        j = s.find("}}", i)
        return j + 2 if j != -1 else n
    return i


def extract_attrs(tag):
    m = re.match(r"<([a-zA-Z][\w\-]*)\s*(.*)", tag, re.DOTALL)
    if not m:
        return None, []
    tag_name = m.group(1).lower()
    rest = m.group(2).rstrip()
    if rest.endswith(">"):
        rest = rest[:-1].rstrip()
    attrs = []
    i = 0
    n = len(rest)
    while i < n:
        while i < n and rest[i] in " \t\n\r":
            i += 1
        if i >= n:
            break
        name_start = i
        while i < n and rest[i] not in "= \t\n\r/>":
            i += 1
        name = rest[name_start:i]
        if not name:
            i += 1
            continue
        while i < n and rest[i] in " \t\n\r":
            i += 1
        if i < n and rest[i] == "=":
            i += 1
            while i < n and rest[i] in " \t\n\r":
                i += 1
            if i < n and rest[i] in ('"', "'"):
                q = rest[i]
                i += 1
                val_start = i
                while i < n:
                    skip = _skip_django_block(rest, i)
                    if skip != i:
                        i = skip
                        continue
                    if rest[i] == q:
                        break
                    if rest[i] == "\\" and i + 1 < n:
                        i += 2
                        continue
                    i += 1
                value = rest[val_start:i]
                attrs.append((name, q, value))
                if i < n:
                    i += 1
            else:
                val_start = i
                while i < n and rest[i] not in " \t\n\r/>":
                    i += 1
                value = rest[val_start:i]
                attrs.append((name, "", value))
        else:
            attrs.append((name, "", ""))
    return tag_name, attrs


def apply_tdefault(dvar_text, collected):
    def repl(m):
        s = m.group(1)
        if not has_chinese(s):
            return m.group(0)
        collected.add(s)
        return f'|tdefault:"{s}"'
    return RE_DVAR_DEFAULT.sub(repl, dvar_text)


def wrap_js(js_text, source_hint):
    # JavaScript template literals can contain nested HTML, expressions, and
    # even other template literals.  Rewriting them with this lightweight
    # scanner is unsafe (it previously corrupted valid markup and closing
    # script tags), so leave such blocks untouched and audit their visible
    # strings separately.
    if "`" in js_text:
        return js_text

    result = []
    i = 0
    n = len(js_text)
    while i < n:
        if js_text[i] in ('"', "'", "`"):
            quote = js_text[i]
            start = i
            i += 1
            buf = []
            while i < n:
                ch = js_text[i]
                if ch == "\\" and i + 1 < n:
                    buf.append(js_text[i:i + 2])
                    i += 2
                    continue
                if ch == quote:
                    i += 1
                    break
                buf.append(ch)
                i += 1
            string = "".join(buf)
            original = js_text[start:i]
            if has_chinese(string) and not should_skip_js_string(js_text, start):
                result.append(wrap_one_js_string(string, quote))
            else:
                result.append(original)
            continue
        if js_text[i] == "/" and i + 1 < n:
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
        result.append(js_text[i])
        i += 1
    return "".join(result)


def should_skip_js_string(text, start):
    s = text[start:start + 120]
    if "{%" in s or "{{" in s:
        return True
    j = start - 1
    while j >= 0 and text[j] in " \t\n\r":
        j -= 1
    if j >= 0 and text[j] in "{,":
        k = start + 1
        while k < len(text) and text[k] in " \t\n\r":
            k += 1
        if k < len(text) and text[k] == ":":
            return True
    before = text[max(0, start - 50):start]
    if re.search(r"\b(?:gettext|ngettext|pgettext)\s*\(\s*$", before):
        return True
    if re.search(r"\bcase\s+$", before):
        return True
    if re.search(r"==?\s+$", before):
        return True
    return False


def wrap_one_js_string(string, quote):
    if quote == "`":
        parts = re.split(r"(\$\{[^}]*\})", string)
        out = []
        for part in parts:
            if re.match(r"\$\{.*\}", part):
                inner = part[2:-1]
                out.append(f" + ({inner}) + ")
            elif has_chinese(part):
                esc = js_escape(part)
                out.append(f"gettext('{esc}')")
            elif part:
                out.append(f"'{js_escape(part)}'")
        s = "".join(out)
        s = re.sub(r"^\s*\+\s*|\s*\+\s*$", "", s)
        s = re.sub(r"\+\s*\+", "+", s)
        return s
    else:
        esc = js_escape(string)
        return f"gettext('{esc}')"


def js_escape(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")


def wrap_html_tag(tag):
    # 标签内部含有 Django 模板标记时直接跳过，避免重建时破坏条件属性。
    if "{%" in tag or "{{" in tag:
        return tag
    tag_name, attrs = extract_attrs(tag)
    if not tag_name:
        return tag
    new_attrs = []
    changed = False
    for name, q, value in attrs:
        lower_name = name.lower()
        if not has_chinese(value):
            new_attrs.append(format_attr(name, q, value))
            continue
        if lower_name.startswith("on"):
            wrapped = wrap_js(value, f"on-{lower_name}")
            new_attrs.append(format_attr(name, q, wrapped))
            changed = True
            continue
        if lower_name in TRANSLATE_ATTRS:
            if q == "":
                q = '"'
            new_attrs.append(format_attr(name, q, f"{{% trans '{escape_trans(value)}' %}}"))
            changed = True
            continue
        if lower_name == "value":
            type_attr = next((v for n, _, v in attrs if n.lower() == "type"), "")
            if type_attr and type_attr.lower() in ("submit", "button", "reset"):
                new_attrs.append(format_attr(name, q, f"{{% trans '{escape_trans(value)}' %}}"))
                changed = True
                continue
        new_attrs.append(format_attr(name, q, value))
    if not changed:
        return tag
    rest = " ".join(new_attrs)
    if tag.endswith("/>"):
        return f"<{tag_name} {rest} />"
    return f"<{tag_name} {rest}>"


def format_attr(name, q, value):
    if q:
        return f'{name}={q}{value}{q}'
    return f'{name}={value}'


def escape_trans(s):
    return s.replace("'", "\\'")


def wrap_text_group(texts, dvars):
    if not dvars:
        combined = "".join(texts)
        if not has_chinese(combined.strip()):
            return combined
        clean = collapse_whitespace(combined.strip())
        if not clean:
            return combined
        return f"{{% trans '{escape_trans(clean)}' %}}"
    # 保持 text/dvar 的原始交错顺序
    group_parts = []
    t_idx = 0
    d_idx = 0
    while t_idx < len(texts) or d_idx < len(dvars):
        if t_idx < len(texts):
            group_parts.append(texts[t_idx])
            t_idx += 1
        if d_idx < len(dvars):
            group_parts.append(dvars[d_idx])
            d_idx += 1
    full_text = "".join(group_parts)
    aliases = {}
    alias_idx = 0
    tmp = full_text
    for idx, dvar in enumerate(dvars):
        alias_idx += 1
        aliases[f"__i18n{alias_idx}"] = dvar[2:-2].strip()
        tmp = tmp.replace(dvar, f"{{{{ __i18n{alias_idx} }}}}", 1)
    if not has_chinese(tmp.strip()):
        return full_text
    with_parts = " ".join(f"{k}={v}" for k, v in aliases.items())
    return f"{{% blocktrans with {with_parts} %}}{tmp}{{% endblocktrans %}}"


def collapse_whitespace(s):
    return re.sub(r"\s+", " ", s)


def ensure_load(content, needs_i18n, needs_common_tags):
    if content.lstrip().startswith("{% extends"):
        lines = content.splitlines()
        extends_end = 0
        for idx, line in enumerate(lines):
            if line.lstrip().startswith("{% extends"):
                if "%}" in line:
                    extends_end = idx + 1
                    break
        head = "\n".join(lines[:extends_end])
        tail = "\n".join(lines[extends_end:])
        adds = []
        if needs_i18n and "{% load i18n %}" not in content:
            adds.append("{% load i18n %}")
        if needs_common_tags and "{% load common_tags %}" not in content:
            adds.append("{% load common_tags %}")
        if adds:
            return head + "\n" + "\n".join(adds) + "\n" + tail
        return content
    else:
        adds = []
        if needs_i18n and "{% load i18n %}" not in content:
            adds.append("{% load i18n %}")
        if needs_common_tags and "{% load common_tags %}" not in content:
            adds.append("{% load common_tags %}")
        if adds:
            return "\n".join(adds) + "\n" + content
        return content


def process_file(path, dry_run=False):
    content = path.read_text(encoding="utf-8")
    tokens = tokenize(content)
    new_tokens = []
    changed = False
    default_strings = set()
    needs_i18n = False
    needs_common_tags = False
    i = 0
    n = len(tokens)
    blocktrans_depth = 0
    while i < n:
        kind, val = tokens[i]
        if kind == "dtag":
            tag_inner = val[2:-2].strip()
            tag_name = tag_inner.split(None, 1)[0].lower() if tag_inner else ""
            if tag_name in ("endblocktrans", "endblocktranslate"):
                blocktrans_depth = max(0, blocktrans_depth - 1)
                new_tokens.append((kind, val))
                i += 1
                continue
            if blocktrans_depth:
                new_tokens.append((kind, val))
                i += 1
                continue
            if tag_name in ("blocktrans", "blocktranslate"):
                blocktrans_depth += 1
                new_tokens.append((kind, val))
                i += 1
                continue
            new_val = apply_tdefault(val, default_strings)
            if new_val != val:
                new_tokens.append((kind, new_val))
                changed = True
                needs_common_tags = True
            else:
                new_tokens.append((kind, val))
            i += 1
            continue
        if blocktrans_depth:
            new_tokens.append((kind, val))
            i += 1
            continue
        if kind == "comment":
            new_tokens.append((kind, val))
            i += 1
            continue
        if kind == "htag":
            wrapped = wrap_html_tag(val)
            if wrapped != val:
                new_tokens.append((kind, wrapped))
                changed = True
                needs_i18n = True
            else:
                new_tokens.append((kind, val))
            i += 1
            continue
        if kind == "dvar":
            dvars_with_tdefault = apply_tdefault(val, default_strings)
            if dvars_with_tdefault != val:
                new_tokens.append((kind, dvars_with_tdefault))
                changed = True
                needs_common_tags = True
            else:
                new_tokens.append((kind, val))
            i += 1
            continue
        if kind == "raw":
            wrapped = wrap_js(val, str(path))
            if wrapped != val:
                new_tokens.append((kind, wrapped))
                changed = True
            else:
                new_tokens.append((kind, val))
            i += 1
            continue
        if kind == "text":
            texts = [val]
            dvars_in_group = []
            j = i + 1
            while j < n and tokens[j][0] in ("text", "dvar"):
                if tokens[j][0] == "text":
                    texts.append(tokens[j][1])
                else:
                    dvars_in_group.append(tokens[j][1])
                j += 1
            group_text = "".join(texts)
            wrapped = wrap_text_group(texts, dvars_in_group)
            if wrapped != group_text:
                new_tokens.append(("text", wrapped))
                changed = True
                needs_i18n = True
            else:
                new_tokens.append(("text", group_text))
            i = j
            continue
        new_tokens.append((kind, val))
        i += 1
    if changed:
        new_content = "".join(t[1] for t in new_tokens)
        new_content = ensure_load(new_content, needs_i18n, needs_common_tags)
        actual_changed = new_content != content
        if actual_changed and not dry_run:
            path.write_text(new_content, encoding="utf-8")
        return actual_changed, default_strings
    return False, default_strings


def write_i18n_extra(strings):
    lines = ["# Auto-generated by scripts/i18n_wrap_templates.py", "from django.utils.translation import gettext_noop", ""]
    for s in sorted(strings):
        lines.append(f"gettext_noop('{s.replace(chr(39), chr(92)+chr(39))}')")
    EXTRA_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Wrap Django templates for i18n")
    parser.add_argument("--dry-run", action="store_true", help="Do not write files")
    args = parser.parse_args()

    all_defaults = set()
    report = []
    for root, dirs, files in os.walk(TEMPLATES_DIR):
        dirs.sort()
        files.sort()
        for name in files:
            if not name.endswith(".html"):
                continue
            path = Path(root) / name
            changed, defaults = process_file(path, dry_run=args.dry_run)
            all_defaults.update(defaults)
            if changed:
                report.append(str(path.relative_to(BASE_DIR)))

    if not args.dry_run:
        write_i18n_extra(all_defaults)
    report_path = Path("/tmp/i18n_wrap_report.txt")
    report_path.write_text("\n".join(report), encoding="utf-8")
    print(f"Processed. Changed files: {len(report)}")
    print(f"Default strings collected: {len(all_defaults)}")
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
