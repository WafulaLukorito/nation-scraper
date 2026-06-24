import re
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARKDOWN_DIR = ROOT / "markdown"
PATTERN = re.compile(r"^\s*\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)


def main(dry_run: bool = False) -> int:
    if not MARKDOWN_DIR.exists():
        print(f"Markdown directory not found: {MARKDOWN_DIR}")
        return 1

    renamed = 0
    skipped = 0
    errors = []

    for path in sorted(MARKDOWN_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        match = PATTERN.search(text)
        if not match:
            errors.append(f"missing date header: {path.name}")
            continue

        date_prefix = match.group(1)
        if path.name.startswith(f"{date_prefix}-"):
            skipped += 1
            continue

        new_name = f"{date_prefix}-{path.name}"
        new_path = path.with_name(new_name)
        if new_path.exists():
            errors.append(f"target exists: {new_path.name}")
            continue

        if dry_run:
            print(f"DRY RUN: {path.name} -> {new_name}")
        else:
            path.rename(new_path)
        renamed += 1

    print(f"Renamed {renamed} files, skipped {skipped} already-prefixed files, errors {len(errors)}")
    if errors:
        print("Errors:")
        for error in errors[:50]:
            print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sys.exit(main(dry_run=dry_run))
