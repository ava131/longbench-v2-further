#!/usr/bin/env python3
"""把 TV 数据集的 gsm8k.jsonl / longbenchv2.jsonl 原地改成 issue 的 turns 格式。

- gsm8k:    {"question": [{"content":..., "role":...}, ...], "answer": ""}
- v2:       其他字段不变，"context" 变成同样的 turns 数组

用法：
    python to_turns.py --all
    python to_turns.py --dir 32k_218
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

def convert(d):
    d=Path(d)
    g=d/'gsm8k.jsonl'
    if g.exists():
        rows=[json.loads(l) for l in g.open(encoding='utf-8')]
        out=[]
        for r in rows:
            q=r['question']
            out.append({'question':q if isinstance(q,list) else parse(q),'answer':r.get('answer','')})
        with g.open('w',encoding='utf-8') as f:
            for r in out: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    v=d/'longbenchv2.jsonl'
    if v.exists():
        rows=[json.loads(l) for l in v.open(encoding='utf-8')]
        with v.open('w',encoding='utf-8') as f:
            for r in rows:
                if not isinstance(r['context'],list): r['context']=parse(r['context'])
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
