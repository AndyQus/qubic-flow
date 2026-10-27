"""Write the CHANGELOG entry of a version into `releaseNotes` of umbrel-app.yml.

Umbrel shows `releaseNotes` in the update dialog. Usage:
    python umbrel_release_notes.py <version> <CHANGELOG.md> <umbrel-app.yml>

If the CHANGELOG has no block for the version, the file is left untouched.
"""
import re
import sys


def extract_notes(changelog: str, version: str) -> str | None:
    m = re.search(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^---\s*$|^## \[|\Z)",
        changelog,
        flags=re.M | re.S,
    )
    if not m:
        return None
    lines = []
    for line in m.group(1).strip().splitlines():
        heading = re.match(r"^#{3,}\s+(.*)", line)
        lines.append(f"{heading.group(1)}:" if heading else line.rstrip())
    return "\n".join(lines).strip() or None


def replace_release_notes(app_yml: str, notes: str) -> str:
    block = "releaseNotes: |-\n" + "\n".join(
        f"  {line}" if line else "" for line in notes.splitlines()
    ) + "\n"
    # The field runs until the next top-level key (or a blank line before it).
    pattern = re.compile(r"^releaseNotes:.*?(?=^\S|\Z)", flags=re.M | re.S)
    if pattern.search(app_yml):
        return pattern.sub(lambda _: block + "\n", app_yml, count=1)
    return app_yml.rstrip("\n") + "\n\n" + block


def main() -> int:
    version, changelog_path, app_yml_path = sys.argv[1:4]
    with open(changelog_path, encoding="utf-8") as f:
        notes = extract_notes(f.read(), version)
    if not notes:
        print(f"::warning::No CHANGELOG entry for {version} - releaseNotes unchanged")
        return 0
    with open(app_yml_path, encoding="utf-8") as f:
        app_yml = f.read()
    with open(app_yml_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(replace_release_notes(app_yml, notes))
    print(f"releaseNotes set from CHANGELOG {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
