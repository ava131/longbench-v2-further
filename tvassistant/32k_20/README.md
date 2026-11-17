# TV Assistant 32k × 20

家庭电视智能助手的多轮对话数据集，每条约 **32k tokens**。

## 来源

话题来自真实电视助手日志（issue #2 里贴的 113 条用户 query，17 类话题）：

美国队长、动画片、比利时、养生、提醒吃药、天气、播放歌曲、科普问答、健康、视频、新闻、电视剧、换台、电影、回放、学习、听书。

## 构造

- 20 段独立对话，每段不同用户人设（爸爸/学生/爷爷/妈妈…）和话题组合；
- 用 `collect_tv.py` 逐段续写：每段 2–3k tokens，累计到 **32,768**（允许 +1,000）；
- 对话格式为 `user: ...` / `assistant: ...`，中文口语化；
- 生成模型：**deepseek-flash**（DSH 环境里的 DeepSeek key），不是 qwen3.8-27b；
  如需换成 qwen，设置 `BASE_URL` / `MODEL` 后重跑即可。

## 统计

| 项 | 值 |
|---|---:|
| 条数 | 20 |
| token 最小 / 中位 / 最大 | 32,788 / 33,749 / 33,767 |
| 轮数 | 709 – 1,393 |
| 语言 | 中文 |

## 文件

| 文件 | 说明 |
|---|---|
| `longbenchv2.jsonl` | 20 行，`context`=对话全文，`question`=最后一句用户话，其余为空占位 |
| `gsm8k.jsonl` | 20 行，`{"question": 对话全文, "answer": ""}` |
| `requests.meta.jsonl` | `pos / source_id / persona / tokens / turns / last_user` |

## 复现

```bash
export DEEPSEEK_API_KEY=sk-xxx
python collect_tv.py --n 20 --out raw --workers 8
python assemble.py --raw raw --out 32k_20
```

换成本地 vLLM 的 qwen：

```bash
export BASE_URL=http://<host>:<port> MODEL=qwen3.8-27b OPENAI_API_KEY=EMPTY
python collect_tv.py --n 20 --out raw --workers 4
```

## 说明

- 这是**缓存/长上下文性能测试数据**，`answer`、选项为空占位，不用于准确率评分；
- 对话由模型生成，内容包含剧名、天气、股价等，**数字不保证实时准确**；
- token 数用 Qwen tokenizer 统计，不含 system prompt 与 chat template。
