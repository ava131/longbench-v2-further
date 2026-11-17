#!/usr/bin/env python3
"""统计 JSONL 文件里出现过哪些字段（key），以及每个字段出现在多少条记录里。

用法：
    python field_stats.py -s ready/normal_32k_v2.jsonl
    python field_stats.py -s data.jsonl --depth 1
    python field_stats.py -s data.jsonl --json
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict

PY_TYPES = (str, int, float, bool, type(None), list, dict)


def open_text(path: str):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def walk(obj, prefix, counts, types, depth, max_depth):
    if not isinstance(obj, dict):
        return
    for key, value in obj.items():
        full = f"{prefix}.{key}" if prefix else key
        counts[full] += 1
        types[full][type(value).__name__] += 1
        if isinstance(value, dict) and (max_depth < 0 or depth < max_depth):
            walk(value, full, counts, types, depth + 1, max_depth)


def main() -> int:
    parser = argparse.ArgumentParser(description="统计 JSONL 的字段及出现次数")
    parser.add_argument("-s", "--source", required=True, help="JSONL 文件路径（支持 .gz）")
    parser.add_argument("--depth", type=int, default=1,
                        help="嵌套字典展开深度，默认 1（只看顶层）；0 表示只看顶层，-1 表示无限")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = parser.parse_args()

    counts = Counter()
    types = defaultdict(Counter)
    lines = valid = errors = 0

    try:
        handle = open_text(args.source)
    except OSError as exc:
        print(f"打开失败: {exc}", file=sys.stderr)
        return 1

    with handle:
        for lineno, raw in enumerate(handle, 1):
            raw = raw.strip()
            if not raw:
                continue
            lines += 1
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors += 1
                print(f"跳过第 {lineno} 行：{exc}", file=sys.stderr)
                continue
            if not isinstance(row, dict):
                errors += 1
                print(f"跳过第 {lineno} 行：不是 JSON 对象", file=sys.stderr)
                continue
            valid += 1
            walk(row, "", counts, types, 0, args.depth)

    rows = [{"field": k, "count": v,
             "percent": round(v / valid * 100, 2) if valid else 0.0,
             "types": dict(types[k])}
            for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    if args.json:
        print(json.dumps({"source": args.source, "lines": lines, "valid": valid,
                          "errors": errors, "fields": rows}, ensure_ascii=False, indent=2))
        return 0

    print(f"文件: {args.source}")
    print(f"行数: {lines}  可解析: {valid}  跳过: {errors}  字段数: {len(counts)}")
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
