# 开箱即用的数据

clone 本仓库后**不需要安装任何依赖**，这两个文件可以直接用：

| 文件 | 条数 | 格式 | 大小 |
|---|---|---|---|
| `agent_mt_v2_32k_20x2.jsonl` | 40（20 用户 × 2 轮） | LongBench v2 字段 | ~5.4 MB |
| `agent_mt_gsm8k_32k_20x2.jsonl` | 40 | `question` / `answer` | ~5.3 MB |

- 每条 context 截到 **32,768 tokens**（Qwen tokenizer）
- 第 1 轮：原生 question
- 第 2 轮：在原 question 后追加 `The sentence #1 of the text is: "..." . What role does this sentence play in the whole text?`
- 实测：t1 平均 **32,819 tokens**，t2 平均 **32,886 tokens**（+67）
- 第 2 轮的 prompt 逐字以第 1 轮为前缀，`t2.startswith(t1) == True`

## 直接用

```python
import json
rows = [json.loads(l) for l in open("ready/agent_mt_gsm8k_32k_20x2.jsonl")]
print(rows[0]["question"][-200:])   # 第 1 轮尾部
print(rows[20]["question"][-300:])  # 第 2 轮尾部（多了追问）
```

v2 格式多带 `_id / domain / sub_domain / difficulty / length / choice_A-D / answer / context`。

## 重新生成

```bash
.venv/bin/python gen_followup.py --per-turn 20 --turns 2 \
    --format v2 --target-tokens 32768 --out ready/agent_mt_v2_32k_20x2.jsonl
```

## 4 轮版本

| 文件 | 条数 | 大小 |
|---|---|---|
| `agent_mt_gsm8k_32k_20x4.jsonl` | 80（20 用户 × 4 轮） | ~11 MB |
| `agent_mt_v2_32k_20x4.jsonl` | 80 | ~11 MB |

- 第 1 轮：原生 question
- 第 t 轮（t=2/3/4）：在上一轮 question 后追加第 (t-1) 句 + 追问
- 实测 token：t1 32,819 / t2 32,886 / t3 32,953 / t4 33,014（每轮 +67 左右）
- 每条 t 轮 prompt 都以 t-1 轮为前缀（`startswith` 校验通过）

## 分组间隔版本（95 条）

`grouped_32k_gsm8k.jsonl` + `grouped_32k.manifest.json`

- 第 1 组：10 条 base，目标间隔 22，各出现 4 次
- 第 2 组：5 条 base，目标间隔 20，各出现 4 次
- 第 3 组：5 条 base，目标间隔 25，各出现 4 次
- 另有 15 条完全独立的 prompt，只出现一次

实测实际间隔（因为 95 个位置放 80 次复用 + 15 独立，精确间隔无解）：

| 组 | 目标 | 实际中位 | 实际均值 | 范围 |
|---|---|---|---|---|
| 1 | 22 | 23 | 23.3 | 22–26 |
| 2 | 20 | 23 | 22.9 | 21–25 |
| 3 | 25 | 25 | 25.0 | 21–28 |

同一条 base 的相邻两次出现，后一次 prompt 以前一次为前缀（追加一句追问），校验通过。

## 正态间隔版本（154 条）

`normal_32k_gsm8k.jsonl` / `normal_32k_v2.jsonl` + `normal_32k.manifest.json`

- 20 条 base，每条重复 **7 次** = 140 条
- 14 条完全独立的 prompt，各出现 1 次 = 14 条
- 间隔目标 **N(22, 3)**，实测：均值 **21.98**、标准差 **3.00**、范围 15–32
- 每条重复 = 同一 32k 前缀 + 追加第 k 句追问；同 base 相邻两次前缀链校验通过
- token 范围 32,777–33,403

文件按发送顺序排列；manifest 里有 `pos / kind / base / occ / tokens`。

> 正态间隔版本的完整统计见 [normal_32k_summary.md](normal_32k_summary.md)。
