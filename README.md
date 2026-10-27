# longbench-v2-further

从 **LongBench v2** 构造“第 1 轮原生、第 2 轮起追加一句话追问”的多轮数据集。

- 用 Qwen tokenizer 按 **token**（不是字符/词）精确分批
- 第 1 轮：原始 context（截到目标 token 数）+ 原生 question
- 第 t 轮（t≥2）：在上一轮 question 末尾追加
  `原文第 N 句是：“...”。这句话在全文中是什么作用？`
- 前缀逐字节不变，第 2 轮能命中第 1 轮的整段前缀
- 输出支持 **LongBench v2 字段** 或 **gsm8k 的 question/answer**

## 安装

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 使用

```bash
# 1. 下载数据（data.json 约 465 MB）与 Qwen3 tokenizer
.venv/bin/python download_data.py

# 2. 按 token 长度分类，并选出离 32768 最近的 3 条
.venv/bin/python classify.py --select 3 --target-tokens 32768

# 3. 生成：3 个用户 × 2 轮，v2 格式
.venv/bin/python gen_followup.py --per-turn 3 --turns 2 \
    --format v2 --target-tokens 32768 --out out/agent_mt_v2.jsonl \
    --manifest out/agent_mt_v2.manifest.json

# 4. 生成 gsm8k 格式
.venv/bin/python gen_followup.py --per-turn 3 --turns 2 \
    --format gsm8k --target-tokens 32768 --out out/agent_mt_gsm8k.jsonl
```

`data.json` 太大，已在 `.gitignore` 里排除；用 `download_data.py` 重新下载即可。
如果之前下到一半，默认会跳过已有文件，加 `--force` 重新下；也可以自己用
`curl -C -` 续传。本次实测这条链路只有 30–300 KB/s，465 MB 需要较长时间。

### 下载没完成时

`download_data.py` 是普通 HTTP 下载，网络慢时可以分批拉。若 `data.json` 还没下完，`classify.py --partial`
会按最后一个完整对象截断后解析，先用已有数据把流程跑通：

```bash
.venv/bin/python classify.py --partial --select 3 --target-tokens 32768
```

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--target-tokens` | `32768` | 每条 context 截断到的 token 数 |
| `--turns` | `2` | 轮数 |
| `--per-turn` | `3` | 每轮请求数（也是用户数） |
| `--format` | `v2` | `v2` 输出 LongBench v2 字段；`gsm8k` 只输出 question/answer |
| `--lang` | `en` | 追问语言（`en` / `zh`） |
| `--tokenizer` | `data/tokenizer.json` | Qwen tokenizer（默认 Qwen3-8B，可换本地路径） |
| `--out` | `out/agent_mt_v2.jsonl` | 输出文件 |
| `--manifest` | 无 | 输出每条的 token 数/共享前缀信息 |

## 输出

`v2`：

```json
{"_id":"q00_t2","domain":"...","sub_domain":"...","difficulty":"...",
 "length":"medium","question":"<原生 question + 追加的追问>",
 "choice_A":"...","choice_B":"...","choice_C":"...","choice_D":"...",
 "answer":"B","context":"<截断后的 32k context>"}
```

`gsm8k`：

```json
{"question":"<context + 两轮 question>","answer":"B"}
```

## 已验证

在 `data.json` 前 26 MB（33 条）上跑通：

- 28/33 条 ≥ 32768 tokens
- 第 1 轮 context 截到 32k tokens；第 2 轮 question 以第 1 轮 question 为前缀
- 生成 3 用户 × 2 轮 = 6 条，v2 与 gsm8k 两种格式都通过前缀断言

## 示例产物

`examples/` 下有两份用前 35 条数据生成的 demo（3 用户 × 2 轮）：

- `agent_mt_v2_demo.jsonl`
- `agent_mt_gsm8k_demo.jsonl`

实测：t1 平均 **32,781 tokens**，t2 平均 **32,874 tokens**（每轮 +93 tokens），且
`t2.question.startswith(t1.question)` 成立。

## 注意

- 数据里 `answer` 是 A/B/C/D 字母；追加追问后选项与答案不再匹配，纯压测可忽略
- 换 tokenizer 会改变 token 计数，进而改变选中的样本
- LongBench v2 的 context 最长 2M words，tokenize 全量 503 条需要一些时间
