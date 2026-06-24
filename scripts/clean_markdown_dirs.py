import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
MD = ROOT / 'markdown'
KEEP = {'Makau Mutua', 'Unknown Author'}

def main():
    if not MD.exists():
        print('markdown directory not found')
        return 1
    removed = []
    kept = []
    for p in sorted(MD.iterdir()):
        if p.is_dir():
            if p.name in KEEP:
                kept.append(p.name)
            else:
                try:
                    shutil.rmtree(p)
                    removed.append(p.name)
                except Exception as e:
                    print('error removing', p, e)
    print(f'removed={len(removed)} kept={len(kept)}')
    if removed:
        print('Removed folders:')
        for n in removed[:100]:
            print(n)
    print('Kept folders:')
    for n in kept:
        print(n)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
