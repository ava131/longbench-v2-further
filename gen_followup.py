#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 LongBench v2 构造“第 1 轮原生 + 后续追加一句话追问”的多轮数据集。

第 t 轮（t>=2）在上一轮 question 末尾追加：
    原文第 (t-1) 句：“...”。这句话在全文中是什么作用？
因此第 2 轮 = 原 32k + 一句话 + 追问，前缀与第 1 轮完全一致。

输出格式：
    v2     : LongBench v2 字段（context/question/choice_A-D/answer/...）
    gsm8k  : 只有 question/answer，question 是完整 prompt
"""
import argparse
import json
import os
import re
import sys

from tokenizers import Tokenizer

BUCKETS = [0, 8192, 16384, 24576, 32768, 40960, 65536, 131072, 10**12]


def length_bucket(n):
    for lo, hi in zip(BUCKETS, BUCKETS[1:]):
        if lo <= n < hi:
            return "short" if hi <= 24576 else ("medium" if hi <= 65536 else "long")
    return "long"


def split_sentences(text, lang):
    # 有些样本的 context 是 {"doc": "..."} 的 JSON 包装，先拆出来
    stripped = text.strip()
    if stripped.startswith("{") and '"doc"' in stripped[:200]:
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict) and isinstance(obj.get("doc"), str):
                text = obj["doc"]
        except Exception:
            pass
    # 去掉开头的 UUID/短行等噪声，避免把 "26b5c67b-..." 当成第一句
    lines = text.lstrip().split("\n")
    while lines:
        first = lines[0].strip()
        if len(first) < 40 or re.fullmatch(r"[0-9a-fA-F-]{32,36}", first):
            lines.pop(0)
        else:
            break
    text = "\n".join(lines)
    pat = r'(?<=[。！？])' if lang == "zh" else r'(?<=[.!?])\s+'
    parts = [x.strip() for x in re.split(pat, text) if x and x.strip()]

    def meaningful(s):
        if len(s) < 40:
            return False
        letters = sum(c.isalpha() for c in s)
        return letters / max(1, len(s)) >= 0.5

    good = [p for p in parts if meaningful(p)]
    return good or parts


def truncate_tokens(tok, text, n):
    ids = tok.encode(text).ids
    if len(ids) <= n:
        return text, len(ids)
    return tok.decode(ids[:n]), n


def suffix_text(sentence, idx, lang):
    s = sentence.strip()
    if len(s) > 300:
        s = s[:300] + "…"
    if lang == "zh":
        return f'\n\n原文第 {idx} 句是：“{s}”。这句话在全文中是什么作用？'
    return f'\n\nThe sentence #{idx} of the text is: "{s}". What role does this sentence play in the whole text?'


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data/data.json")
    p.add_argument("--index", default="data/length_index.json")
    p.add_argument("--tokenizer", default="data/tokenizer.json")
    p.add_argument("--target-tokens", type=int, default=32768)
    p.add_argument("--turns", type=int, default=2)
    p.add_argument("--per-turn", type=int, default=3)
    p.add_argument("--format", choices=["v2", "gsm8k"], default="v2")
    p.add_argument("--lang", choices=["en", "zh"], default="en")
    p.add_argument("--out", default="out/agent_mt_v2.jsonl")
    p.add_argument("--manifest", default=None)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--partial", action="store_true",
                   help="data.json 未下载完时，按最后一个完整对象截断解析")
    args = p.parse_args()

    tok = Tokenizer.from_file(args.tokenizer)
    if args.partial:
        txt = open(args.data, encoding="utf-8", errors="ignore").read()
        pos = txt.rfind("\n  }")
        data = json.loads(txt[: pos + 4] + "\n]")
    else:
        data = json.load(open(args.data, encoding="utf-8"))
    index = {x["_id"]: x for x in json.load(open(args.index, encoding="utf-8"))}

    # 选离目标 token 最近、且不小于目标的样本
    cand = [x for x in index.values() if x["tokens"] >= args.target_tokens]
    cand.sort(key=lambda x: x["tokens"] - args.target_tokens)
    picked = cand[: args.per_turn]
    if len(picked) < args.per_turn:
        sys.exit(f"满足 >= {args.target_tokens} tokens 的样本只有 {len(picked)} 条，不够 {args.per_turn}")

    by_id = {r["_id"]: r for r in data}
    records, manifest = [], []

    per_user = []
    for u, meta in enumerate(picked):
        rec = by_id[meta["_id"]]
        ctx, ctx_tokens = truncate_tokens(tok, rec["context"], args.target_tokens)
        sents = split_sentences(ctx, args.lang)

        question = rec["question"]
        rows = []
        for t in range(1, args.turns + 1):
            if t >= 2:
                question = question + suffix_text(sents[t - 2], t - 1, args.lang)
            rid = f"q{u:02d}_t{t}"

            if args.format == "gsm8k":
                prompt = ctx + "\n\n" + question
                rows.append({"question": prompt, "answer": rec["answer"]})
                n_tokens = len(tok.encode(prompt).ids)
            else:
                rec_out = {
                    "_id": rid,
                    "domain": rec.get("domain"),
                    "sub_domain": rec.get("sub_domain"),
                    "difficulty": rec.get("difficulty"),
                    "length": length_bucket(ctx_tokens),
                    "question": question,
                    "choice_A": rec["choice_A"],
                    "choice_B": rec["choice_B"],
                    "choice_C": rec["choice_C"],
                    "choice_D": rec["choice_D"],
                    "answer": rec["answer"],
                    "context": ctx,
                }
                rows.append(rec_out)
                n_tokens = len(tok.encode(ctx + "\n\n" + question).ids)

            manifest.append({"id": rid, "sample": rec["_id"], "turn": t,
                             "tokens": n_tokens, "context_tokens": ctx_tokens})
        per_user.append(rows)

    records = [per_user[u][t] for t in range(args.turns) for u in range(len(picked))]

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 校验前缀链
    for u in range(len(picked)):
        items = [records[t * len(picked) + u] for t in range(args.turns)]
        for prev, cur in zip(items, items[1:]):
            if args.format == "gsm8k":
                assert cur["question"].startswith(prev["question"]), "前缀链断裂"
            else:
                assert cur["context"] == prev["context"]
                assert cur["question"].startswith(prev["question"]), "前缀链断裂"

    if args.manifest:
        json.dump(manifest, open(args.manifest, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    print(f"写出 {len(records)} 条 -> {args.out}", file=sys.stderr)
    print(f"样本 {len(picked)} 个，每个 {args.turns} 轮，target={args.target_tokens} tokens",
          file=sys.stderr)
    for t in range(1, args.turns + 1):
        chunk = [m for m in manifest if m["turn"] == t]
        avg = sum(x["tokens"] for x in chunk) / len(chunk)
        print(f"  t{t}: {len(chunk)} 条, 平均 {avg:,.0f} tokens", file=sys.stderr)


if __name__ == "__main__":
    main()
