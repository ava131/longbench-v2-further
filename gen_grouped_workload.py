#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分组间隔负载：同一 base prompt 按目标间隔重复 N 次，其余位置插入独立 prompt。

例：--group 10:22 --group 5:20 --group 5:25 --repeats 4 --independent 15
= 10 条每 22 条出现一次、5 条每 20、5 条每 25，各重复 4 次，再穿插 15 条永不重复的 prompt。

同一 prompt 的每次重复都基于同一 32k 前缀，后一次追加一句追问（+x tokens）。
"""
import argparse
import json
import os
import statistics
import sys

from tokenizers import Tokenizer
from gen_followup import split_sentences, suffix_text, truncate_tokens


def parse_groups(items):
    out = []
    for it in items:
        cnt, gap = it.split(":")
        out.append((int(cnt), int(gap)))
    return out


def schedule(groups, repeats, n_independent, starts):
    """贪心：每步优先发已到期的复用，否则发独立 prompt；实际间隔会 >= 目标。"""
    pending = []  # (group_idx, base_idx, next_due, done)
    for gi, (cnt, gap) in enumerate(groups):
        for b in range(cnt):
            pending.append([gi, b, starts.get((gi, b), 0), 0])
    total = sum(cnt for cnt, _ in groups) * repeats + n_independent
    rows = []
    indep_left = n_independent
    pos = 0
    while pos < total:
        due = [p for p in pending if p[2] <= pos and p[3] < repeats]
        if due:
            due.sort(key=lambda p: (p[2], p[0], p[1]))
            p = due[0]
            rows.append(("repeat", p[0], p[1], p[3], pos))
            p[3] += 1
            p[2] = pos + groups[p[0]][1]
            if p[3] >= repeats:
                pending.remove(p)
        elif indep_left > 0:
            rows.append(("indep", 0, n_independent - indep_left, 0, pos))
            indep_left -= 1
        else:
            pending.sort(key=lambda p: p[2])
            p = pending[0]
            rows.append(("repeat", p[0], p[1], p[3], pos))
            p[3] += 1
            p[2] = pos + groups[p[0]][1]
            if p[3] >= repeats:
                pending.remove(p)
        pos += 1
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data/data.json")
    p.add_argument("--index", default="data/length_index.json")
    p.add_argument("--tokenizer", default="data/tokenizer.json")
    p.add_argument("--target-tokens", type=int, default=32768)
    p.add_argument("--group", action="append", default=["10:22", "5:20", "5:25"])
    p.add_argument("--repeats", type=int, default=4)
    p.add_argument("--independent", type=int, default=15)
    p.add_argument("--format", choices=["v2", "gsm8k"], default="gsm8k")
    p.add_argument("--lang", choices=["en", "zh"], default="en")
    p.add_argument("--partial", action="store_true")
    p.add_argument("--out", default="ready/grouped_32k.jsonl")
    p.add_argument("--manifest", default="ready/grouped_32k.manifest.json")
    args = p.parse_args()

    groups = parse_groups(args.group)
    n_group = sum(c for c, _ in groups)
    n_total = n_group * args.repeats + args.independent

    if args.partial:
        txt = open(args.data, encoding="utf-8", errors="ignore").read()
        data = json.loads(txt[: txt.rfind("\n  }") + 4] + "\n]")
    else:
        data = json.load(open(args.data, encoding="utf-8"))
    index = {x["_id"]: x for x in json.load(open(args.index, encoding="utf-8"))}
    by_id = {r["_id"]: r for r in data}

    cand = [x for x in index.values() if x["tokens"] >= args.target_tokens]
    cand.sort(key=lambda x: x["tokens"] - args.target_tokens)
    need = n_group + args.independent
    if len(cand) < need:
        sys.exit(f"满足 >= {args.target_tokens} 的样本只有 {len(cand)} 条，需要 {need}")
    picked = cand[:need]

    tok = Tokenizer.from_file(args.tokenizer)
    # 交错起点，避免所有 prompt 同一位置到期
    starts = {}
    off = 0
    for gi, (cnt, gap) in enumerate(groups):
        for b in range(cnt):
            starts[(gi, b)] = off % max(1, gap)
            off += 1

    order = schedule(groups, args.repeats, args.independent, starts)

    records, meta = [], []
    for rank, (kind, gi, b, occ, pos) in enumerate(order):
        if kind == "indep":
            base = picked[n_group + b]
        else:
            base = picked[sum(c for c, _ in groups[:gi]) + b]
        rec = by_id[base["_id"]]
        ctx, ctx_tokens = truncate_tokens(tok, rec["context"], args.target_tokens)
        sents = split_sentences(ctx, args.lang)
        question = rec["question"]
        for k in range(occ):
            question += suffix_text(sents[k], k + 1, args.lang)

        rid = f"{kind[0]}{gi}_{b:02d}_r{occ}" if kind == "repeat" else f"ind_{b:02d}"
        if args.format == "gsm8k":
            prompt = ctx + "\n\n" + question
            records.append({"question": prompt, "answer": rec["answer"]})
            ntok = len(tok.encode(prompt).ids)
        else:
            records.append({
                "_id": rid, "domain": rec.get("domain"),
                "sub_domain": rec.get("sub_domain"), "difficulty": rec.get("difficulty"),
                "length": "medium", "question": question,
                "choice_A": rec["choice_A"], "choice_B": rec["choice_B"],
                "choice_C": rec["choice_C"], "choice_D": rec["choice_D"],
                "answer": rec["answer"], "context": ctx,
            })
            ntok = len(tok.encode(ctx + "\n\n" + question).ids)

        meta.append({"pos": pos, "id": rid, "kind": kind, "group": gi,
                     "base": base["_id"], "occ": occ, "tokens": ntok,
                     "gap_target": groups[gi][1] if kind == "repeat" else None})

    # 实际间隔
    for gi in range(len(groups)):
        poss = sorted(m["pos"] for m in meta if m["kind"] == "repeat" and m["group"] == gi and m["occ"] > 0)
        # 按 base 分组算间隔
        gaps = []
        by_base = {}
        for m in meta:
            if m["kind"] == "repeat" and m["group"] == gi:
                by_base.setdefault(m["base"], []).append(m["pos"])
        for v in by_base.values():
            v.sort()
            gaps += [b - a for a, b in zip(v, v[1:])]
        if gaps:
            print(f"组{gi}: 目标 {groups[gi][1]} | 实际间隔 中位 {statistics.median(gaps)} "
                  f"均值 {sum(gaps)/len(gaps):.1f} 范围 {min(gaps)}-{max(gaps)}", file=sys.stderr)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    json.dump(meta, open(args.manifest, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"写出 {len(records)} 条 -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
