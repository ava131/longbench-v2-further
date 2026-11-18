#!/usr/bin/env python3
import json, glob, re, statistics
from pathlib import Path

def parse_text(t):
    turns=[]
    for line in t.splitlines():
        m=re.match(r'^(user|assistant)\s*[:：]\s*(.*)$', line.strip(), re.I)
        if m: turns.append({'content':m.group(2).strip(),'role':m.group(1).lower()})
        elif turns and line.strip(): turns[-1]['content']+='\n'+line.strip()
    return turns

def load():
    ds=[]
    for f in sorted(glob.glob('/tmp/tvgen6/raw/*.json')):
        d=json.load(open(f,encoding='utf-8'))
        if d.get('text') and d.get('tokens',0)>30000: ds.append((d['id'],d['text']))
    ds.sort(); return ds

def build_main(groups, prompts):
    seq=[]; it=iter(prompts)
    for g in groups:
        grp=[next(it) for _ in range(g)]
        seq.extend(grp); seq.extend(grp)
    return seq

def insert_pairs(seq, specials):
    L=len(seq); n=len(specials)
    for k,(pid,d) in enumerate(specials):
        p=int((k+0.5)*L/(n+1))
        seq.insert(p, pid)
        q=min(p+d+1, len(seq))
        seq.insert(q, pid)
        L=len(seq)
    return seq

def append_gap(seq, d):
    L=len(seq)
    if L<=d: return
    pos=L-d
    pid=seq[pos]
    # 确保这是该 prompt 的最后一次出现
    if pid in seq[pos+1:]:
        return
    seq.append(pid)

def gaps(seq):
    pos={}
    for i,p in enumerate(seq): pos.setdefault(p,[]).append(i)
    out=[]
    for v in pos.values():
        v.sort(); out += [b-a for a,b in zip(v,v[1:])]
    return out

def emit(seq, dialogs, outdir):
    d=Path(outdir); d.mkdir(parents=True,exist_ok=True)
    meta=[]
    with (d/'gsm8k.jsonl').open('w',encoding='utf-8') as fg, (d/'longbenchv2.jsonl').open('w',encoding='utf-8') as fv:
        for i,pid in enumerate(seq):
            text=dialogs[pid]
            turns=parse_text(text)
            s=json.dumps(turns,ensure_ascii=False,separators=(',',':'))
            fg.write(json.dumps({'question':s,'answer':''},ensure_ascii=False)+'\n')
            fv.write(json.dumps({'_id':f'tv-{i:04d}','domain':'TV Assistant','sub_domain':'smart-tv-assistant',
                'difficulty':'easy','length':'long','question':turns[-1]['content'] if turns else '',
                'choice_A':'','choice_B':'','choice_C':'','choice_D':'','answer':'','context':s},ensure_ascii=False)+'\n')
            meta.append({'pos':i,'dialogue_id':pid})
    json.dump(meta,open(d/'requests.meta.jsonl','w',encoding='utf-8'),ensure_ascii=False,indent=1)
    g=gaps(seq)
    from collections import Counter
    print(outdir,'rows',len(seq),'gaps',len(g),'mean %.2f median %.0f'%(statistics.mean(g),statistics.median(g)))
    print('  hist', dict(sorted(Counter(g).items())))

if __name__=='__main__':
    ds=load(); dialogs={i:t for i,t in ds}; ids=[i for i,_ in ds]
    print('dialogs',len(ids))
    # 50%: 100 主体 + 15 特殊 = 230 条
    p50=ids[:100]
    seq50=build_main([20,24,26,30], p50)
    specials50=[(ids[100+k],d) for k,d in enumerate([5,5,5,5,10,10,10,10,10,10,10,10,50,100,180])]
    seq50=insert_pairs(seq50, specials50)
    for d in (180,100,50): append_gap(seq50,d)
    emit(seq50, dialogs, '32k_230_hit50')
    # 30%: 5 块 × (26 首次 + 12 重复) + 4 特殊 = 198 条
    seq30=[]; base=0
    for b in range(5):
        grp=ids[base:base+26]; base+=26
        seq30.extend(grp); seq30.extend(grp[:10])
    specials30=[(ids[130+k],d) for k,d in enumerate([5,10,50,180])]
    seq30=insert_pairs(seq30, specials30)
    for d in (180,100,50): append_gap(seq30,d)
    emit(seq30, dialogs, '32k_198_hit30')
