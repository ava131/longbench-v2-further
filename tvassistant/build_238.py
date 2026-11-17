#!/usr/bin/env python3
"""TV 对话按 PersonaMem-238 的结构生成：218 底座 + 20 条插入（13 独立 + 7 大间隔）。"""
import json, argparse, statistics
from pathlib import Path
from tokenizers import Tokenizer

def load(raw):
    out=[]
    for f in sorted(Path(raw).glob("*.json")):
        d=json.load(open(f,encoding="utf-8"))
        if "text" in d: out.append(d)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--raw41", default="/tmp/tvgen4/raw")
    ap.add_argument("--raw13", default="/tmp/tvgen5/raw")
    ap.add_argument("--schedule", default=str(Path(__file__).with_name("schedule_218.json")))
    ap.add_argument("--out", default="32k_238")
    ap.add_argument("--tokenizer", default="/Users/Admin/Workspace/PersonaMem-further/tokenizer/tokenizer.json")
    args=ap.parse_args()
    tok=Tokenizer.from_file(args.tokenizer)
    d41=load(args.raw41); d13=load(args.raw13)
    d41.sort(key=lambda x:x["id"]); d13.sort(key=lambda x:x["id"])
    print("41-set",len(d41),"13-set",len(d13))
    sched=json.load(open(args.schedule,encoding="utf-8"))
    personas=[]
    for x in sched:
        if x["persona"] not in personas: personas.append(x["persona"])
    mapping={p:d41[i] for i,p in enumerate(personas)}
    body=[x for x in sched if x["pos"]<216]
    tail=[x for x in sched if x["pos"]>=216]
    K=20; indep_n=13; gap_n=7
    slots=[int((i+0.5)*216/K) for i in range(K)]
    gap_slots=set([s for s in slots if s>=45][:gap_n])
    kinds=['g' if s in gap_slots else 'i' for s in slots]
    assert kinds.count('g')==gap_n and kinds.count('i')==indep_n

    ni=0; new_rows=[]
    for k in kinds:
        if k=='i':
            new_rows.append({'kind':'indep','text':d13[ni]['text'],'src':d13[ni]['id']}); ni+=1
        else:
            new_rows.append({'kind':'gap','text':None,'src':None})

    out=[]; si=0
    for i in range(216):
        while si<K and slots[si]==i:
            out.append(('new',si)); si+=1
        out.append(('old',i))
    while si<K: out.append(('new',si)); si+=1

    final=[]; pos_of={}
    for pos,(typ,idx) in enumerate(out):
        if typ=='old':
            x=body[idx]; d=mapping[x['persona']]
            final.append({'kind':'old','persona':x['persona'],'text':d['text'],'src':d['id'],'sched_kind':x['kind']})
            pos_of.setdefault(x['persona'],[]).append(pos)
        else:
            nr=new_rows[idx]
            if nr['kind']=='indep':
                final.append({'kind':'indep','persona':None,'text':nr['text'],'src':nr['src'],'sched_kind':'indep'})
            else:
                cand=[p for p,ps in pos_of.items() if ps and ps[-1]<=pos-40]
                if not cand: raise RuntimeError('no gap candidate')
                p=min(cand, key=lambda p: abs((pos-pos_of[p][-1])-45))
                txt=[r['text'] for r in final if r['persona']==p][-1]
                final.append({'kind':'gap','persona':p,'text':txt,'src':None,'sched_kind':'gap'})
                pos_of[p].append(pos)
    for x in tail:
        d=mapping[x['persona']]
        final.append({'kind':'old','persona':x['persona'],'text':d['text'],'src':d['id'],'sched_kind':x['kind']})

    outdir=Path(args.out); outdir.mkdir(parents=True,exist_ok=True)
    meta=[]
    with (outdir/"longbenchv2.jsonl").open("w",encoding="utf-8") as f2, (outdir/"gsm8k.jsonl").open("w",encoding="utf-8") as fg:
        for i,r in enumerate(final):
            users=[l[5:].strip() for l in r['text'].splitlines() if l.startswith("user:")]
            q=users[-1] if users else ""
            f2.write(json.dumps({"_id":f"tv238-{i:03d}","domain":"TV Assistant","sub_domain":"smart-tv-assistant",
                "difficulty":"easy","length":"long","question":q,"choice_A":"","choice_B":"","choice_C":"","choice_D":"",
                "answer":"","context":r['text']},ensure_ascii=False)+"\n")
            fg.write(json.dumps({"question":r['text'],"answer":""},ensure_ascii=False)+"\n")
            meta.append({"pos":i,"kind":r['kind'],"persona":r['persona'],"source_id":r['src'],
                         "tokens":len(tok.encode(r['text']).ids)})
    json.dump(meta,open(outdir/"requests.meta.jsonl","w",encoding="utf-8"),ensure_ascii=False,indent=1)
    N=len(final)
    print("rows",N,"indep",sum(1 for m in meta if m['kind']=='indep'),"gap",sum(1 for m in meta if m['kind']=='gap'))
    print("head==tail[-2]", final[0]['text']==final[-2]['text'], "| head1==tail[-1]", final[1]['text']==final[-1]['text'])
    pos={}
    for m in meta:
        if m['kind']=='indep' or m['persona'] in (final[-2]['persona'],final[-1]['persona']): continue
        pos.setdefault(m['persona'],[]).append(m['pos'])
    gaps=[b-a for v in pos.values() for a,b in zip(sorted(v),sorted(v)[1:])]
    print("gaps mean %.2f median %.0f sd %.2f | >=40 count %d"%(statistics.mean(gaps),statistics.median(gaps),statistics.pstdev(gaps),sum(1 for g in gaps if g>=40)))

if __name__=="__main__":
    main()
