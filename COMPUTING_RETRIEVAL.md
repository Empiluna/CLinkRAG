# 计算机与 AI 文献检索改进与验收

此页记录 `0ec95bd` 阶段的实测。该次尚未排首的九道中文题和方法子集召回下降已在下一轮逐题追踪，最新结果见[中文查找与相似方法复核](RETRIEVAL_FOLLOWUP.md)。

## 实施计划

比较起点是本地分支的 `b0eb8e0`。先记录旧版实际可检索的资料范围、排名、关键调用和耗时，然后分别修改以下环节。

| 环节 | 现状与改动方向 | 验收方法 |
| --- | --- | --- |
| 查找计算机论文 | 随包的 16 篇开放文献服务于跨学科示例。增加可离线查找和引用的计算机会议原摘要，逐篇保留作者、标识、原址和许可。 | 从正常文献查证入口发起查询，校验论文身份、返回的摘录、字符偏移和导出出处。 |
| 文献排序 | 比较中文术语、英文缩写、方法标识和相近题名的表现。不可变文献集合复用索引。 | 用同一候选池测前几名的命中及相关度。把自编题、独立人工判断和非计算机回归分开报告。 |
| 深度研究 | 核查 Semantic Scholar 对指定论文标识的处理，测量补充搜索时重复送入重排模型的摘要数量。 | 固定候选及重排环境，比较选文名次、调用数、实际计时，并单独核验外部服务。 |
| 交付 | 接入本地工作台及 Windows 便携包。 | 运行项目测试，解压启动新版，经 HTTP 核验真实查询与原句。 |

质量和延迟分别报告。首次索引、热查询、外部接口和模型重排各有自己的耗时口径。

## 从哪里开始

打开工作台，在「文献查证」选择「计算机与 AI」，用中文或英文输入问题。例如输入「分布式共识」，点开一条结果，可以核对会议、作者、摘要原句和出版者页面。Markdown 笔记保留出处，RIS 可以导入文献管理器。已有 DOI 或 arXiv 编号并希望生成研究报告时，在「深度研究」的问题里直接带上编号，例如「BERT（DOI 10.18653/v1/N19-1423）的原论文摘要报告了哪些结果？」。

## 检索质量

在同一台机器上从 Git 提取旧版，在独立解释器里运行两版真实的本地查询入口。两版使用完全相同的题目、原文和候选顺序。下表中的首位、前三命中表示用户要找的论文出现在相应位置。固定候选池可以测排序，无法据此推算整个学术网络的检全率。[逐题名次、数据版本与源码散列](evaluation/reports/cs_ai_quality.json)

| 文献查证任务 | 旧版 | 新版 |
| --- | ---: | ---: |
| 24 道中文已知论文题，首位命中 | 6/24 | **15/24** |
| 同一组中文题，前三命中 | 7/24 | **16/24** |
| 其中 16 道用中文描述概念的题，首位命中 | 0/16 | **7/16** |
| 同一组题的英文版，首位命中 | 21/24 | **23/24** |
| 同一组题的英文版，前三命中 | 22/24 | **24/24** |
| CSFCube，50 组专家判断，前十名相关度 nDCG@10 | 0.3945 | 0.3945 |
| LitSearch，100 道英文题，首位 / 前三命中 | 64% / 76% | 64% / 76% |

24 道中英配对题由项目编写，目标与干扰项取自 36 篇真实计算机论文，包含相近模型、方法以及两道编号题。新版增加 93 组中英文术语映射，并区分 C++、C#、B+ tree 和带版本号的模型名。按论文自身的编号核对身份，可以避免另一篇文章仅在摘要里提到该编号就排在原作前面。中文首位命中的绝对增幅为 37.5 个百分点，按题重采样的 95% 区间为 20.8–58.3 个百分点。英文首位多出的两题都是编号查找。中文仍有 9 题未把目标排在第一，逐题结果保留在报告里。

