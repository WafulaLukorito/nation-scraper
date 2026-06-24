import json
import datetime
import sys


def parse_date(s):
    if not s:
        return datetime.datetime.min
    try:
        if s.endswith('Z'):
            return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ')
        return datetime.datetime.fromisoformat(s)
    except Exception:
        try:
            return datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))
        except Exception:
            return datetime.datetime.min


def main():
    path = 'success_log.json'
    if len(sys.argv) > 1:
        path = sys.argv[1]
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list):
        print('JSON root is not a list; aborting.')
        return
    data.sort(key=lambda x: parse_date(x.get('date', '')), reverse=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'Sorted {len(data)} entries in {path} (newest first)')


if __name__ == '__main__':
    main()
