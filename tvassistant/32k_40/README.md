# TV Assistant 32k × 40

40 条独立的中文电视助手对话，每条 32k tokens。

- 单主话题 + 允许联想，不跨到无关话题；
- token：32,957 – 33,768（中位 33,758）
- 轮数：中位约 1,346

文件：

| 文件 | 说明 |
|---|---|
| `longbenchv2.jsonl` | 40 行，`context`=全文，`question`=最后一句用户话 |
| `gsm8k.jsonl` | 40 行，`{"question": 全文, "answer": ""}` |
| `requests.meta.jsonl` | `pos / source_id / persona / tokens / turns / last_user` |
