> 最新状态：2026-10-07 两项 API 和 GPU 完整在线联调已通过，12 项回归测试通过。详见 [S2_API_VALIDATION.md](S2_API_VALIDATION.md)。

# GPU 与 API 验证（2026-10-07）

已将本项目 `RERANKER_DEVICE` 从 `cpu` 改为 `cuda:0`；已填写的密钥保持不变，未在日志中输出。

| 项目 | 结果 |
|---|---|
| 显卡 | NVIDIA GeForce RTX 5060，8GB |
| 驱动 | 595.79 |
| PyTorch | 2.8.0+cu128，CUDA runtime 12.8 |
| CUDA 实算 | GPU 矩阵运算通过；设备 capability 12.0 |
| BGE 真实运行设备 | cuda:0，FP16 |
| BGE 样例评分 | 相关文本 4.66796875；无关文本 -11.015625 |
| 本次 BGE 测试峰值分配显存 | 1093.2 MiB（不包含其他应用显存，不代表所有输入的峰值） |
| 依赖检查 | 72 个包全部兼容 |
| 回归测试 | 8 项全部通过 |
| DeepSeek 真实 API | 成功，JSON 输出解析通过 |
| 真实摘要问答 | 成功，包含三个核心组件、引用 [0] 和匹配的来源 ID |
| Semantic Scholar 在线检索 | 未验证，S2_API_KEY 仍为空 |

BGE 测试使用已有的原版 bge-reranker-v2-m3 权重，并设置 HF_HUB_OFFLINE=1 和 TRANSFORMERS_OFFLINE=1，确认本地 GPU 推理。此测试没有调用付费模型。

DeepSeek 测试使用用户配置的 https://api.deepseek.com 与 deepseek-flash；先验证小型 JSON 请求，再通过原入口运行一次真实论文摘要问答。由于摘要足够回答问题，Gap Critic 返回提前结束，因此该示例没有经过在线追加检索、引文扩展或 BGE 重排。GPU 重排由上述独立真实推理测试验证，不能把两项测试视为完整在线检索链已通过。

真实输出：`results/deepseek-sample-20261007.jsonl`。问题是根据所提供摘要解释 SciRAG 的三个核心组件；回答正确识别自适应检索、引文感知符号推理和大纲引导综合。内容检查只验证该样例，不能代替科研质量评测。

安装脚本、示例配置、运行说明和完整依赖锁文件均已同步到 CUDA 版本。官方安装包 SHA256 为 `0ad925202387f4e7314302a1b4f8860fa824357f9b1466d7992bf276370ebcff`，下载后已核验。

填好 Semantic Scholar 密钥后，可运行 `./run-local.ps1 -Live` 检查 snippet 服务权限，再测试在线检索分支。DeepSeek 与 Semantic Scholar 的密钥用途不同。
