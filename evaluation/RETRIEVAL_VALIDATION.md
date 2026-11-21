# 跨领域文献检索与证据验收

2026 年 11 月 21 日。验收对象为本地文献工作台和复用于在线研究的 BM25 索引。旧版比较起点为 `85d7ca8`。深度模型调用、网页操作和解压安装有单独的验收记录。

## 从论文到功能

[BEIR 论文](https://arxiv.org/abs/2104.08663)和[作者的评测代码](https://github.com/beir-cellar/beir)把文档、查询与相关性标注分开。项目在公开测试集上运行自己的排序器，逐数据集报告名次与漏检。原先每个搜索词都会对同一批文献重新统计词频，现在同一批搜索词共享 BM25 倒排索引。

[SciFact 原论文](https://aclanthology.org/2020.emnlp-main.609/)和[公开实现](https://github.com/allenai/scifact)把定位论文和定位证据句分为两步。工作台保存原文和字符范围，可以复查任意摘录。局部原句有查询词时优先返回该句和相邻上下文。只有中文索引词或题名命中英文论文时，保留 4,000 字符以内的整个摘要，因此结果位于摘要中间时仍可被核对。更长的材料用原语言标题定位一段连续原文。摘要中出现一个词只能说明它可能相关，研究人员仍须阅读引文及限制。

在同一批 16 篇真实摘要上对三个检索词重复运行 15 次，逐查询重建词频与共享索引耗时中位数分别为 16.016 和 5.063 毫秒。全部查询的逐篇 BM25 得分完全相同。该测量针对本机词法计算，在线模型与网络耗时另计。

## 16 篇开放摘要与个人资料

在 PLOS 出版社的 JATS XML 中校验 DOI、作者署名和许可，直接取 `article-meta/abstract`，移除标记并规范空白。16 篇均有 Creative Commons Attribution 授权，逐篇许可链接／原文、作者、题名、DOI、原始 XML URL 与年份在 [文献记录](../clinkrag/data/library.json) 中。个别早年 XML 只有许可文字，其许可链接指向原论文。正式引用请使用作者与 DOI。中文主题词与示例题由本项目编写。

测试涉及历史考古、教育、心理学、经济学、气候与生态、计算与语言、应用数学、材料科学、土木工程和科学传播。中文主题词可检索英语摘要；个人材料也支持 `keywords` 元数据。没有双语词汇的个人英语文献更适合用英文术语查找。没有词项匹配时返回空结果，查不到文献的问题也会在真实词法系统中因通用词重合而产生误匹配。

| 16 篇自带摘要、每种语言 16 道自编已知文献题 | 英文首位命中 | 中文首位命中 |
| --- | ---: | ---: |
| 初始词法信号，题名和摘要 | 16/16 | 0/16 |
| 工作台词法排序，加权题名、中文主题索引、摘要 | 16/16 | 16/16 |

32 题全部在目标领域命中，所有返回摘录都经过 `text[start:end] == quote` 检查。每题目标 DOI、实际名次和检查摘录数见[逐题结果](reports/library_retrieval.json)。这批问题根据收录文献人工选取，也使用了人工中文索引。它验收已知文献发现与原文回查。开放检索的泛化表现需看下面的外部测试。

## 公开、独立标注的英文检索任务

使用 BEIR 官方发布的 corpus、queries、test qrels，对每个有正相关标注的问题在完整数据集检索，过滤与问题相同的文档 ID。保留所有测试问题，不添加中文主题词，不针对这些标注训练。词法基线使用上版的题名一次加正文一次。工作台使用题名两次、正文一次和同一个停用词处理函数。这是**词法组件对照**；旧完整版同时还有 BGE 与搜索服务名次，其端到端效果不能从这个表推断。

| 测试集 | 文档／问题 | 基线 → 工作台 nDCG@10 | 工作台 Hit@3 | 前三条无相关文献 |
| --- | ---: | ---: | ---: | ---: |
| [SciFact 科学论断](https://huggingface.co/datasets/BeIR/scifact) | 5,183／300 | 0.6617 → 0.6650 | 69.00% | 93 |
| [NFCorpus 营养与健康](https://huggingface.co/datasets/BeIR/nfcorpus) | 3,633／323 | 0.3069 → 0.3088 | 57.89% | 136 |
| [ArguAna 论点](https://huggingface.co/datasets/BeIR/arguana) | 8,674／1,406 | 0.4115 → 0.4252 | 41.75% | 819 |
| [FiQA 金融问答](https://huggingface.co/datasets/BeIR/fiqa) | 57,638／648 | 0.2360 → 0.2361 | 32.10% | 440 |

四套公开测试共 75,128 份文档、2,677 个独立问题。FiQA 的前十名排序得分几乎持平，前三条命中率从 32.87% 降到 32.10%。金融问答和反论点检索中，仅凭词项相似仍很容易漏检，不能据此宣称通用科研问题均能获得合格回答。

Hit@3 衡量前三篇是否至少有一篇带正相关标注，MRR@10 衡量十篇内首个相关结果的倒数名次，nDCG@10 计入相关程度和位置，Recall@100 衡量前一百篇覆盖的相关文献比例。并列分数保留原始语料顺序。各项指标、用时、数据快照散列及未命中数见[运行记录](reports/public_retrieval.json)。这次排序在 SciFact 的 Hit@3 从 70% 降到 69%，NFCorpus 的 Recall@100 从 0.2369 降到 0.2344。公测题仍存在明显漏检，尤其在需要区分论点和反论点时。没有进行显著性检验。

## 如何复跑

从项目根目录运行。内置文献与个人材料测试只使用 Python 标准库。

```powershell
python -m evaluation.benchmark_library --output evaluation/reports/library_retrieval.json
python -m unittest discover -s tests -p test_open_library.py -v
```

公开基准首次需要联网和足够的内存。使用含 requests 和 pyarrow 的 Python 环境。程序支持原始大学站点 ZIP 以及 [BEIR 官方 Hugging Face 镜像](https://huggingface.co/BeIR)。本次因大学站点 TLS 连接中断，使用后者。下载的论文、论点和相关性标注只在 `.cache/beir/` 缓存，交付包仅带指标。缓存后去掉 `--download` 即可离线复跑。

```powershell
python -m evaluation.benchmark_public scifact nfcorpus arguana fiqa --mirror huggingface --download --output evaluation/reports/public_retrieval.json
```

重新从出版社下载并校验本地文献库：

```powershell
python evaluation/refresh_library.py
```
