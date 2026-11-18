#!/usr/bin/env python3
"""生成 TV 对话：第一句用户话必须与 topics.json 里的 query 完全一致。"""
from __future__ import annotations
import argparse, json, os, random, re, time, urllib.request, concurrent.futures as cf
from pathlib import Path
from tokenizers import Tokenizer

SYS=("你是一位对话编剧。写家庭电视智能助手和用户的真实对话，只输出对话，"
     "每行一条，格式严格为 `user: ...` 或 `assistant: ...`，不要解释、标题、编号或总结。")
PERSONAS=["一位刚下班的中年爸爸","一位和父母同住的年轻女生","一位退休在家的爷爷",
          "一位周末在家的大学生","一位带孩子的妈妈","一位喜欢追剧的上班族",
          "一位独居的年轻男生","一位喜欢看纪录片的老师","一位爱看养生节目的奶奶"]

def call(key, messages, max_tokens=3200, temperature=0.95, base_url="https://api.deepseek.com",
         model="deepseek-flash", retries=4):
    body=json.dumps({"model":model,"reasoning_effort":"none","messages":messages,
                     "max_tokens":max_tokens,"temperature":temperature}).encode()
    req=urllib.request.Request(f"{base_url}/v1/chat/completions",data=body,
        headers={"Content-Type":"application/json","Authorization":f"Bearer {key}"})
    last=None
    for a in range(retries):
        try:
            d=json.load(urllib.request.urlopen(req,timeout=600))
            return d["choices"][0]["message"]["content"], d["usage"]["completion_tokens"]
        except Exception as e:
            last=e; time.sleep(2+3*a)
    raise last

def parse(text):
    turns=[]
    for line in text.splitlines():
        m=re.match(r"^\s*(user|assistant)\s*[:：]\s*(.*)$", line, re.I)
        if m: turns.append([m.group(1).lower(), m.group(2).strip()])
        elif turns and line.strip() and len(turns[-1][1])<2000: turns[-1][1]+="\n"+line.strip()
    merged=[]
    for r,c in turns:
        c=c.strip()
        if not c: continue
        if merged and merged[-1][0]==r: merged[-1][1]+="\n"+c
        else: merged.append([r,c])
    return merged

def toks(tok,turns): return len(tok.encode("\n".join(f"{r}: {c}" for r,c in turns)).ids)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--topics",default=str(Path(__file__).with_name("topics.json")))
    ap.add_argument("--tokenizer",default="/Users/Admin/Workspace/PersonaMem-further/tokenizer/tokenizer.json")
    ap.add_argument("--out",default="/tmp/tvgen6/raw")
    ap.add_argument("--n",type=int,default=50)
    ap.add_argument("--workers",type=int,default=8)
    ap.add_argument("--target",type=int,default=32768)
    ap.add_argument("--max-total",type=int,default=33768)
    ap.add_argument("--max-chunks",type=int,default=40)
    ap.add_argument("--max-tokens",type=int,default=3200)
    ap.add_argument("--seed",type=int,default=7777)
    ap.add_argument("--offset",type=int,default=0)
    ap.add_argument("--id-base",type=int,default=None)
    ap.add_argument("--base-url",default=os.environ.get("BASE_URL","https://api.deepseek.com"))
    ap.add_argument("--model",default=os.environ.get("MODEL","deepseek-flash"))
    args=ap.parse_args()
    args.key=os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not args.key: raise SystemExit("need DEEPSEEK_API_KEY")
    Path(args.out).mkdir(parents=True,exist_ok=True)
    tok=Tokenizer.from_file(args.tokenizer)
    topics=json.load(open(args.topics,encoding="utf-8"))
    pool=[]
    for name,v in topics.items():
        for q in v.get("user",[]): pool.append((name,q))
    rng=random.Random(args.seed); rng.shuffle(pool)
    # 去重 query
    seen=set(); picked=[]
    for name,q in pool:
        if q in seen: continue
        seen.add(q); picked.append((name,q))
        if len(picked)>=args.offset+args.n: break
    if len(picked)<args.offset+args.n: raise SystemExit(f"only {len(picked)} unique queries")

    picked=picked[args.offset:args.offset+args.n]
    def gen(item):
        idx,(topic,query)=item
        idx=idx+(args.id_base if args.id_base is not None else args.offset)
        out=Path(args.out)/f"{idx:03d}.json"
        if out.exists():
            try:
                d=json.load(open(out,encoding="utf-8"))
                if d.get("text") and d.get("tokens",0)>=args.target-2000:
                    print(f"SKIP [{idx:03d}] {d['tokens']}",flush=True)
                    return idx,d["tokens"]
            except Exception:
                pass
        persona=rng.choice(PERSONAS)
        turns=[["user",query]]
        chunks=0
        # 第一轮：用户就是原句
        try:
            content,_=call(args.key,[{"role":"system","content":SYS},
                {"role":"user","content":f"用户第一句固定为：{query}\n请直接写出助手的回答（只写 assistant: 一行或几行）。"}],
                max_tokens=args.max_tokens,base_url=args.base_url,model=args.model)
            at=parse(content)
            if at and at[0][0]=="assistant": turns.append(at[0])
        except Exception as e:
            print("first fail",idx,e,flush=True); return idx,-1
        while toks(tok,turns)<args.target and chunks<args.max_chunks:
            tail="\n".join(f"{r}: {c}" for r,c in turns[-8:])[-1200:]
            msg=(f"接着下面这段对话继续往下写，格式不变，不要重复，不要总结。\n{tail}\n"
                 f"主线话题：{topic}。可以自然联想，但不要换到天气、股票等无关话题。至少 2000 tokens。")
            try:
                content,_=call(args.key,[{"role":"system","content":SYS},{"role":"user","content":msg}],
                               max_tokens=args.max_tokens,base_url=args.base_url,model=args.model)
            except Exception as e:
                print("cont fail",idx,e,flush=True); break
            new=parse(content)
            if not new: break
            turns.extend(new); chunks+=1
            json.dump({"id":idx,"topic":topic,"query":query,"turns":turns},out.open("w",encoding="utf-8"),ensure_ascii=False)
            print(f"[{idx:03d}] chunk {chunks} -> {toks(tok,turns)}",flush=True)
        while len(turns)>2 and toks(tok,turns)>args.max_total: turns.pop()
        text="\n".join(f"{r}: {c}" for r,c in turns)
        json.dump({"id":idx,"topic":topic,"query":query,"tokens":len(tok.encode(text).ids),"text":text},
                  out.open("w",encoding="utf-8"),ensure_ascii=False)
        print(f"DONE [{idx:03d}] {toks(tok,turns)} tokens",flush=True)
        return idx,toks(tok,turns)

    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        res=list(ex.map(gen,list(enumerate(picked))))
    print("all done",res,flush=True)

if __name__=="__main__": main()
