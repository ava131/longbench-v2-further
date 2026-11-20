#!/usr/bin/env python3
"""检查 JSON / JSONL 数据集里的重复。

用法示例：
  # 按 _id 查重（默认）
  python check_duplicates.py -s data.json

  # 按多个字段组合查重
  python check_duplicates.py -s data.json --fields context question

  # 整行完全重复
  python check_duplicates.py -s data.json --full-row

  # 只看前 5 个重复样例，输出 JSON
  python check_duplicates.py -s data.json --fields context --top 5 --json
"""
import argparse, hashlib, json, sys
from collections import defaultdict

def load(path):
    with open(path, encoding='utf-8-sig') as f:
        raw = f.read()
    s = raw.lstrip()
    if not s:
        return []
    if s[0] == '[':
        return json.loads(s)
    if s[0] == '{':
        try:
            d = json.loads(s)
            return d if isinstance(d, list) else [d]
        except json.JSONDecodeError:
            pass
    return [json.loads(line) for line in s.splitlines() if line.strip()]

def key_of(row, fields, full):
    if full:
        payload = json.dumps(row, ensure_ascii=False, sort_keys=True)
    else:
        payload = '\x1f'.join(str(row.get(f)) for f in fields)
    return hashlib.sha256(payload.encode()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', required=True)
    ap.add_argument('--fields', default='_id', help='逗号分隔，默认 _id')
    ap.add_argument('--full-row', action='store_true', help='整行比较')
    ap.add_argument('--top', type=int, default=10)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    rows = load(args.source)
    fields = [f.strip() for f in args.fields.split(',') if f.strip()]
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[key_of(row, fields, args.full_row)].append(i)

    dups = {k: v for k, v in groups.items() if len(v) > 1}
    extra = sum(len(v) - 1 for v in dups.values())
    distinct = len(groups)

    if args.json:
        out = {
            'source': args.source,
            'rows': len(rows),
            'distinct': distinct,
            'duplicate_keys': len(dups),
            'extra_rows': extra,
            'duplicate_groups': [
                {'key_fields': 'ALL' if args.full_row else fields,
                 'count': len(v), 'indices': v[:20],
                 'sample': {k: rows[v[0]].get(k) for k in (fields if not args.full_row else list(rows[v[0]])[:5])}}
                for k, v in sorted(dups.items(), key=lambda kv: -len(kv[1]))[:args.top]
            ],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print(f'文件: {args.source}')
    print(f'总行数: {len(rows)}  不同值: {distinct}  重复组: {len(dups)}  多出的行: {extra}')
    if not dups:
        print('没有重复')
        return
    print()
    print(f'{"次数":>4}  {"首次出现(前10个位置)":<40}  样例')
    for k, v in sorted(dups.items(), key=lambda kv: -len(kv[1]))[:args.top]:
        sample = rows[v[0]]
        if args.full_row:
            desc = json.dumps(sample, ensure_ascii=False)[:60]
        else:
            desc = ' | '.join(f'{f}={sample.get(f)!r}' for f in fields)[:60]
        print(f'{len(v):>4}  {str(v[:10]):<40}  {desc}')

if __name__ == '__main__':
    main()
