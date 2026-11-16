#!/usr/bin/env python3
"""Check skills against the Agent Skills specification and keep private material out of the pack."""
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
LINK = re.compile(r"\]\(\s*(?:<([^>]+)>|([^)\s]+))")
CODE = re.compile(r"^[ \t]*(`{3,}|~{3,}).*?^[ \t]*\1|(?<![`\\])(`+)(?!`)[^\n]*?(?<!`)\2(?!`)", re.S | re.M)
LEAKS = [
    (re.compile(r"[A-Za-z]:[\\/]+(Users|Documents)[\\/]", re.I), "local path"),
    (re.compile(r"AppData[\\/]+(Local|Roaming)", re.I), "local path"),
    (re.compile(r"/memorie[s]/", re.I), "agent memory note"),
]
# The FORBIDDEN_TERMS secret holds private names, so the list itself is never published.
TERMS = [term.strip() for term in os.environ.get("FORBIDDEN_TERMS", "").split(",") if term.strip()]
LEAKS += [(re.compile(re.escape(term), re.I), "private name") for term in TERMS]


def frontmatter(text):
    match = re.match(r"---\n(.*?)\n---\n", text.replace("\r\n", "\n"), re.S)
    if not match:
        return None
    fields, key = {}, None
    for line in match.group(1).split("\n"):
        if line[:1].isspace() and key:
            fields[key] = f"{fields[key]} {line.strip()}".strip()
        elif ":" in line:
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            fields[key] = "" if value in (">", ">-", "|", "|-") else value.strip("'\"")
    return fields


def check_skill(folder, errors):
    skill = folder / "SKILL.md"
    if not skill.is_file():
        errors.append(f"{folder.name}: missing SKILL.md")
        return
    text = skill.read_text(encoding="utf-8")
    fields = frontmatter(text)
    if fields is None:
        errors.append(f"{folder.name}/SKILL.md: missing YAML frontmatter")
        return
    name, description = fields.get("name", ""), fields.get("description", "")
    if name != folder.name:
        errors.append(f"{folder.name}/SKILL.md: name '{name}' must match the folder name")
    if not NAME.fullmatch(name) or len(name) > 64:
        errors.append(f"{folder.name}/SKILL.md: name must be 1-64 lowercase letters, digits and single hyphens")
    if not 1 <= len(description) <= 1024:
        errors.append(f"{folder.name}/SKILL.md: description must be 1-1024 characters, is {len(description)}")
    if text.count("\n") >= 500:
        errors.append(f"{folder.name}/SKILL.md: over 500 lines; move detail into references/")


def check_file(path, errors):
    rel = path.relative_to(ROOT).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    for number, line in enumerate(text.splitlines(), 1):
        for pattern, why in LEAKS:
            if pattern.search(line):
                errors.append(f"{rel}:{number}: {why}")
    if path.suffix == ".md":
        for angled, plain in LINK.findall(CODE.sub("", text)):
            target = unquote(angled or plain)
            if re.match(r"[a-z][a-z0-9+.-]*:|#", target):
                continue
            if not (path.parent / target.split("#")[0]).exists():
                errors.append(f"{rel}: broken link {target}")


def main():
    errors = []
    skills = sorted(p for p in (ROOT / "skills").glob("*") if p.is_dir())
    for folder in skills:
        check_skill(folder, errors)
    shipped = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, check=True,
    ).stdout.decode().split("\0")
    for path in sorted(ROOT / name for name in shipped if name):
        if path.is_file():
            check_file(path, errors)
    if not TERMS:
        print("warning: FORBIDDEN_TERMS is not set, so private names were not checked")
    for error in errors:
        print(f"error: {error}")
    print(f"{len(skills)} skills, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
