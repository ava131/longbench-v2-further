# TV Assistant 32k × 230（计算命中率 50%）

- 100 条主体：分组 20/24/26/30，每组出现两次；
- 15 条特殊对：间隔 5×4、10×8、50/100/180；
- 共 230 条，每个 prompt 恰好两次 → **计算命中率 50.0%**；
- 每条第一句用户话来自 issue 的真实 query，逐字一致。

文件：`gsm8k.jsonl`（question=列表样字符串）、`longbenchv2.jsonl`、`requests.meta.jsonl`。
