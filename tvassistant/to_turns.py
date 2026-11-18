#!/usr/bin/env python3
"""把 TV 数据集的 gsm8k/v2 内容改成“看起来像列表的字符串”。

- 解析 user:/assistant: 文本为 turns 数组；
- 再用 json.dumps 压成字符串，写回 question / context；
- 这样 AISBench 里 str.format 会原样插入，不会出现 Python list repr。

用法：
    python to_turns.py --all
"""
import argparse, json, re
from pathlib import Path

def parse(text):
    turns=[]; cur=None
    for line in text.splitlines():
        m=re.match(r'^(user|assistant)\s*[:：]\s*(.*)$', line.strip(), re.I)
        if m:
            if cur: turns.append(cur)
            cur={'content':m.group(2).strip(),'role':m.group(1).lower()}
        elif cur and line.strip():
            cur['content'] += '\n' + line.strip()
    if cur: turns.append(cur)
    return turns

def to_str(v):
    if isinstance(v, list):
        return json.dumps(v, ensure_ascii=False, separators=(',',':'))
    if isinstance(v, str) and v.lstrip().startswith('['):
        return v
    return json.dumps(parse(v), ensure_ascii=False, separators=(',',':'))

def convert(d):
    d=Path(d)
    for name, field in (('gsm8k.jsonl','question'),('longbenchv2.jsonl','context')):
        p=d/name
        if not p.exists(): continue
        rows=[json.loads(l) for l in p.open(encoding='utf-8')]
        with p.open('w',encoding='utf-8') as f:
            for r in rows:
                r[field]=to_str(r[field])
                f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print(d.name,'converted')

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--dir'); ap.add_argument('--all',action='store_true')
    args=ap.parse_args()
    base=Path(__file__).parent
    if args.all:
        for d in sorted(base.glob('32k_*')):
            if d.is_dir(): convert(d)
    else:
        convert(base/args.dir)
