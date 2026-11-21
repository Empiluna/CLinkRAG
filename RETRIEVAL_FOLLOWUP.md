# 中文文献查找与相似方法检索复核

对照版本为 `0ec95bd`，它也是上一版 15/24 首位命中及方法子集 0.2507 召回率对应的提交。本文把「用中文描述一篇已知论文」与「根据方法寻找多篇相似论文」分别统计。前者关心目标的名次，后者关心所有已标注相关的论文里有多少进入前十。

## 实验设计

1. 在 36 篇固定论文上重放原有 24 组中英问题。对中文未排第一的九题查看完整候选、目标和排在前面的论文，保持输入和候选顺序一致。
2. 从 Git 提取 `b0eb8e0`、`0ec95bd` 两个历史版本的候选排序实现。复用同一套真实 BGE 分数，逐项追踪 CSFCube 方法类的前十边界，并区分语义排序、词法排序和最终名次。
3. 独立固定 34 个新意图的中文、英文问法。20 个来自之前 100 题以外的 LitSearch，14 个覆盖随包的 7 个计算机会议。问题、目标、取样规则与评价指标在代码修改前封存，逐题输出在候选方案冻结后揭晓。题单 SHA-256 为 `2781c74149cc59e853cc2990b2b104dc60d7965f76993b5e600b6044f1d2a945`。[冻结题单](evaluation/data/cs_ai_followup_holdout.json)
4. 从浏览器使用的 HTTP 入口复测个人文献查证，检查来源、字符位置、导出，以及无关问题是否产生伪匹配。单独复测离线索引时延、完整回归与 Windows 发行包。
5. 用两批跨论文方法题复核真实输入。第一批用于发现粘贴整篇摘要时的退步。第二批在最终打分前另行封存，每批都从候选中剔除用作问题的论文，两批的原作和候选完全不重叠。

