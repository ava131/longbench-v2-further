#!/usr/bin/env python3
"""拼接两个数据集（JSONL 或 JSON 数组），并校验字段/类型一致。

用法：
  python merge_datasets.py --base base.jsonl --add win_60_72k.jsonl --out merged.jsonl
  python merge_datasets.py --base base.json  --add add.json  --out merged.jsonl \
      --fill bucket=60k-72k --rename prompt=question

- base/add 都支持 .jsonl（一行一条）和 .json（数组）
- 必需字段：_id/domain/sub_domain/difficulty/length/question/choice_A..D/answer/context
- 缺失字段用 --fill key=value 补（value 会按 JSON 解析，0 是 int，"x" 是 str）
- 字段名不一致用 --rename old=new
"""
import argparse, json, sys
from collections import Counter

REQUIRED=['_id','domain','sub_domain','difficulty','length','question',
          'choice_A','choice_B','choice_C','choice_D','answer','context']

def load(path):
    with open(path,encoding='utf-8-sig') as f:
        raw=f.read()
    stripped=raw.lstrip()
    if not stripped: return []
    if stripped[0]=='[':
        data=json.loads(stripped)
        if not isinstance(data,list): sys.exit(f'{path}: 不是数组')
        return data
    if stripped[0]=='{':
        try:
            data=json.loads(stripped)
            return data if isinstance(data,list) else [data]
        except json.JSONDecodeError:
            pass  # 当成 JSONL
    rows=[]
    for i,line in enumerate(stripped.splitlines(),1):
        line=line.strip()
        if not line: continue
        try: rows.append(json.loads(line))
        except Exception as e: sys.exit(f'{path}:{i} 解析失败: {e}')
    return rows

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base',required=True)
    ap.add_argument('--add',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--fill',action='append',default=[],help='key=value，可多次')
    ap.add_argument('--rename',action='append',default=[],help='old=new，可多次')
    args=ap.parse_args()

    fill={}
    for x in args.fill:
        k,v=x.split('=',1)
        try: v=json.loads(v)
        except Exception: pass
        fill[k]=v
    rename=dict(x.split('=',1) for x in args.rename)

    a=load(args.base); b=load(args.add)
    for r in a+b:
        for old,new in rename.items():
            if old in r and new not in r: r[new]=r.pop(old)
    for name,rows in (('base',a),('add',b)):
        if not rows: sys.exit(f'{name} 为空')
        for i,r in enumerate(rows):
            miss=[k for k in REQUIRED if k not in r]
            if miss: sys.exit(f'{name} 第 {i+1} 行缺字段: {miss}；可用 --fill 或 --rename 修复')

    keys_a=set().union(*map(set,a)); keys_b=set().union(*map(set,b))
    print('base 条数:',len(a),'| add 条数:',len(b))
    print('base keys:',sorted(keys_a))
    print('add  keys:',sorted(keys_b))
    print('只在 base:',sorted(keys_a-keys_b),'| 只在 add:',sorted(keys_b-keys_a))

    allkeys=sorted(keys_a|keys_b)
    for r in a+b:
        for k,v in fill.items(): r.setdefault(k,v)
    for r in a+b:
        for k in allkeys: r.setdefault(k,None)

    types={}
    for r in a+b:
        for k,v in r.items(): types.setdefault(k,Counter())[type(v).__name__]+=1
    for k in allkeys:
        print(f'  {k:12s}', dict(types[k]))
    bad=[(k,dict(types[k])) for k in ('context',) if set(types[k])-{'str'}]
    bad+=[(k,dict(types[k])) for k in ('_tokens','_copy') if k in types and set(types[k])-{'int','NoneType'}]
    if bad: sys.exit(f'类型不一致: {bad}')

    dup=set(r['_id'] for r in a)&set(r['_id'] for r in b)
    if dup: print(f'警告: base 和 add 有 {len(dup)} 个重复 _id')

    out=a+b
    if args.out.endswith('.json'):
        json.dump(out, open(args.out,'w',encoding='utf-8'), ensure_ascii=False)
    else:
        with open(args.out,'w',encoding='utf-8') as f:
            for r in out: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print(f'合并: {len(a)} + {len(b)} = {len(out)} -> {args.out}')

if __name__=='__main__': main()
