# LongBench v2 — 按 token 长度切分的两个窗口子集

## 1. 来源

- 原始数据：`/tmp/lbv2data.json`（LongBench v2 全量，JSON 数组，**503** 条）。
  本目录所有文件均由该文件派生，**源文件只读，未做任何修改**。
- 每条原始字段：`_id`, `domain`, `sub_domain`, `difficulty`, `length`,
  `question`, `choice_A`, `choice_B`, `choice_C`, `choice_D`, `answer`, `context`。
  其中 `length` 是数据集自带的标签（`short` / `medium` / `long`），**不是**本次使用的
  token 计数依据；长度判定一律以本次计算的 `_tokens` 为准。

## 2. Tokenizer 与计数方法

- Tokenizer：`/tmp/qwen38_tokenizer.json`（Qwen3.8-27B，`tokenizers` 0.23.3，
  BPE + ByteLevel，vocab 248,044，含 33 个 added/special tokens）。
- 计数方式：对每条样本**完整 `context` 字段**单独编码，
  `tokenizer.encode(context, add_special_tokens=False).ids` 的**长度**即为 `_tokens`。
  不加入 BOS/EOS 等特殊 token，不做截断、不做拼接（只计 context，不含 question/choices）。
- 覆盖度：503 条**全部**计算完毕，无一跳过（全量分布：min 10,176 / median 102,244 /
  max 4,523,227 tokens）。

## 3. 窗口定义与结果

两个窗口按 `_tokens` 左闭右开筛选，**保留 context 全文，不截断**：

| 窗口 | 区间（tokens） | 条数 | min | median | max |
|---|---|---|---|---|---|
| A `28k-40k` | 28,672 ≤ t < 40,960 | **37** | 28,889 | 33,321 | 40,801 |
| B `60k-72k` | 61,440 ≤ t < 73,728 | **19** | 62,063 | 68,642 | 72,943 |
| 合并 | A ∪ B | **56** | 28,889 | 35,822.5 | 72,943 |

（`_tokens` 有间隔，故 min 不等于窗口下界；上表 max 均严格小于窗口上界。）

窗口内样本构成：

- A（37）：Single-Document QA 14、Multi-Document QA 9、Long-dialogue History
  Understanding 9、Long In-context Learning 3、Code Repository Understanding 2；
  难度 easy 12 / hard 25。
- B（19）：Multi-Document QA 8、Single-Document QA 6、Long In-context Learning 2、
  Code Repository Understanding 2、Long-dialogue History Understanding 1；
  难度 easy 6 / hard 13。

## 4. 文件清单

| 文件 | 内容 | 条数 | 格式 |
|---|---|---|---|
| `longbenchv2_28k_40k.jsonl` | 窗口 A | 37 | 每行一个 JSON 对象 |
| `longbenchv2_28k_40k.json` | 窗口 A | 37 | JSON 数组 |
| `longbenchv2_60k_72k.jsonl` | 窗口 B | 19 | 每行一个 JSON 对象 |
| `longbenchv2_60k_72k.json` | 窗口 B | 19 | JSON 数组 |
| `longbenchv2_28_40_60_72.jsonl` | A + B 合并（A 在前，B 在后） | 56 | 每行一个 JSON 对象 |
| `longbenchv2_28_40_60_72.json` | A + B 合并 | 56 | JSON 数组 |
| `_stats.json` | 上述统计的机器可读版本 | — | JSON |

全部文件为 **UTF-8 无 BOM**、`ensure_ascii=False`（中文等非 ASCII 字符按原样写入）。

## 5. 字段说明

单窗口文件（A / B）= 原始 12 个字段原样保留 + 1 个新增字段：

- `_tokens` (int)：该条 `context` 用上述 tokenizer 编码得到的 token 数，筛选依据。

合并文件额外多 1 个字段：

- `bucket` (str)：`"28k-40k"` 或 `"60k-72k"`，标记所属窗口。

原始字段含义不变：`_id` 唯一标识；`domain` / `sub_domain` 任务类别；`difficulty`
难度（easy/hard）；`length` 数据集自带长度标签；`question` 题干；`choice_A`–`choice_D`
四个选项；`answer` 正确选项字母（A–D）；`context` 原文全文（未截断、未改写）。

## 6. 自检结果（全部通过）

- 每个文件的条数与筛选结果一致：A=37、B=19、合并=56；`.jsonl` 行数 == `.json` 数组长度。
- 所有 `.json` 均可被 `json.load` 解析（`.jsonl` 每行均可 `json.loads`），UTF-8 解码无错。
- 每条 `_tokens` 落在所属窗口区间内（左闭右开）；独立重算 token 数与 `_tokens` 完全一致。
- 每条 `context` 与源数据逐字符相同（长度与内容均一致，确认未截断），其余原始字段亦未被改写。
- 合并文件按 `bucket` 拆分后与 A、B 单窗口文件逐条相等；`_id` 无重复。

## 7. 复现

```bash
/tmp/pmvenv/bin/python /tmp/build_lb2_windows.py    # 计算 + 生成（约 70s）
/tmp/pmvenv/bin/python /tmp/verify_lb2_windows.py   # 独立自检
```

## 130 条扩增版（重复 + 散列）

`longbenchv2_130.json` / `.jsonl`：从上面 56 条扩到 130 条。

- 每条至少出现 2 次，其中 18 条出现 3 次；
- 顺序打散，同一 `_id` 的最小间隔 6，中位间隔 32；
- 新增 `_copy` 字段表示第几次出现。