不同题集的候选数量、标签和指标各异。已知论文题可能存在其他也有用的结果，只有相似方法专家集提供多级相关性判断。[CSFCube 论文](https://arxiv.org/abs/2103.12906) · [LitSearch 论文](https://aclanthology.org/2024.emnlp-main.840/)

## 九道中文题分别出了什么问题

同一批 36 篇英文题名和摘要中，上版四题直接返回空列表，两题返回了其他论文但没有目标，三题能找到目标却排在后面。表中的机制线索来自目标文献中真正匹配到的文字。即使找对了论文，回答具体问题时仍需核对原文。例如 BERT 摘要能支持“双向预训练”的描述，单靠定位论文不能证明摘要写明了两个训练任务。[逐题题名、得分、线索与原句校验](evaluation/reports/chinese-lookup-diagnosis.json)

| 要找的论文 | 上版 → 本版名次 | 原因与能区分两篇论文的线索 |
| --- | --- | --- |
| BERT（Q01） | 4 → **1** | 上版只认出“预训练”，RoBERTa 排第一。原作题名中的 *bidirectional* 能区分两者。 |
| RAG（Q04） | 空列表 → **1** | 用自然语言说“从外部知识库检索再生成”，没有命中固定名称。新版能同时匹配知识、检索、序列和生成。 |
| DETR（Q07） | 3 → **1** | 原来只匹配“目标检测”，与 Faster R-CNN 同分。集合预测和匹配提供了更具体的依据。 |
| Mask R-CNN（Q08） | 空列表 → **1** | “实例分割、掩码分支”没连到英文原文。新版可匹配 *instance*、*mask* 和 *branch*。 |
| LoRA（Q10） | 6 → **1** | 只识别“微调、预训练”时 QLoRA 排第一。冻结权重和训练矩阵更能辨认原始方法。 |
| ZeRO（Q15） | 未返回目标 → **1** | 旧规则漏掉英文并列及复数写法。万亿参数、并行和冗余三条线索在目标摘要中同时出现。 |
| Learned Index（Q17） | 未返回目标 → **1** | “数据库”这个大类不能辨认学习型索引。目标摘要写到了数组、位置和索引。 |
| GraphSAGE（Q19） | 空列表 → **1** | 问题描述的是如何给未见过的节点生成表示。新版能找到节点、采样和嵌入的英文表述。 |
| Codex（Q22） | 空列表 → **1** | “文档字符串”对应 *docstrings*，与评估、生成等词结合，能区分代码生成论文和一般语言模型研究。 |

新版从本地的 CC-CEDICT、Google 机器学习术语表及 Python 术语表提取可能的英文表达，查询时才使用。检查英文词形、连续短语和有多少个独立线索出现在同一篇论文里，避免仅凭一个泛词召入大量文献。DOI、arXiv 编号仍按论文本身标识定位。匹配到人工编目主题词的随包文献可以保留完整短摘要，避免一个有歧义的译词截掉关键上下文。[词汇来源、处理和许可](clinkrag/data/CEDICT.md)

## 相似研究方法为何曾经退步

17 道题里，早版到上版有 3 道改善、2 道下降、12 道持平。前十名中的专家相关候选总数其实从 28 增至 29。原指标给每道题相同权重，其中结构探针题只有 2 个正例，少找回 1 篇就使那道题的召回率从 50% 降到 0%，足以拉低全组平均。

用相同的 BGE 分数回放，跌出的两篇相关论文在语义排序里都排第 11。上版给长问题完整文字和短检索词各投一次票。一篇机器翻译论文在摘要不同位置命中了 *NMT*、*phrase*、*source* 等词，压过了真正探测模型句法结构的论文。另一题中，多任务学习论文因共享了实验用语，压过使用相近实验方法的 RNN 论文。

现在，合并连续空白后超过 300 个字符的问题，如果给出具体操作步骤或明确寻找相似方法，可以按摘要同一句中的技术线索评分，再结合短检索词在整篇摘要上的得分。如果粘贴的参考材料同时叙述背景、方法和结果，或者要同时比较多个条件，就保留整篇匹配。短问题也沿用整篇排序。判定使用实际问题文本，候选论文的身份与评测标签均不参与。

| 深度研究排序，同一候选池 | 早版 | 上版 | 本版 |
| --- | ---: | ---: | ---: |
| 17 道方法题，前十平均召回率 | 27.17% | 25.07% | **28.75%** |
| 结构探针原作的名次 | 10 | 17 | **8** |
| RNN 心理语言学实验论文的名次 | 10 | 13 | **10** |
| 50 道专家题，前十平均召回率 | 32.01% | 32.07% | **33.32%** |
| 50 道专家题，前三命中率 | 72% | 76% | 76% |

方法组前十召回率比上版提高约 3.68 个百分点，按题配对的 95% 区间为 0 至 +9.56 个百分点。17 题参与了方案选择，且区间含零。背景组、结果组的排名与上版一致。控制实验测的是候选排序和进入审查池的变化，最终能否引用某篇论文还取决于可取得的原文和后续审查。[前十边界、审查池及分子分母](evaluation/METHOD_RETRIEVAL_FOLLOWUP.md)

## 新问题验证

| 新题与候选池 | 中文首位命中，上版 → 本版 | 中文前三命中，上版 → 本版 | 英文首位命中，上版 → 本版 |
| --- | ---: | ---: | ---: |
| LitSearch，20 个官方问题，2,614 篇候选 | 1 → **6** | 2 → **9** | 14 → 14 |
| 7 个会议，14 个新问题，1,052 篇候选 | 6 → **13** | 6 → **14** | 14 → 14 |

LitSearch 保留官方相关论文标签，中文问题根据英文问题改写。部分题有多个相关目标，中文前十召回率从 20.0% 到 **52.5%**。会议题每题指定一篇原作，题目依据散列抽出的摘要编写。两组都是固定诊断样本。LitSearch 有一题要找通过裁剪特征减小知识图谱补全内存开销的 GreenKGC，目标原排第 9，新版掉出前十。这个例子表明共享“知识图谱”主题仍可能压过真正区分方法和资源约束的细节。[冻结输入、两版逐题排名和区间](evaluation/reports/cs-ai-followup-holdout.json)

首次揭盲时，两组中文首位分别为 6/20、13/14，LitSearch 中文前十召回为 47.5%。随后在独立的个人文献 UI 输入上发现一个问题：同一篇论文中的“语言模型”，会因候选库大小而被算作一条或两条匹配线索。修复后，准入依据来自原问题中实际被覆盖的词，IDF 仍可用于区分已准入论文的名次。表中是最终版本在同一份封存输入上的复测。新题返回的 623 段摘录均与源字符位置一致。

另用 22 道未见过的 LitSearch 英文方法题测试深度研究，前十召回率两版均为 95.45%。其中只有 2 道超过 300 字符。为检验长问题，又用 BIRCO 发布的 DORIS-MAE **全部 60 道长问题、6,634 个问题–候选对**实际计算 BGE 分数。它衡量计算机研究中多个需求的满足程度，官方分数采用模型辅助的分项标注，与 CSFCube 的专家方法相似度是两种指标。[DORIS-MAE 论文](https://proceedings.neurips.cc/paper_files/paper/2023/hash/78f9c04bdcb06f1ada3902912d8b64ba-Abstract-Datasets_and_Benchmarks.html) · [固定 BIRCO 测试集](https://huggingface.co/datasets/mteb/BIRCO-DorisMae-Test/tree/71bd4abb260b3c0e38c51354179e41c16192522a)

对所有长问题一律使用单句匹配的实验版本让 DORIS-MAE 的 nDCG@10 从 0.70017 降至 0.68377。这项回归促使我们限制它的适用范围。正式版本仅 1/60 题触发单句匹配，nDCG@10 为 **0.70013**，最高相关等级论文的前十召回率保持 **40.83%**。这组结果说明保护了多条件问题，尚不能证明方法检索在任意新问题上均有提升。[三种策略对照、配对区间及逐题结果](evaluation/reports/long-needs-followup.json)

### 给出一篇论文，寻找用相似方法的其他论文

第一批 7 题把中文请求与真实论文完整摘要一起提交，每题从另外 43 篇中找方法相似的研究，实际运行 BGE 共 301 对。初次盲测的前十召回从 **97.14% 降至 93.57%**。共形预测一题里，一篇讨论其他方法的论文凭实验叙述中的通用词获得了很高的单句分。真正用随机森林做共形预测的论文从第 9 掉到第 14。修正后，系统保留有背景和结果的参考摘要上下文，这篇论文回到第 9。7 题全部候选的最终顺序与旧版一致。这组已用于诊断，保留两份记录。[原始盲测](evaluation/reports/cross-paper-methods-first-blind.json) · [修正后复测](evaluation/reports/cross-paper-methods.json)

另一批 7 个新问题、47 篇候选在揭晓成绩前另行封存，包含纯方法摘录、中文要求加方法段，以及完整摘要。329 个问题–候选对实际运行 BGE。4 题触发了单句评分。每题前十找回的相关论文比例均持平，前三均有相关论文；排序细节有进有退。

| 新确认集 | 上版 | 定版 |
| --- | ---: | ---: |
| 前十平均召回 | 85.71% | 85.71% |
| 前三有相关论文 | 7/7 | 7/7 |
| 前十排序质量 nDCG@10 | 0.8546 | 0.8583 |

树分解、跨模型蒸馏两题的相关研究整体靠前，多目标老虎机题的排序质量下降。nDCG 差值的配对 95% 区间为 −0.0138 至 +0.0217。两批的标注依据是项目在打分前逐篇给出的操作相似度，尚缺外部专家复核。独立确认支持这批新题的召回持平，对普遍提升仍缺少证据。[冻结问题与逐篇评分依据](evaluation/data/cross_paper_method_confirmation.json) · [完整名次及配对区间](evaluation/reports/cross-paper-method-confirmation.json)

## 实际使用与复现

浏览器给个人文献库每次最多传入 20 篇，因此另在真实 HTTP 入口测试小文献库。每题保留原作与上版前三名干扰项，再按固定散列补齐。九道错题的首位命中从 0/9 到 **9/9**。另用 12 个考古、音乐、植物等问题查找同一组计算机文献，两版都正确返回空列表。原有跨学科 16 组中英文题各自保持 16/16 首位。原来的 100 道 LitSearch 英文题仍为 64% 首位命中、86% 前十召回。[个人库 HTTP 实测](evaluation/reports/personal-lookup-followup.json) · [既有检索集回归](evaluation/reports/cs-ai-followup-regression.json)

更高的命中率有计算成本。36 篇文献的热索引连续查 24 个中文问题，耗时中位数从 1.768 毫秒增至 41.292 毫秒，折合每题从 0.074 到 1.721 毫秒。1,052 篇会议库预建索引的首次查找为 110.6 毫秒。同一组 34 个长问题的 CPU 融合阶段从 24.4 增至 25.8 毫秒，复用了相同的 GPU 分数。[中文逐轮计时](evaluation/reports/chinese-lookup-diagnosis.json) · [会议库计时](evaluation/reports/computing-timing-followup.json)

本地查证在固定的英文论文中可以按中文的功能描述找出目标。在线深度研究还受出版方与检索服务提供的材料影响。实际提交一题中文实时图像匹配问题，不给论文名和 DOI。第一次运行在本机加载模型时遇到 Windows 页面文件不足，结束并行 GPU 评测后重试，3 次检索返回 18 篇候选，其中包含 ORB 原作，9 篇有可用摘要。单独按 DOI 核查时，Semantic Scholar 与 Crossref 都没返回 ORB 的摘要。这次没有生成可核对来源的回答，不能计为回答成功。[线上运行记录](evaluation/reports/method-live-image-matching.json) · [IEEE 原作](https://ieeexplore.ieee.org/document/6126544/)

使用完整开发环境，质量对照需要 Git 历史，Parquet 语料需要 `pyarrow`，深度排序需要 BGE。先下载并校验一次公开语料，之后可离线复跑。命令在项目根目录执行，线上研究单独运行并会调用配置的服务。

```powershell
python evaluation/benchmark_cs_ai.py --baseline 0ec95bd --download --litsearch --output evaluation/reports/cs-ai-followup-regression.json
python evaluation/diagnose_chinese_lookup.py --output evaluation/reports/chinese-lookup-diagnosis.json
python -m evaluation.benchmark_followup_holdout --output evaluation/reports/cs-ai-followup-holdout.json
python evaluation/verify_lookup_followup.py --output evaluation/reports/personal-lookup-followup.json
python evaluation/audit_method_ranking.py --external --output evaluation/reports/method-ranking-followup.json
python evaluation/benchmark_long_needs.py --download --output evaluation/reports/long-needs-followup.json
python -m evaluation.benchmark_cross_paper_methods --output evaluation/reports/cross-paper-methods.json
python -m evaluation.benchmark_cross_paper_methods --dataset confirmation --output evaluation/reports/cross-paper-method-confirmation.json
python -m unittest discover -s tests -q
```

定版通过 146 项 Python 测试和 72 项浏览器检查。Windows 包的解压验收还会用内置解释器从中文方法描述定位英文论文，并核验第一名摘录的原文位置。[打包与验证命令](WINDOWS_RELEASE.md)
