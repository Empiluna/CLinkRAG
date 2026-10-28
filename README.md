# CLinkRAG · 科学前沿导航系统

这是一个面向科学论文的研究工作台：输入研究问题，在线查找论文，筛选证据，生成带来源的回答，并展示研究过程与论文之间的关系。项目基于 [SciRAG](https://github.com/yale-nlp/SciRAG) 扩展；原项目的说明保存在 [SCIRAG_UPSTREAM.md](SCIRAG_UPSTREAM.md)。

## 本地运行

Windows：按 [RUN_LOCAL.md](RUN_LOCAL.md) 安装依赖并运行 `./start-ui.ps1`。默认地址为 `http://127.0.0.1:8765/`。模型与 Semantic Scholar 的 API 密钥写入本地 `config.local.yaml`；该文件、模型缓存和研究历史不会提交到 GitHub。

代码流程、资料范围与使用限制见 [CLINKRAG_README.md](CLINKRAG_README.md)。

## 分支

- `local`：日常开发与本地运行，作为此仓库的默认分支。
- `deploy/cloudflare`：Cloudflare Containers 部署配置，目标域名为 `clinkrag.hifuu.space`。部署参数与步骤见该分支的 `deploy/cloudflare/README.md`。
