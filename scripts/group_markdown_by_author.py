import json
import re
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARKDOWN_DIR = ROOT / "markdown"
SUCCESS_LOG = ROOT / "success_log.json"
AUTHOR_PATTERN = re.compile(r"^\*\*Author:\*\*\s*(.+?)\s*$", re.MULTILINE)
ID_PATTERN = re.compile(r"-(\d+)\.md$")


def safe_folder_name(name: str) -> str:
    name = name.strip()
    name = re.sub(r'[<>:"/\\|?*]', '-', name)
    name = re.sub(r"\s+", " ", name)
    name = name.strip(" .")
    if not name:
        return "unknown-author"
    return name


def load_success_authors() -> dict[str, str]:
    if not SUCCESS_LOG.exists():
        return {}
    with SUCCESS_LOG.open("r", encoding="utf-8") as f:
        data = json.load(f)
    mapping = {}
    for item in data:
        if isinstance(item, dict):
            url = item.get("url") or item.get("link")
            author = item.get("author")
            if not author or not url:
                continue
            match = ID_PATTERN.search(url)
            if match:
                mapping[match.group(1)] = author
    return mapping


def find_author_in_file(path: pathlib.Path) -> tuple[str | None, str | None]:
    text = path.read_text(encoding="utf-8")
    match = AUTHOR_PATTERN.search(text)
    author = match.group(1).strip() if match else None
    file_id = None
    match_id = ID_PATTERN.search(path.name)
    if match_id:
        file_id = match_id.group(1)
    return author, file_id


def main(dry_run: bool = False) -> int:
    if not MARKDOWN_DIR.exists() or not MARKDOWN_DIR.is_dir():
        print(f"Markdown folder not found: {MARKDOWN_DIR}")
        return 1

    success_authors = load_success_authors()
    total = 0
    moved = 0
    skipped = 0
    errors = []
    folders = set()

    for path in sorted(MARKDOWN_DIR.glob("*.md")):
        total += 1
        author, file_id = find_author_in_file(path)
        if not author and file_id:
            author = success_authors.get(file_id)

        if not author:
            errors.append(f"missing author for {path.name}")
            continue

        folder = safe_folder_name(author)
        target_dir = MARKDOWN_DIR / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / path.name

        if path == target_path:
            skipped += 1
            continue

        if target_path.exists():
            errors.append(f"target exists: {target_path}")
            continue

        if dry_run:
            print(f"DRY RUN: {path.name} -> {folder}/{path.name}")
        else:
            path.rename(target_path)
        folders.add(folder)
        moved += 1

    print(
        f"Processed {total} files: moved={moved}, skipped={skipped}, folders={len(folders)}, errors={len(errors)}"
    )
    if errors:
        print("Errors:")
        for error in errors[:100]:
            print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sys.exit(main(dry_run=dry_run))
