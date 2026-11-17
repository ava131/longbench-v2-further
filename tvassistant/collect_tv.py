#!/usr/bin/env python3
"""采集家庭电视智能助手对话，生成 32k token 的数据集。

用法：
    DEEPSEEK_API_KEY=sk-xxx python collect_tv.py --n 20 --out raw --workers 8

说明：
  * 话题来自真实电视助手日志（topics.json）；
  * 同一模型分别扮演“用户”和“电视助手”，逐段续写；
  * 每段约 2-3k tokens，累计到 32,768（允许 +1,000）后停止；
  * 输出 raw/<id>.json，供 assemble.py 转成 jsonl。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
import urllib.request
import concurrent.futures as cf
from pathlib import Path

from tokenizers import Tokenizer

SYS = ("你是一位对话编剧。写家庭电视智能助手和用户的真实对话，只输出对话，"
       "每行一条，格式严格为 `user: ...` 或 `assistant: ...`，不要解释、标题、编号或总结。")

PERSONAS = [
    "一位刚下班的中年爸爸", "一位和父母同住的年轻女生", "一位退休在家的爷爷",
    "一位周末在家的大学生", "一位带孩子的妈妈", "一位喜欢追剧的上班族",
    "一位独居的年轻男生", "一位喜欢看纪录片的老师", "一位爱看养生节目的奶奶",
    "一位喜欢动画片的小学生家长",
]


def api_call(key, messages, max_tokens=3200, temperature=0.95, base_url="https://api.deepseek.com",
             model="deepseek-flash", retries=4):
    body = json.dumps({"model": model, "reasoning_effort": "none", "messages": messages,
                       "max_tokens": max_tokens, "temperature": temperature}).encode()
    req = urllib.request.Request(f"{base_url}/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"})
    last = None
    for attempt in range(retries):
        try:
            d = json.load(urllib.request.urlopen(req, timeout=600))
            return d["choices"][0]["message"]["content"], d["usage"]["completion_tokens"]
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 + attempt * 3)
    raise last


def parse_turns(text):
    turns = []
    for line in text.splitlines():
        m = re.match(r"^\s*(user|assistant)\s*[:：]\s*(.*)$", line, re.I)
        if m:
            turns.append([m.group(1).lower(), m.group(2).strip()])
        elif turns and line.strip() and len(turns[-1][1]) < 2000:
            turns[-1][1] += "\n" + line.strip()
    merged = []
    for role, content in turns:
        content = content.strip()
        if not content:
            continue
        if merged and merged[-1][0] == role:
            merged[-1][1] += "\n" + content
        else:
            merged.append([role, content])
    return merged


def token_count(tok, turns):
    return len(tok.encode("\n".join(f"{r}: {c}" for r, c in turns)).ids)


def build_prompt(topics, persona, seeds, first):
    lines = [f"用户人设：{persona}。"]
    lines.append("真实的电视助手话题素材（用户可能会这样问）：")
    for name, qs in seeds:
        lines.append(f"【{name}】" + "；".join(qs))
    lines.append("把上面这些话题自然地串成一段连续对话，用户会追问、换话题、表达喜好。")
    lines.append("助手回答 2-4 句，中文口语化，像电视上的智能助手。")
    lines.append("必须写满，不要提前结束，不要写总结。")
    return "\n".join(lines)


def gen_one(args, idx, tok, topics):
    rng = random.Random(args.seed + idx)
    names = list(topics)
    rng.shuffle(names)
    chosen = names[:args.topics_per_conv]
    persona = rng.choice(PERSONAS)
    seeds = []
    for name in chosen:
        qs = topics[name]["user"]
        if not qs:
            continue
        seeds.append((name, rng.sample(qs, min(len(qs), rng.randint(2, 3)))))
    turns = []
    chunks = 0
    out = Path(args.out) / f"{idx:02d}.json"
    while token_count(tok, turns) < args.target_tokens and chunks < args.max_chunks:
        if chunks == 0:
            prompt = build_prompt(topics, persona, seeds, True) + "\n至少写 2500 tokens。"
        else:
            tail = "\n".join(f"{r}: {c}" for r, c in turns[-10:])[-1500:]
            remaining = seeds[min(chunks, len(seeds)):]
            extra = build_prompt(topics, persona, remaining or seeds, False) if remaining else ""
            prompt = (f"接着下面这段对话继续往下写，格式不变，不要重复已有内容，不要总结。\n"
                      f"上一段结尾：\n{tail}\n\n{extra}\n至少再写 2000 tokens。")
        try:
            content, n = api_call(args.key, [{"role": "system", "content": SYS},
                                             {"role": "user", "content": prompt}],
                                  max_tokens=args.max_tokens, base_url=args.base_url, model=args.model)
        except Exception as exc:  # noqa: BLE001
            print(f"[{idx:02d}] call failed: {exc}", flush=True)
            break
        new = parse_turns(content)
        if not new:
            break
        turns.extend(new)
        chunks += 1
        json.dump({"id": idx, "persona": persona, "turns": turns}, out.open("w", encoding="utf-8"),
                  ensure_ascii=False)
        print(f"[{idx:02d}] chunk {chunks} +{n} -> {token_count(tok, turns)} tokens", flush=True)

    while len(turns) > 2 and token_count(tok, turns) > args.max_tokens_total:
        turns.pop()
    extra = 0
    while token_count(tok, turns) < args.target_tokens and extra < 10:
        tail = "\n".join(f"{r}: {c}" for r, c in turns[-8:])[-1200:]
        try:
            content, _ = api_call(args.key, [{"role": "system", "content": SYS},
                                             {"role": "user", "content": f"接着写，格式不变，不要重复，不要总结：\n{tail}\n至少 1500 tokens。"}],
                                  max_tokens=args.max_tokens, base_url=args.base_url, model=args.model)
        except Exception:  # noqa: BLE001
            break
        turns.extend(parse_turns(content))
        extra += 1
        while len(turns) > 2 and token_count(tok, turns) > args.max_tokens_total:
            turns.pop()

    text = "\n".join(f"{r}: {c}" for r, c in turns)
    total = len(tok.encode(text).ids)
    json.dump({"id": idx, "persona": persona, "tokens": total, "text": text},
              out.open("w", encoding="utf-8"), ensure_ascii=False)
    print(f"DONE [{idx:02d}] tokens={total} turns={len(turns)}", flush=True)
    return idx, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", default=str(Path(__file__).with_name("topics.json")))
    ap.add_argument("--tokenizer", default="/Users/Admin/Workspace/PersonaMem-further/tokenizer/tokenizer.json")
    ap.add_argument("--out", default="raw")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--target-tokens", type=int, default=32768)
    ap.add_argument("--max-tokens-total", type=int, default=33768)
    ap.add_argument("--max-chunks", type=int, default=40)
    ap.add_argument("--max-tokens", type=int, default=3200)
    ap.add_argument("--topics-per-conv", type=int, default=8)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    ap.add_argument("--model", default=os.environ.get("MODEL", "deepseek-flash"))
    args = ap.parse_args()
    args.key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not args.key:
        raise SystemExit("请设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY")
    Path(args.out).mkdir(parents=True, exist_ok=True)
    tok = Tokenizer.from_file(args.tokenizer)
    topics = json.loads(Path(args.topics).read_text(encoding="utf-8"))
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda i: gen_one(args, i, tok, topics), range(args.n)))
    print("all done", results, flush=True)


if __name__ == "__main__":
    main()
