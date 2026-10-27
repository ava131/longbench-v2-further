#!/usr/bin/env python3
"""用 tokenizer 统计 LongBench v2 每条样本的 token 长度并分桶。

输出 data/length_index.json；可选输出 data/selection.json（离目标 token 数最近的 N 条）。
"""
import argparse
import json
import os
import statistics

from tokenizers import Tokenizer

BUCKETS = [0, 8192, 16384, 24576, 32768, 40960, 65536, 131072, 10**12]


def bucket_of(n):
    for lo, hi in zip(BUCKETS, BUCKETS[1:]):
        if lo <= n < hi:
            return f"[{lo//1024}k, {hi//1024}k)"
    return "?"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data/data.json")
    p.add_argument("--tokenizer", default="data/tokenizer.json")
    p.add_argument("--out", default="data/length_index.json")
    p.add_argument("--selection", default="data/selection.json")
    p.add_argument("--target-tokens", type=int, default=32768)
    p.add_argument("--select", type=int, default=0, help="选出多少条（0 不选）")
    p.add_argument("--min-tokens", type=int, default=0)
    p.add_argument("--max-tokens", type=int, default=10**12)
    p.add_argument("--limit", type=int, default=0, help="只处理前 N 条（调试）")
    p.add_argument("--partial", action="store_true",
                   help="data.json 还没下载完时，按最后一个完整对象截断后解析")
    args = p.parse_args()

    tok = Tokenizer.from_file(args.tokenizer)
    if args.partial:
        txt = open(args.data, encoding="utf-8", errors="ignore").read()
        pos = txt.rfind("\n  }")
        if pos < 0:
            raise SystemExit("没有找到完整对象，文件太小")
        data = json.loads(txt[: pos + 4] + "\n]")
        print("partial 模式：解析出", len(data), "条（文件未下载完）", flush=True)
    else:
        data = json.load(open(args.data, encoding="utf-8"))
    if args.limit:
        data = data[: args.limit]
    print("样本数:", len(data), flush=True)

    index = []
    for i, rec in enumerate(data):
        toks = len(tok.encode(rec["context"]).ids)
        index.append({
            "_id": rec["_id"],
            "domain": rec.get("domain"),
            "sub_domain": rec.get("sub_domain"),
            "difficulty": rec.get("difficulty"),
            "tokens": toks,
            "words": len(rec["context"].split()),
        })
        if (i + 1) % 25 == 0:
            print("  已处理", i + 1, flush=True)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    json.dump(index, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    lens = [x["tokens"] for x in index]
    print("\n总样本 %d | token 中位 %s | 平均 %s | 最大 %s" % (
        len(lens), f"{statistics.median(lens):,.0f}",
        f"{sum(lens)/len(lens):,.0f}", f"{max(lens):,}"))
    from collections import Counter
    cnt = Counter(bucket_of(n) for n in lens)
    for lo, hi in zip(BUCKETS, BUCKETS[1:]):
        b = f"[{lo//1024}k, {hi//1024}k)" if hi < 10**12 else f"[{lo//1024}k, +inf)"
        if b in cnt:
            print(f"  {b:>18}: {cnt[b]:3d}")

    lo_t = max(args.min_tokens, args.target_tokens) if args.select else args.min_tokens
    cand = [x for x in index if lo_t <= x["tokens"] <= args.max_tokens]
    print(f"\n在 [{lo_t:,}, {args.max_tokens:,}] 内: {len(cand)} 条")
    if args.select:
        cand.sort(key=lambda x: abs(x["tokens"] - args.target_tokens))
        sel = cand[: args.select]
        json.dump(sel, open(args.selection, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("已选 %d 条，token 范围 %s ~ %s -> %s" % (
            len(sel), f"{sel[-1]['tokens']:,}", f"{sel[0]['tokens']:,}", args.selection))


if __name__ == "__main__":
    main()
