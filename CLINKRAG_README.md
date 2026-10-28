# CLinkRAG：本地实现与使用

2026-10-08，基于 SciRAG 的可运行研究原型。保留原版 SciRAG，并新增跨文献实体链接、带来源的关系抽取、条件检查、图扩展检索和证据路径生成。当前实验结论见 [对照报告](CLINKRAG_COMPARISON.md)：功能跑通，尚未证明跨文献路径和共现模块带来稳定收益。

## 页面使用

在此项目目录执行 `./start-ui.ps1`，打开 <http://127.0.0.1:8765/>。

- **CLinkRAG · 跨文献证据路径**：默认使用随项目保存的 28 篇 RAG 主题论文摘要/片段，支持中文问题。它目前不是全领域在线知识库。
- **SciRAG · 同一固定语料**：调用原版问答流程，将外部检索适配到同一个本地语料库。固定 3 篇种子；流程按问题决定是否继续扩展。
- **SciRAG · 在线论文检索**：保留原有 Semantic Scholar 在线检索流程；其资料范围不同，不用于这次受控组件对比。

“执行过程”显示种子召回、GPU 评分、图扩展、条件检查、被拒绝的连接、候选路径、最终上下文和模型输入输出。“回答与来源”显示引用、原始证据和实际采用的路径；“对照实验”显示本次真实测试结果。历史记录可恢复、导出，不会重新调用 API。

页面种子数默认 3；受控实验固定 5。界面问答和实验均使用 2,500 个 cl100k 分词单位作为上下文预算代理，实际模型计费 token 以 API 返回为准。CLI 普通问答默认预算 5,000。参数和实际路径均记录在输出中。

## 实现流程与代码

1. `clinkrag/core.py`：去重论文，将原文切为不重叠证据窗口，保存字符位置；统计实体窗口频数、两两共现和跨论文出现数。NPMI 结合低频收缩，并要求至少 3 个窗口、2 篇论文。共现仅生成无方向的检索边。
2. `clinkrag/index.py`：模型逐篇抽取实体、作者报告的因果关系、关联关系与条件；第二次模型调用复核。实体提及和关系引文必须能定位到原文，否则剔除。实体按类型与规范名称归并，提取时提供已知词表辅助别名统一；保留每条关系的论文、窗口、原句及位置。落盘 JSON/SQLite 和缓存。
3. `clinkrag/pipeline.py`：BGE 对证据窗口评分取得种子；沿共享实体、关系边和合格共现边限跳数扩展，记录每个证据的进入原因。检索可双向探索，解释路径仍遵守原关系方向。
4. `clinkrag/core.py` 的 `build_paths`：对任务、模型、数据集、指标、设置与桥接状态做保守检查；明确冲突拒绝连接，缺失条件标为未知。只用通过来源检查的 `reported_causal` 关系构建有向路径，最多 3 边；共现边不会升级为因果证据。
5. `pack_context`：将原始证据、路径及可能冲突按统一预算打包，元数据计入预算。保留完整窗口，不用无出处摘要替代原文。
6. `generate`：要求模型仅据所给资料作答，保留条件与不确定性，并引用证据编号。运行后检查编号有效性。编号正确不代表论断已获科学证实。
7. `clinkrag/evaluate.py`：普通 RAG、SciRAG 原版三步贡献筛选、CLinkRAG 及两个消融的组件对照；另跑完整 SciRAG 固定语料适配。自动诊断评分与生成分开记录。

`clinkrag/runtime.py` 复用现有 DeepSeek 和 CUDA BGE；`debug_ui/worker.py` 接入页面；`tests/test_clinkrag.py` 验证计数、方向、条件、预算、来源定位及评分审计等行为。原版 `longans/pipe.py` 的研究算法保留。

## 命令行复现

在项目目录的 PowerShell 中运行，使用现有 `config.local.yaml`，不要将密钥写入命令：

```powershell
$env:PYTHONUTF8 = '1'
# 已有相同版本索引时复用缓存，否则调用模型建图。
.\.venv\Scripts\python.exe -m clinkrag.cli build --output results/clinkrag-build-new
.\.venv\Scripts\python.exe -m clinkrag.cli ask --question "Self-RAG 和 CRAG 如何控制检索质量？" --output results/clinkrag-question-new
# 新目录会重新进行真实生成与自动评分，产生 API 用量。
.\.venv\Scripts\python.exe -m clinkrag.cli compare --output results/clinkrag-comparison-new
# 功能回归，不调用在线模型。
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`compare` 对已有输出目录会续跑而非重跑；请使用新目录比较代码或配置变更后的结果。网页对照标签当前读取 `results/clinkrag-comparison-20261008`，不会自动改成任意新实验。

## 换语料

`--corpus` 接受 UTF-8 JSON：

```json
{"papers":[{"id":"stable-paper-id","title":"Paper title","text":"Original abstract or full text"}]}
```

必须提供真实原文和稳定 ID。当前页面仍固定加载 `evaluation/data/corpus.json`；自定义语料先通过 CLI 构建和问答。`--questions` 格式参考 `evaluation/data/questions.json`，包含问题、必要论文 ID 和评分标准。语料、问题及选择标准应在正式测试前冻结。

## 实现边界

- 这是检索与生成增强，不进行因果效应估计，也不把 A→B、B→C 自动当作已证实的 A→C。
- 关系抽取与复核依赖同一模型；原句定位只能证明存在出处，不能替代专家审查关系含义。
- 本版用 BGE 直接评分小语料全部窗口；尚未实现大规模向量索引、学习式实体消歧或条件对齐模型。
- 语料变动生成新版本快照，复用适用的抽取缓存；尚未实现大型知识库的逐边增量更新。
- 摘要/片段经常缺少实验条件，跨论文连接只能标为不确定。实体粒度粗、限定词丢失、路径预算排序均会影响实际跨文献收益。
- SQLite 是本地快照存储，在线运行读取内存图；它不是独立图数据库服务。当前也没有独立的因果摘要训练模块。

后续优先使用含方法和实验条件的全文证据，人工标注跨篇桥接是否成立，再扩大问题集验证两项算法改动。不要仅通过提高跨篇路径数量来宣称质量改善。
