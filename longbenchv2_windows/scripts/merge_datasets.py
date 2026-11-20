#!/usr/bin/env python3
"""拼接两个 JSONL 数据集，并校验字段/类型/格式一致。

- 必需字段：_id/domain/sub_domain/difficulty/length/question/choice_A..D/answer/context
- 可选：_tokens/bucket/_copy 等；用 --fill key=value 给缺失字段补默认值
"""
import argparse, json, sys
from collections import Counter

REQUIRED=['_id','domain','sub_domain','difficulty','length','question','choice_A','choice_B','choice_C','choice_D','answer','context']

def load(path):
    rows=[]
    for i,line in enumerate(open(path,encoding='utf-8'),1):
        line=line.strip()
        if not line: continue
        try: rows.append(json.loads(line))
        except Exception as e: sys.exit(f'{path}:{i} JSON 解析失败: {e}')
    return rows

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base',required=True)
    ap.add_argument('--add',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--fill',action='append',default=[],help='key=value，可多次')
    ap.add_argument('--allow-dup-id',action='store_true')
    args=ap.parse_args()
    fill={}
    for x in args.fill:
        k,v=x.split('=',1)
        try: v=json.loads(v)
        except Exception: pass
        fill[k]=v
    a=load(args.base); b=load(args.add)
    for name,rows in (('base',a),('add',b)):
        for i,r in enumerate(rows):
            miss=[k for k in REQUIRED if k not in r]
            if miss: sys.exit(f'{name} 第 {i+1} 行缺字段: {miss}')
    keys_a=set().union(*[set(r) for r in a]) if a else set()
    keys_b=set().union(*[set(r) for r in b]) if b else set()
    allkeys=sorted(keys_a|keys_b)
    print('base keys:',sorted(keys_a)); print('add  keys:',sorted(keys_b))
    print('only in base:',sorted(keys_a-keys_b),'| only in add:',sorted(keys_b-keys_a))
    for r in a+b:
        for k,v in fill.items(): r.setdefault(k,v)
    for r in a+b:
        for k in allkeys: r.setdefault(k,None)
    # 类型一致性
    types={}
    bad=[]
    for r in a+b:
        for k,v in r.items():
            t=type(v).__name__
            types.setdefault(k,Counter())[t]+=1
            if k in ('_tokens','_copy') and v is not None and not isinstance(v,int): bad.append((k,t))
            if k=='context' and not isinstance(v,str): bad.append((k,t))
    for k in allkeys: print(' type',k,dict(types[k]))
    if bad: sys.exit(f'类型异常: {bad[:5]}')
    ids_a=[r['_id'] for r in a]; ids_b=[r['_id'] for r in b]
    if not args.allow_dup_id:
        dup=set(ids_a)&set(ids_b)
        if dup: print('警告: 交集 _id 数量',len(dup))
    out=a+b
    with open(args.out,'w',encoding='utf-8') as f:
        for r in out: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print('merged',len(a),'+',len(b),'=',len(out),'->',args.out)
    print('base _tokens:',min(r.get('_tokens') or 0 for r in a),'-',max(r.get('_tokens') or 0 for r in a))
    print('add  _tokens:',min(r.get('_tokens') or 0 for r in b),'-',max(r.get('_tokens') or 0 for r in b))

if __name__=='__main__': main()
