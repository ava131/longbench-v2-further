#!/usr/bin/env python3
"""统计数据集里出现过哪些字段（key），以及每个字段出现在多少条记录里。

支持：
  * JSONL：每行一个 JSON 对象
  * JSON：整个文件是一个对象数组（例如 LongBench v2 的 data.json）

用法：
    python field_stats.py -s ready/normal_32k_v2.jsonl
    python field_stats.py -s data/data.json
    python field_stats.py -s data.json --depth 2 --json
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict


def open_text(path: str):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8-sig", errors="replace")
    return open(path, "r", encoding="utf-8-sig", errors="replace")


def walk(obj, prefix, counts, types, depth, max_depth):
    if not isinstance(obj, dict):
        return
    for key, value in obj.items():
        full = f"{prefix}.{key}" if prefix else key
        counts[full] += 1
        types[full][type(value).__name__] += 1
        if isinstance(value, dict) and (max_depth < 0 or depth < max_depth):
            walk(value, full, counts, types, depth + 1, max_depth)


def detect(handle):
    """返回 'json'（对象数组）或 'jsonl'，同时检测 LFS 指针。"""
    head = ""
    while len(head) < 8192:
        chunk = handle.read(8192)
        if not chunk:
            break
        head += chunk
    handle.seek(0)
    stripped = head.lstrip()
    if stripped.startswith("version https://git-lfs"):
        raise SystemExit("这看起来是 Git LFS 指针文件，不是真实数据；请先 git lfs pull。")
    if stripped.startswith("["):
        return "json"
    if stripped and stripped[0] not in "{":
        raise SystemExit(f"无法识别的文件开头：{stripped[:60]!r}")
    return "jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description="统计 JSON/JSONL 的字段及出现次数")
    parser.add_argument("-s", "--source", required=True, help="文件路径（.json / .jsonl，支持 .gz）")
    parser.add_argument("--format", choices=["auto", "jsonl", "json"], default="auto")
    parser.add_argument("--depth", type=int, default=1,
                        help="嵌套字典展开深度，默认 1；0 只看顶层；-1 无限")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = parser.parse_args()

    counts = Counter()
    types = defaultdict(Counter)
    total = valid = errors = 0
    reasons = Counter()

    try:
        handle = open_text(args.source)
    except OSError as exc:
        print(f"打开失败: {exc}", file=sys.stderr)
        return 1

    with handle:
        fmt = args.format if args.format != "auto" else detect(handle)
        if fmt == "json":
            try:
                data = json.load(handle)
            except json.JSONDecodeError as exc:
                print(f"JSON 解析失败: {exc}", file=sys.stderr)
                return 1
            if not isinstance(data, list):
                print("顶层不是数组，也不是 JSONL", file=sys.stderr)
                return 1
            total = len(data)
            for i, row in enumerate(data, 1):
                if not isinstance(row, dict):
                    errors += 1
                    reasons["不是 JSON 对象"] += 1
                    continue
                valid += 1
                walk(row, "", counts, types, 0, args.depth)
        else:
            for lineno, raw in enumerate(handle, 1):
                raw = raw.strip()
                if not raw:
                    continue
                total += 1
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError as exc:
                    errors += 1
                    reasons[f"解析失败: {exc.msg}"] += 1
                    print(f"跳过第 {lineno} 行：{exc}", file=sys.stderr)
                    continue
                if not isinstance(row, dict):
                    errors += 1
                    reasons["不是 JSON 对象"] += 1
                    continue
                valid += 1
                walk(row, "", counts, types, 0, args.depth)

    rows = [{"field": k, "count": v,
             "percent": round(v / valid * 100, 2) if valid else 0.0,
             "types": dict(types[k])}
            for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    if args.json:
        print(json.dumps({"source": args.source, "format": fmt, "records": total,
                          "valid": valid, "errors": errors,
                          "error_reasons": dict(reasons), "fields": rows},
                         ensure_ascii=False, indent=2))
        return 0

    print(f"文件: {args.source}（{fmt}）")
    print(f"记录: {total}  可解析: {valid}  跳过: {errors}  字段数: {len(counts)}")
    if reasons:
        print("跳过原因: " + ", ".join(f"{k}×{v}" for k, v in reasons.most_common()))
    print()
    width = max([len(r["field"]) for r in rows] + [5])
    print(f"{'字段'.ljust(width)}  {'出现次数':>8}  {'占比':>7}  类型")
    print("-" * (width + 40))
    for r in rows:
        type_str = ", ".join(f"{k}×{v}" for k, v in sorted(r["types"].items()))
        print(f"{r['field'].ljust(width)}  {r['count']:>8}  {r['percent']:>6.2f}%  {type_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