另用外部数据检验泛化。CSFCube 采用背景、方法、结果三个方面的专家标注。LitSearch 从有完整目标元数据的问题中按固定散列抽取 100 题，让各题在相同的 566 篇候选中排序。题目包括作者编写及专家审核的检索问题。这一子集的前十召回率两版均为 86%。以上三组共 198 个场景，新版返回的 1,839 段摘录均能按字符位置取回相同原文，旧版的 1,777 段也全部通过。[CSFCube 数据及评测说明](https://github.com/iesl/CSFCube) · [LitSearch 论文](https://aclanthology.org/2024.emnlp-main.840/)

## 检索耗时

| 实际操作 | 对照 | 优化后 | 如何解读 |
| --- | ---: | ---: | --- |
| 原有 16 篇文献，首次查一次 | 6.482 ms | **3.132 ms** | 每轮清空应用索引，保留系统文件缓存 |
| 同一库连续查 8 个问题，含生成笔记和 RIS | 55.167 ms | **0.784 ms** | 一组 8 次查询的总时间 |
| 临时传入 28 篇 RAG 文献，独立查 4 次 | 53.062 ms | **23.541 ms** | 每次独立索引，适用于临时资料 |
| 新增的 1,052 篇会议摘要，首次检索 | 342.394 ms | **103.506 ms** | 同一新版、同一资料库，比较现场建索引与随包预建索引 |
| 两次补搜，BGE 实际打分的「问题、摘要」对数 | 66 | **28** | 候选增加时复用上一轮已算的分数 |
| 同一补搜案例，模型推理 / 完整选文环节 | 851 / 986 ms | **455 / 591 ms** | 实际 RTX 5060 推理，外部检索与判读使用固定响应 |

前四项是应用计时中位数。公开静态文献复用索引，导入的个人材料按请求处理。预建文件与摘要和分词代码按散列绑定，版本不匹配时从原文重建。五轮交替测试中，1,052 篇预建与现场建索引的 12 组查询得到相同论文、分数和摘录位置。索引已热后，12 次查询分别为 3.608 和 3.317 毫秒，预建收益集中在首次查询。[原有查证入口逐次计时](evaluation/reports/library-reuse-performance.json) · [会议库检索、导出与计时](evaluation/reports/computing-library.json)

补搜速度实验在同一批 28 篇文献上交替跑 5 轮，两版最后选出的 8 篇论文及名次完全一致。GPU 不同批大小产生的最大原始分差为 0.00391。这里的 40.1% 时间下降适用于被测选文环节。外部 API、生成回答和排队时间需要另计。[GPU 逐轮计时](evaluation/reports/deep-reranking-performance.json)

Crossref 对相同查询和候选数量复用 5 分钟内的成功结果，并合并同时发出的相同请求。线上实测查询 `graph neural networks oversmoothing` 首次耗时 1,128 毫秒，再查耗时 3.641 毫秒。HTTP 请求数分别为 1、0，三篇 DOI 及顺序一致。未命中、超时和错误可立即重试。这个例子的首查耗时受网络影响。[实际返回的 DOI 与请求次数](evaluation/reports/computing-library.json)

## 深度研究与外部服务

- **指定原论文。** 用 Semantic Scholar 的批量接口查 Transformer、BERT、LoRA、FlashAttention、MapReduce、PagedAttention，6 个编号全部核实。5 篇有可用摘要，MapReduce 只有书目信息。五个成功的普通主题搜索里有 3 个把目标送入前五，第六次搜索被服务限流。同五个目标按编号查找全部命中。只有用户提供的编号会触发这一环节，进入候选的论文仍需经过相关性和原文检查。[逐篇在线核验](evaluation/reports/deep-reference-live.json) · [Semantic Scholar 接口](https://api.semanticscholar.org/api-docs/graphs)
- **长问题的排序。** 修复内部候选排序沿用外部查询长度校验、丢弃超过 300 字符问题全文的情况。使用真实 BGE 重排 CSFCube 的 50 组候选，nDCG@10 从 0.4200 到 0.4350，前三命中率从 72% 到 76%。16 个短问题各项持平。总体 nDCG 差值的 95% 区间为 −0.0012 至 +0.0320，仍包含零。方法类子集的前十召回率从 0.2717 降到 0.2507，结果类从 0.3878 升到 0.4128。与前面的本地文献查证表使用不同的排序器。[各子集与逐题结果](evaluation/reports/deep-candidate-quality.json)
- **跑完一次真实研究。** 向正式 worker 提交带 DOI 的 BERT 中文问题，使用已配置的论文服务、生成模型和本机重排。84.4 秒完成，3 次关键词查询产生的候选连同按编号查到的文献共 17 篇，最后选中 BERT 原作。正文引用两处均能在这篇论文的原摘要中找到，证据审查已单独保存。这个案例验证了从查找到引用的链路。[完整回答及核验结果](evaluation/reports/deep-computing-live.json)

## 新增论文的来源与覆盖

新增独立的会议摘要库，原有 16 篇跨领域示例仍可从「示例文献」使用。按收录的会议与年份划分，AISTATS 2024 有 547 篇、EACL 2024 有 223 篇、ESA 2025 有 116 篇、DISC 2025 有 66 篇、ECOOP 2025 有 42 篇、ICDT 2025 有 36 篇、ECRTS 2025 有 22 篇。涵盖机器学习与统计、自然语言处理、算法、分布式计算、编程语言、数据库理论和实时系统。每会按固定规则抽一篇用完整题名搜索，七篇都排第一，并验证了来源和导出。其他会议、年份和论文全文需要从相应出版平台获取。

会议库包含署名、原始出版链接与 CC BY 4.0 许可。分发的是从出版方元数据提取并统一空白的摘要文本。EACL 取有摘要的长、短论文，AISTATS 取 PMLR 第 238 卷有摘要的文章，LIPIcs 取 DataCite 明示 CC BY 4.0 的会议论文。[ACL 授权说明](https://aclanthology.org/faq/copyright/) · [AISTATS 第 238 卷](https://proceedings.mlr.press/v238/) · [PMLR 出版协议](https://proceedings.mlr.press/pmlr-license-agreement.html) · [LIPIcs 出版库](https://drops.dagstuhl.de/entities/series/LIPIcs) · [数据刷新脚本](evaluation/refresh_computing.py)

## 复现

在含基线提交 `b0eb8e0` 的 Git 工作副本中，进入项目目录并激活完整 Python 环境。首轮公开评测需联网下载固定语料，LitSearch 读取 Parquet 使用 `pyarrow`。后续可以去掉 `--download` 复用已校验的缓存。质量评测的两个版本使用独立进程。

```powershell
python evaluation/benchmark_cs_ai.py --download --litsearch --output evaluation/reports/cs_ai_quality.json
python evaluation/measure_library_reuse.py --output evaluation/reports/library-reuse-performance.json
python -m evaluation.benchmark_computing_library --output evaluation/reports/computing-library.json
python -m unittest discover -s tests -q
```

本机已安装 BGE 时可复测 GPU。下列最后两条会访问真实服务，最后一条也会调用配置的生成模型。Crossref 实测可向上面的会议库命令加 `--crossref`。变更会议元数据后依次运行 `python -m evaluation.refresh_computing` 和 `python -m evaluation.build_computing_index` 即可更新随包索引。

```powershell
python evaluation/measure_online_reranking.py --device cuda:0 --repetitions 5 --output evaluation/reports/deep-reranking-performance.json
python evaluation/benchmark_deep_candidates.py --device cuda:0 --output evaluation/reports/deep-candidate-quality.json
python evaluation/check_named_papers.py --output evaluation/reports/deep-reference-live.json
python evaluation/verify_deep_run.py --live --case computing --out evaluation/reports/deep-computing-live.json
```

回归覆盖 138 项 Python 测试、72 项浏览器流程检查及 75 项研究过程界面检查。浏览器测试通过本地 HTTP 入口实际搜索会议摘要并导出 RIS。跨领域旧题包含十个领域、16 组中英问题，两种语言各 16 题首位均命中。[浏览器验收代码](tests/fieldwork-browser.cjs) · [Windows 打包与解压验收](WINDOWS_RELEASE.md)

2026 年 11 月 22 日在 Windows x64 上解压发行包、移除系统 Python 路径与模型凭证，通过包内 CMD 启动。HTTP 检查读到了全部 1,052 篇会议库记录的总数，验证了查询结果的原文位置和会议导出，在线 Crossref 查到 3 篇带摘录的论文。另从开发用工作台的 8765 端口实际提交「图神经网络」，成功返回 3 条结果。
