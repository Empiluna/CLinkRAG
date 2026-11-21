# 科研工作台重构与验收报告

2026 年 11 月 21 日，Windows x64。比较起点为 Git 提交 `85d7ca8`。重构立项时记录了启动、科研流程、界面和验证方式的交付口径。[实施前规划](REBUILD_PLAN.md)

## 从旧版本到可交付功能

| 研究者的操作 | 起点版本 | 当前结果 | 实际验收 |
| --- | --- | --- | --- |
| 初次启动 | 无项目虚拟环境时，旧启动脚本退出码 1 | 便携包自带 Python，在可写目录解压、双击启动，自动挑选本机端口 | 单独解压、清空 Python 路径和 API 密钥、端口占用、重复启动、页面与检索请求。[发行验收](WINDOWS_RELEASE.md) |
| 阅读自己的论文 | 默认在线工作流依赖 Semantic Scholar、生成模型及本机 BGE | 导入文本型 PDF、TXT 或粘贴材料。可选择 PDF 页码，查看命中片段并导出 Markdown、RIS | 使用一份真实 12 页 PLOS 出版 PDF，选第 1–2 页，中文提问生成英文检索词，定位到第 2 页，字符偏移逐字相符。[出版 PDF 记录](evaluation/reports/publisher-pdf.json) |
| 查找并核对外部资料 | 科研主页以完整在线研究为入口 | 可立即搜索 Crossref 公开摘要、打开 DOI、查看出处、导出参考文献。中文问题可补充英文检索词 | 教育、城市气候和结构工程 3 个查询均成功，各返回 3 条带 DOI 和原句的记录。此检查衡量服务连通和出处完整性。[查询与返回 DOI](evaluation/reports/workbench-live.json) |
| 从原文整理发现 | 常规入口生成长报告并检查引用编号 | 可以手选片段，只把所选材料送给已配置模型。简报逐条关联引文，检查来源 ID、原词、数值，再让同一模型复核论断 | 用配置的 DeepSeek 服务真实生成和复核 10 个领域的简报。最终 10/10 返回了含目标 DOI 的发现，30 条引文均在相应论文中逐字找到。[完整问题、发现与引文](evaluation/reports/workbench-live.json) |
| 从研究结果转到写作 | 已有历史、报告与引用抽屉 | 首页出现查证入口，报告新增阅读目录，原句可回到资料位置，桌面／手机都能操作导出 | 用 Edge 验证查证、个人材料、PDF、英文词、模型选择交互、导出和引用跳转。浏览器自动化用例与真实远程模型分别运行。[界面截图与测试方法](FIELDWORK_UI.md) |
| 运行原有长研究 | 已有六阶段流程、模型配置及本地历史 | 完整环境继续支持在线选文、图关系、答复与独立证据梳理 | 真实 S2、现有模型服务和本机排序模型运行教育研究，用时 122.5 秒。3 条成功查询共得 16 篇候选，最终选 1 篇。正文引用 2 个片段，均可回到这篇原摘要。[完整运行结果](evaluation/reports/deep-live.json) |

简报复核的两个环节回答不同问题。程序能确定给定片段里确实出现了这段引文。同一模型再次阅读，判断引文能否支撑论断，此环节仍然可能误判。真实模型验收中的 30 条指通过原文定位的引文数。未进行独立专家盲评。

## 两次实测如何改变了实现

第一轮让每个领域各选一道题，保留检索到的前三篇材料，实际调用生成服务。10 个领域中有 8 个产生有原文依据的发现。经济学、计算与语言的题目均找对论文，却只摘出了摘要结尾的未来工作或软件地址。这两个领域没有可以输出的发现。[首轮记录](evaluation/reports/workbench-first-pass.json)

修正后，当中文主题索引命中英文论文而问题用词没有命中具体句子时，系统将 4000 字符以内的完整摘要送入下一步。第二轮两个领域都能读到中段的实质结果。复查教育学问题时，又发现模型将“延迟测验增益高出 50% 至 90%”与“学习效率翻倍”写在同一条发现中，而选中的引文只写了前一个结果。[第二轮记录](evaluation/reports/workbench-context-pass.json)

