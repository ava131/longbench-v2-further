#!/usr/bin/env python3
"""把 TV Assistant 的对话文本转成 issue 里的格式：
每行一个 JSON 数组，元素为 {"content": ..., "role": "user"|"assistant"}。

用法：
    python to_turns.py --dir 32k_218
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

def convert(d):
    d=Path(d)
    src=d/'longbenchv2.jsonl'
    if not src.exists(): src=d/'gsm8k.jsonl'
    rows=[json.loads(l) for l in src.open(encoding='utf-8')]
    convs=[]
    for r in rows:
        text=r.get('context') or r.get('question')
        convs.append(parse(text))
    with (d/'turns.jsonl').open('w',encoding='utf-8') as f:
        for c in convs: f.write(json.dumps(c,ensure_ascii=False)+'\n')
    print(d.name,'conversations',len(convs),'turns',sum(len(c) for c in convs))

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--dir')
    ap.add_argument('--all',action='store_true')
    args=ap.parse_args()
    base=Path(__file__).parent
    if args.all:
        for d in sorted(base.glob('32k_*')):
            if d.is_dir(): convert(d)
    else:
        convert(base/args.dir)
