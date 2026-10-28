本地网页调试台：运行 `./start-ui.ps1` 后打开 http://127.0.0.1:8765 。支持问题输入、自动初始检索、实时步骤、提示词与响应、历史记录和导出，详见 [UI_GUIDE.md](UI_GUIDE.md)。

> 最新状态：2026-10-07 两项 API 和 GPU 完整在线联调已通过，12 项回归测试通过。详见 [S2_API_VALIDATION.md](S2_API_VALIDATION.md)。

# SciRAG 本地运行（Windows / DeepSeek）

原仓库：https://github.com/yale-nlp/SciRAG

检出的上游版本：`56b0a0894b6a5d117e72d0dc8cd08b39c1267b7e`。

现已增加本地调试前端与 CLinkRAG 算法原型，详见 [CLinkRAG 使用说明](CLINKRAG_README.md) 和 [真实对照报告](CLINKRAG_COMPARISON.md)。原项目命令行入口是 `longans/run.py`；同类启动修复同步到两个短回答分支。下文保留原版 SciRAG 的启动说明。

## 配置

编辑项目根目录的 `config.local.yaml`，填写：

```yaml
MODEL_NAME: deepseek-flash
DEEPSEEK_BASE_URL: https://api.deepseek.com
DEEPSEEK_API_KEY: "在本地填写你的密钥"
DEEPSEEK_THINKING: disabled
S2_API_KEY: "在本地填写 Semantic Scholar 密钥"
RERANKER_DEVICE: "cuda:0"
```

服务和模型参考：<https://api-docs.deepseek.com/guides/json_mode/>。按当前官方文档使用 `deepseek-flash`，模型 ID 可自行更改。该选择并非对论文使用 GPT-4o 的严格复现。

私有配置已加入 `.gitignore`。程序从文件位置寻找配置，不依赖终端当前目录；同名环境变量优先。不要将真实密钥写入原仓库已跟踪的 `config.yaml`。

Semantic Scholar 的普通论文搜索权限不一定等同于 `/snippet/search` 权限，需要实际验证。密钥申请及服务文档：<https://www.semanticscholar.org/product/api>。

## 启动

在此目录打开 PowerShell，依次执行：

```powershell
# 本地依赖和输入格式检查，不调用付费模型
.\run-local.ps1 -Check

# 加载/下载原项目的 BGE 重排权重，并运行真实评分
.\run-local.ps1 -PrepareReranker

# 填好密钥后，检查 DeepSeek JSON 调用和 Semantic Scholar snippet 权限
.\run-local.ps1 -Live

# 运行原项目长回答主流程；结果保存到 results/run-时间.jsonl
.\run-local.ps1
```

首次下载重排权重需要网络、数 GB 磁盘空间；当前使用 PyTorch 2.8.0+cu128，在 RTX 5060 的 cuda:0 上以 FP16 执行重排。若需要退回 CPU，可将 RERANKER_DEVICE 改为 cpu。保留原模型 `BAAI/bge-reranker-v2-m3`，只调整精度、缓存和共享实例以适配本机。模型缓存位于项目 `.cache`。

自定义输入与输出：

```powershell
.\run-local.ps1 -InputFile .\examples\sample.jsonl -OutputFile .\results\my-result.jsonl
```

原始入口也可用：

```powershell
.\.venv\Scripts\python.exe .\longans\run.py --input_file .\examples\sample.jsonl --output_file .\results\answer.jsonl --model_name deepseek-flash
```

输出文件保留原来的追加行为。重复运行请换输出文件名，以免把重复结果误当成新样本。

## 输入与初始检索

输入是 JSONL，每行至少包括一个问题和非空的 `ctxs`：

```json
{"input":"研究问题","ctxs":[{"paperId":"来源ID","title":"论文标题","text":"真实检索片段"}]}
```

随附 `examples/sample.jsonl` 使用用户提供的 SciRAG 论文第一页摘要，用来验证启动。它不是在线检索结果，也不是科研评测数据。

原项目要求预先提供初始检索结果，并未在入口内建立全量论文索引。真实研究问题应先准备检索得到的 `ctxs`（上游推荐 OpenScholar Retriever），之后主流程才按需要继续调用 Semantic Scholar、引文扩展及重排。不要将示例摘要复用于无关问题。

## 修复范围

- 修复未闭合字符串、`cost+= =`、缺失 `List` 导入、未定义计费变量。
- 修复反思提前结束分支返回值不一致、无符号扩展时缺失 rationale、BGE 单个分数返回类型兼容问题。
- 修复嵌套子节点在递归时缺失父节点；保留默认检索深度和原算法提示。
- 使 DeepSeek 和其他 OpenAI 兼容服务可配置；取消内部检索判断与 QASA 路径硬编码 GPT-4o。
- 用 SDK 的有界重试替代无限递归重试；空输出和截断 JSON 明确报错。
- Semantic Scholar 增加请求超时、空节点处理和明确的失败状态；不在检索失败时继续假装已取得证据。
- 同一 pipeline 共用 BGE 实例，并对评分加锁，减少多线程重复加载模型。
- 输入 query/question/input 统一；CLI max_tokens 参数生效。
- 保留上游旧计费估计但不将其用于 DeepSeek；DeepSeek 输出 `cost: null`，不是免费，实际费用以服务商账单为准。

原 Linux Conda 环境含固定 Linux 构建与旧 CUDA 包，未直接用于 Windows。此处提供 CUDA 12.8 版安装方式（无需另装 CUDA Toolkit，需兼容的 NVIDIA 驱动）：

```powershell
.\install-local.ps1
```

`requirements-windows.lock.txt` 固定本次实际安装的全部依赖版本；安装脚本优先使用已验证可达的官方 PyTorch 分发地址。

## 验证

```powershell
.\run-local.ps1 -Test
```

自动化测试的模型回复、检索结果和评分是明确标记的受控测试数据，覆盖提前结束、引文扩展开/关、符号重排、汇总、修订、归因以及接口参数传递。它们不证明真实检索质量。`-PrepareReranker` 验证真实权重，`-Live` 验证真实外部服务，完整运行才能验证一次真实问答。

缺少密钥或服务权限时，不能称为已经完成在线端到端复现。历史安装检查见 `VALIDATION.md`；2026-10-07 的 GPU 与 API 实测见 `GPU_API_VALIDATION.md`。
