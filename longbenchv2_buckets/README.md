# LongBench v2 长度分桶（Qwen3.8-27B tokenizer）

从 LongBench v2 官方 `data.json`（503 条）中按 **Qwen3.8-27B** 的 tokenizer 切出四组固定长度样本。

| 文件 | 条数 | token 范围 | 目标 |
|---|---:|---|---:|
| `lt32k_1.jsonl` | 1 | 32,535 | < 32k |
| `32k_42.jsonl` | 42 | 32,766 – 32,768 | 32k |
| `36k_42.jsonl` | 42 | 36,864 | 36k |
| `64k_42.jsonl` | 42 | 65,536 | 64k |

## 选样与截断

- 长度用 `Qwen/Qwen3.8-27B` 的 `tokenizer.json` 计算；
- 每个目标长度选 42 条（`lt32k` 选 1 条）**原始长度 ≥ 目标**的样本，取最接近目标的；
- `context` 截断到不超过目标 token 数（字符级二分微调，尽量贴近目标）；
- 四个桶之间样本不重复。

## 字段

保留 LongBench v2 原字段：`_id / domain / sub_domain / difficulty / length / question / choice_A-D / answer / context`，另加：

| 字段 | 含义 |
|---|---|
| `_tokens` | 截断后的 token 数 |
| `_source_tokens` | 原始 context 的 token 数 |

## 说明

- 这是真实 LongBench v2 样本，`answer` / 选项保留原值，可用于准确率评测；
- 截断后的 `context` 是原文前缀，题目/选项未改；
- token 数不含 system prompt 与 chat template。
