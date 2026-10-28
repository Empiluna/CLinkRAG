> 最新状态：2026-10-07 两项 API 和 GPU 完整在线联调已通过，12 项回归测试通过。详见 [S2_API_VALIDATION.md](S2_API_VALIDATION.md)。

> 更新：2026-10-07 已切换 GPU 并通过 DeepSeek API 实测。当前状态见 [GPU_API_VALIDATION.md](GPU_API_VALIDATION.md)。以下保留 2026-10-02 的历史记录。

# 本地验证记录

验证日期：2026-10-02（Asia/Shanghai）。

结论：安装和本地自检完成。尚未调用 DeepSeek 或 Semantic Scholar；两项 API 密钥按用户要求留空。

| 检查 | 实际结果 |
|---|---|
| 上游源码版本 | `56b0a0894b6a5d117e72d0dc8cd08b39c1267b7e` |
| Python | 3.12.14，项目独立 `.venv` |
| 依赖一致性 | `uv pip check`：72 个包，全部兼容 |
| PyTorch | `2.6.0+cpu`；未启用 GPU |
| 核心依赖与入口 | `run-local.ps1 -Check` 通过 |
| 命令行启动 | longans、shortans/scifact、shortans/pubmed 的 `run.py --help` 均成功 |
| 语法检查 | 三个分支编译通过；原提示文件中有不影响运行的转义字符警告 |
| 受控回归测试 | 8 项测试全部通过；其中完整流程同时覆盖符号扩展开启/关闭 |
| 真实 BGE 推理 | 断网模式加载本地权重并完成评分，通过 |
| DeepSeek 与 S2 在线联调 | 未执行：尚无 API 密钥 |
| 真实在线端到端问答 | 未执行，不能视为已完成论文实验复现 |

## 原重排权重

- 模型：`BAAI/bge-reranker-v2-m3`
- 官方版本：`953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`
- `model.safetensors` 大小：2,271,071,852 字节。
- SHA256：`d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286`，与官方元数据一致。
- 本地缓存：`.cache/huggingface/hub/models--BAAI--bge-reranker-v2-m3/`。

实际测试设置 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`，运行 `run-local.ps1 -PrepareReranker`。

测试问题为 “What is retrieval augmented generation?”，两段候选分别是关于 RAG 的说明和烘焙蛋糕的说明。原始相关性分数为 **4.6648945808410645** 与 **-11.013349533081055**。这确认真实模型可本地推理，不代表科研检索质量评测。

## 测试边界

8 项自动化测试使用受控模型回复和检索夹具，覆盖适配器 JSON 参数、提前结束、检索/重排/聚合/修订/归因完整分支、错误 JSON、输入格式、模型传递、检索失败和未知价格处理。没有把这些测试回复当作用户研究答案保存。

两个短回答分支已同步启动修复并验证入口；完整流程回归主要针对本项目使用的 longans 分支。

## 配置后继续

在 `config.local.yaml` 填写密钥后：

```powershell
.\run-local.ps1 -Live
.\run-local.ps1
```

前者验证模型接口与 Semantic Scholar snippet 服务权限，后者对附带的真实论文摘要样例运行主流程。正式研究问题仍需按原项目要求提供初始检索 `ctxs`。详细说明见 `RUN_LOCAL.md`。
