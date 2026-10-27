#!/usr/bin/env python3
"""下载 LongBench v2 的 data.json 与 Qwen tokenizer 到 data/。"""
import argparse
import os
import sys
import urllib.request

DATA_URL = "https://huggingface.co/datasets/zai-org/LongBench-v2/resolve/main/data.json"
TOK_URL = "https://huggingface.co/Qwen/Qwen3-8B/resolve/main/tokenizer.json"


def fetch(url, out):
    if os.path.exists(out) and os.path.getsize(out) > 0:
        print("已存在，跳过:", out, "(%0.1f MB)" % (os.path.getsize(out) / 1e6))
        return
    print("下载:", url)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with urllib.request.urlopen(url, timeout=600) as r, open(out + ".part", "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    os.replace(out + ".part", out)
    print("完成:", out, "(%0.1f MB)" % (os.path.getsize(out) / 1e6))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-url", default=DATA_URL)
    p.add_argument("--tokenizer-url", default=TOK_URL)
    p.add_argument("--out-dir", default="data")
    args = p.parse_args()
    fetch(args.data_url, os.path.join(args.out_dir, "data.json"))
    fetch(args.tokenizer_url, os.path.join(args.out_dir, "tokenizer.json"))


if __name__ == "__main__":
    main()