最终版检查引文中的数字，并针对翻倍表述检查对应措辞。模型复核时可用周围原文识别相反的限定条件，每条结论的细节仍需由其选中的引文支持。重跑同一组问题，教育简报保留了“单独间隔学习组在延迟后测中与对照组相当”的发现和对应引文。这个保守结果也遗漏了摘要中关于后续传统教学组的发现。最终的 10/10 表示每个示例均获得可定位、引用目标论文的结果，完整综述的覆盖率有待独立测量。

## 检索基准和覆盖边界

随包提供 16 篇逐篇标注许可、作者及 DOI 的开放摘要，涉及 10 个领域。自编的中英文已知文献题共 32 道，32/32 首位命中，109 个返回片段的字符位置全部匹配。这部分使用了人工中文主题词。在实际个人文献中，可以手填英文词或让模型翻译问题后自行修改。[逐题结果](evaluation/reports/library_retrieval.json)

另外用 4 套公开 BEIR 独立标注的完整测试集验证词法排序，共 **75,128 份文档、2,677 个问题**。下表比较上版词法信号与新版文献查证排序，衡量相关材料在前十位的位置，数值越高越好。[数据、协议与完整指标](evaluation/RETRIEVAL_VALIDATION.md)

| 公开任务 | 题数 | 原词法 nDCG@10 | 新版 nDCG@10 |
| --- | ---: | ---: | ---: |
| SciFact 科研论断 | 300 | 0.6617 | 0.6650 |
| NFCorpus 生物医学资料 | 323 | 0.3069 | 0.3088 |
| ArguAna 论证检索 | 1,406 | 0.4115 | 0.4252 |
| FiQA 金融问答 | 648 | 0.2360 | 0.2361 |

部分指标出现退步。SciFact 的前三位命中率由 70.0% 降至 69.0%，FiQA 由 32.87% 降至 32.10%。FiQA 前十位的收益也很小。已知文献找得准、金融领域开放问题仍容易漏掉相关文献，这两点需要同时考虑。全领域生成准确率没有可报告的测量值。

## 参考设计与项目盘点

- PaperQA 的“向自己的文献提问并返回带出处的答案”用于确定优先级，形成本文献工作台的个人材料、证据选择与引文入口。[PaperQA 项目](https://github.com/Future-House/paper-qa)
- ALCE 对引文及回答质量的分项衡量用于区分原文定位与论断支持。项目当前采用逐字核对、数量约束和同模型复核。[ALCE 论文](https://aclanthology.org/2023.emnlp-main.398/)
- BEIR 和 SciFact 分别指导独立相关性测试、证据句查找；早期版本的 RRF、MMR 与有限纠正检索仍用于深度流程。[BEIR 项目](https://github.com/beir-cellar/beir) · [SciFact](https://github.com/allenai/scifact) · [深度检索算法设计](ALGORITHM_CROSS_DOMAIN.md)
- 审阅了 Web 服务、任务生命周期、配置与密钥加载、模型目录、前端、默认研究算法、模型适配器、原有短／长回答入口、评测数据与发行脚本。功能重构集中在默认科研工作台和可复用检索代码。历史 SciRAG 实验入口继续由原回归覆盖。

## 复验

在项目根目录的开发环境下执行。完整 Python 测试本轮 **119 项通过**。Edge 通过 **37 项工作台交互检查、41 项研究过程动画检查**。浏览器检查的样例包含固定远程响应，上文的在线实测使用真实服务。线上接口返回和生成措辞可能随时间变化。

```powershell
python -m unittest discover -s tests -q
python -m evaluation.benchmark_library
python -m evaluation.benchmark_public scifact nfcorpus arguana fiqa --mirror huggingface --download
node tests/fieldwork-browser.cjs
node tests/journey-scenes.cjs
```

以下是可选实测，会联网；使用模型的命令会消耗当前服务账户额度。用新的输出路径可以保留本次验收快照。

```powershell
python evaluation/verify_workbench.py --live --out .cache/acceptance/recheck-briefs.json
python evaluation/verify_public_pdf.py --live --out .cache/acceptance/recheck-pdf.json
python evaluation/verify_deep_run.py --live --out .cache/acceptance/recheck-deep.json
python tools/verify_windows.py ../CLinkRAG-Windows-x64.zip
```

扫描件须先 OCR，PDF 页码为文件中的物理页码。个人资料保存在当前页面内存，退出前请导出。便携包可直接运行本地文献查证、公开检索和配置模型后的简报。完整深度研究使用额外安装的排序模型和依赖。[安装与升级](WINDOWS_RELEASE.md)
