#!/usr/bin/env python3
"""把 raw/*.json 转成 LongBench v2 / gsm8k 两个 jsonl。"""
import json, glob, hashlib
from pathlib import Path
import argparse
from tokenizers import Tokenizer

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--raw", default="raw")
    ap.add_argument("--out", default="32k_20")
    ap.add_argument("--tokenizer", default="/Users/Admin/Workspace/PersonaMem-further/tokenizer/tokenizer.json")
    args=ap.parse_args()
    tok=Tokenizer.from_file(args.tokenizer)
    rows=[]
    for f in sorted(glob.glob(str(Path(args.raw)/"*.json"))):
        d=json.load(open(f,encoding="utf-8"))
        if "text" not in d: continue
        text=d["text"]; toks=len(tok.encode(text).ids)
        turns=[l for l in text.splitlines() if l.startswith(("user:","assistant:"))]
        users=[l[5:].strip() for l in turns if l.startswith("user:")]
        rows.append((d["id"],text,toks,users[-1] if users else "",len(turns)//2,d.get("persona","")))
    rows.sort()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    with (out/"longbenchv2.jsonl").open("w",encoding="utf-8") as f:
        for i,(cid,text,toks,q,nt,p) in enumerate(rows):
            f.write(json.dumps({"_id":f"tvassist-{i:02d}","domain":"TV Assistant","sub_domain":"smart-tv-assistant",
                "difficulty":"easy","length":"long","question":q,"choice_A":"","choice_B":"","choice_C":"","choice_D":"",
                "answer":"","context":text},ensure_ascii=False)+"\n")
    with (out/"gsm8k.jsonl").open("w",encoding="utf-8") as f:
        for cid,text,toks,q,nt,p in rows:
            f.write(json.dumps({"question":text,"answer":""},ensure_ascii=False)+"\n")
    json.dump([{"pos":i,"source_id":cid,"persona":p,"tokens":toks,"turns":nt,"last_user":q}
               for i,(cid,text,toks,q,nt,p) in enumerate(rows)],
              open(out/"requests.meta.jsonl","w",encoding="utf-8"),ensure_ascii=False,indent=1)
    print("rows",len(rows),"tokens",[r[2] for r in rows])

if __name__=="__main__":
    main()
