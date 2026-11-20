#!/usr/bin/env python3
"""从 LongBench v2 data.json 中按 token 窗口筛样本（不截断）。"""
import argparse, json
from tokenizers import Tokenizer

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--data',required=True)
    ap.add_argument('--tokenizer',default='/tmp/qwen38_tokenizer.json')
    ap.add_argument('--min',type=int,required=True,help='token 下限（含）')
    ap.add_argument('--max',type=int,required=True,help='token 上限（不含）')
    ap.add_argument('--out',required=True,help='输出 jsonl')
    args=ap.parse_args()
    tok=Tokenizer.from_file(args.tokenizer)
    data=json.load(open(args.data,encoding='utf-8'))
    sel=[]
    for r in data:
        n=len(tok.encode(r['context'],add_special_tokens=False).ids)
        if args.min<=n<args.max:
            o=dict(r); o['_tokens']=n; sel.append(o)
    with open(args.out,'w',encoding='utf-8') as f:
        for o in sel: f.write(json.dumps(o,ensure_ascii=False)+'\n')
    print('selected',len(sel),'->',args.out)

if __name__=='__main__': main()
