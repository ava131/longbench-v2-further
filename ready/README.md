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
