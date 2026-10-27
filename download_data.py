#!/usr/bin/env python3
"""下载 LongBench v2 的 data.json 与 Qwen tokenizer 到 data/（支持断点续传）。"""
import argparse
import os
import sys
import urllib.request

DATA_URL = "https://huggingface.co/datasets/zai-org/LongBench-v2/resolve/main/data.json"
TOK_URL = "https://huggingface.co/Qwen/Qwen3-8B/resolve/main/tokenizer.json"


def remote_size(url):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers.get("Content-Length") or 0)


def fetch(url, out, proxy=None):
    total = remote_size(url)
    have = os.path.getsize(out) if os.path.exists(out) else 0
    if total and have == total:
        print("已完成，跳过:", out)
        return
    if have > total:
        print("本地文件比远端大，重新下载:", out)
        have = 0
        os.remove(out)
    mode = "ab" if have else "wb"
    req = urllib.request.Request(url)
    if have:
        req.add_header("Range", f"bytes={have}-")
        print(f"续传: {out} 从 {have/1e6:.1f} MB")
    else:
        print(f"下载: {url}")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy}) if proxy
        else urllib.request.ProxyHandler({})
    )
    with opener.open(req, timeout=600) as r, open(out, mode) as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    got = os.path.getsize(out)
    print(f"完成: {out} ({got/1e6:.1f} MB)")
    if total and got != total:
        print(f"⚠️  大小不一致: 本地 {got} / 远端 {total}，重跑本脚本可续传", file=sys.stderr)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-url", default=DATA_URL)
    p.add_argument("--tokenizer-url", default=TOK_URL)
    p.add_argument("--out-dir", default="data")
    p.add_argument("--proxy", default=None, help="例如 http://127.0.0.1:7890")
    p.add_argument("--force", action="store_true", help="删掉已有文件重新下载")
    args = p.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    data_path = os.path.join(args.out_dir, "data.json")
    tok_path = os.path.join(args.out_dir, "tokenizer.json")
    if args.force:
        for f in (data_path, tok_path):
            if os.path.exists(f):
                os.remove(f)
    fetch(args.data_url, data_path, args.proxy)
    fetch(args.tokenizer_url, tok_path, args.proxy)


if __name__ == "__main__":
    main()
