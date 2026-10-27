#!/usr/bin/env python3
"""取一条样本，展示构造后 prompt 的首尾（中间省略）。"""
import argparse
import json
import sys

from tokenizers import Tokenizer
from gen_followup import split_sentences, suffix_text, truncate_tokens


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data/data.json")
    p.add_argument("--tokenizer", default="data/tokenizer.json")
    p.add_argument("--target-tokens", type=int, default=32768)
    p.add_argument("--head", type=int, default=420)
    p.add_argument("--tail", type=int, default=700)
    p.add_argument("--partial", action="store_true")
    p.add_argument("--out", default="")
    args = p.parse_args()

    if args.partial:
        txt = open(args.data, encoding="utf-8", errors="ignore").read()
        data = json.loads(txt[: txt.rfind("\n  }") + 4] + "\n]")
    else:
        data = json.load(open(args.data, encoding="utf-8"))

    tok = Tokenizer.from_file(args.tokenizer)
    rec = None
    for r in data:
        if len(tok.encode(r["context"]).ids) >= args.target_tokens:
            rec = r
            break
    if rec is None:
        sys.exit("没有 >= target 的样本")

    ctx, n = truncate_tokens(tok, rec["context"], args.target_tokens)
    sents = split_sentences(ctx, "en")
    q1 = rec["question"]
    q2 = q1 + suffix_text(sents[0], 1, "en")

    t1 = ctx + "\n\n" + q1
    t2 = ctx + "\n\n" + q2

    lines = []
    lines.append(f"样本 _id: {rec['_id']} | domain: {rec.get('domain')} | 截断后 {n:,} tokens")
    lines.append(f"原始 question: {q1}")
    lines.append("")
    lines.append("=" * 30 + " TURN 1（首）" + "=" * 30)
    lines.append(t1[: args.head])
    lines.append("\n……（中间省略 %d 字符）……\n" % (len(t1) - args.head - args.tail))
    lines.append(t1[-args.tail:])
    lines.append("")
    lines.append("=" * 30 + " TURN 2（首）" + "=" * 30)
    lines.append(t2[: args.head])
    lines.append("\n……（中间省略 %d 字符）……\n" % (len(t2) - args.head - args.tail))
    lines.append(t2[-args.tail:])
    text = "\n".join(lines)
    print(text)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
