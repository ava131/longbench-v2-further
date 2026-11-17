#!/usr/bin/env python3
"""把 TV 对话按 PersonaMem-218 的精确排布映射成 218 条多轮对话数据集。"""
import json, argparse
from pathlib import Path
from tokenizers import Tokenizer

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--raw", default="/tmp/tvgen4/raw")
    ap.add_argument("--schedule", default=str(Path(__file__).with_name("schedule_218.json")))
    ap.add_argument("--out", default="32k_218")
    ap.add_argument("--tokenizer", default="/Users/Admin/Workspace/PersonaMem-further/tokenizer/tokenizer.json")
    args=ap.parse_args()
    tok=Tokenizer.from_file(args.tokenizer)
    raw=sorted(Path(args.raw).glob("*.json"))
    convs=[]
    for f in raw:
        d=json.load(open(f,encoding="utf-8"))
        if "text" not in d: continue
        convs.append((d["id"], d["text"], len(tok.encode(d["text"]).ids)))
    convs.sort()
    sched=json.load(open(args.schedule,encoding="utf-8"))
    personas=[]
    for x in sched:
        if x["persona"] not in personas: personas.append(x["persona"])
    print("dialogues",len(convs),"personas",len(personas))
    mapping={p:convs[i%len(convs)] for i,p in enumerate(personas)}
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    meta=[]
    with (out/"longbenchv2.jsonl").open("w",encoding="utf-8") as f2, (out/"gsm8k.jsonl").open("w",encoding="utf-8") as fg:
        for i,x in enumerate(sched):
            cid,text,toks=mapping[x["persona"]]
            users=[l[5:].strip() for l in text.splitlines() if l.startswith("user:")]
            q=users[-1] if users else ""
            f2.write(json.dumps({"_id":f"tv218-{i:03d}","domain":"TV Assistant","sub_domain":"smart-tv-assistant",
                "difficulty":"easy","length":"long","question":q,"choice_A":"","choice_B":"","choice_C":"","choice_D":"",
                "answer":"","context":text},ensure_ascii=False)+"\n")
            fg.write(json.dumps({"question":text,"answer":""},ensure_ascii=False)+"\n")
            meta.append({"pos":i,"kind":x["kind"],"source_id":cid,"tokens":toks})
    json.dump(meta,open(out/"requests.meta.jsonl","w",encoding="utf-8"),ensure_ascii=False,indent=1)
    print("written",out,len(meta))

if __name__=="__main__":
    main()
