"""
Build an EPUB from markdown files in markdown/Makau Mutua and markdown/Unknown Author.
Usage:
    python scripts\make_epub.py [--ascending] [--output out.epub]

Defaults: order newest-first (descending). Use --ascending for oldest-first.

Requires: ebooklib, markdown2
Install in venv:
    python -m pip install ebooklib markdown2
"""
import argparse
import pathlib
import re
import sys
from datetime import datetime

try:
    import markdown2
    from ebooklib import epub
except Exception as e:
    print("Missing dependencies. Run: python -m pip install ebooklib markdown2")
    raise

ROOT = pathlib.Path(__file__).resolve().parent.parent
MD_DIR = ROOT / 'markdown'
FOLDERS = ['Makau Mutua', 'Unknown Author']
DATE_PREFIX = re.compile(r'^(\d{4}-\d{2}-\d{2})-(.+)$')


def collect_files():
    files = []
    for folder in FOLDERS:
        d = MD_DIR / folder
        if not d.exists():
            continue
        for p in d.glob('*.md'):
            m = DATE_PREFIX.match(p.name)
            if m:
                date = m.group(1)
                rest = m.group(2)
                try:
                    dt = datetime.strptime(date, '%Y-%m-%d')
                except Exception:
                    dt = None
            else:
                dt = None
            files.append((p, dt))
    return files


def md_to_html(content: str) -> str:
    # markdown2 with extras for code-friendly output
    return markdown2.markdown(content, extras=['fenced-code-blocks', 'tables'])


def build_epub(output: pathlib.Path, ascending: bool = False):
    files = collect_files()
    files = [f for f in files if f[1] is not None]
    files.sort(key=lambda x: x[1], reverse=not ascending)

    book = epub.EpubBook()
    book.set_title('Collected Articles - Makau Mutua & Unknown Author')
    book.add_author('Various')

    spine = ['nav']
    toc = []
    chapters = []

    for i, (path, dt) in enumerate(files, start=1):
        text = path.read_text(encoding='utf-8')
        # strip any initial title line (starting with # ) to use as chapter title
        lines = text.splitlines()
        title = None
        for line in lines[:5]:
            if line.strip().startswith('#'):
                title = line.strip().lstrip('#').strip()
                break
        if not title:
            title = path.stem

        html = md_to_html(text)
        chapter = epub.EpubHtml(title=title, file_name=f'chap_{i}.xhtml', lang='en')
        chapter.content = f'<h1>{title}</h1>\n' + html
        book.add_item(chapter)
        chapters.append(chapter)
        spine.append(chapter)
        toc.append(chapter)

    book.toc = tuple(toc)
    book.spine = spine

    # basic CSS
    style = (
        'BODY { font-family: serif; }\n'
        'h1 { font-size: 1.2em; margin-top: 1em; }\n'
    )
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
    book.add_item(nav_css)

    # add default NCX and Nav
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # write
    epub.write_epub(str(output), book, {})
    print(f'Wrote {output} with {len(chapters)} chapters')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ascending', action='store_true', help='oldest-first')
    parser.add_argument('--output', '-o', default='collected.epub')
    args = parser.parse_args()
    out = ROOT / args.output
    build_epub(out, ascending=args.ascending)


if __name__ == '__main__':
    main()
