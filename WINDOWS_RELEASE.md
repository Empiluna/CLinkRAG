# 在 Windows 上使用 CLinkRAG

下载 **CLinkRAG-Windows-x64.zip**，右键选择“全部提取”，把文件夹放在你有写入权限的位置。打开解压后的 CLinkRAG 文件夹，双击 **Start-CLinkRAG.cmd**。启动器会打开默认浏览器，终端里也会显示本机地址。保留终端窗口即可继续使用，结束时按 Ctrl+C。

| 想完成的工作 | 所需条件 |
| --- | --- |
| 用公开样本文献体验检索、阅读原句、导出 Markdown 与 RIS | 解压后的发行包 |
| 在自己的 TXT、可复制文字的 PDF 或粘贴的材料里查找证据 | 解压后的发行包。扫描件需要先用 OCR 识别 |
| 从 Crossref 找公开论文摘要 | 可以访问 Crossref 的网络 |
| 根据已有证据生成研究简报 | 在设置中配置可用模型及密钥，需要连接对应服务 |
| 运行原有深度研究流程 | 完整研究环境、Semantic Scholar 凭证、模型凭证、重排模型 |

**便携环境。** ZIP 随附官方 Windows x64 CPython 3.14.10 嵌入式运行时。普通用户第一次打开页面即可试用随包文献和本地阅读工具。启动器只监听本机的 IPv4 回环地址。默认端口 8765 已被其他应用占用时，它会自动使用空闲端口。双击同一目录的启动器会打开当前会话。不同目录各自保存设置与历史。

**存储位置。** 首次写入的设置保存在项目根目录的 `config.local.yaml`。深度研究记录存放在 `results/web-runs`。关闭浏览器页面后，服务可以继续运行。停止服务后将整个项目目录移动到其他位置即可携带本地资料。

**升级到完整研究环境。** 在电脑上安装 uv，确保能够下载 Python 3.12、PyTorch 依赖和重排模型。使用 PowerShell 在解压目录执行下列命令。现有完整安装脚本使用 CUDA 12.8 版 PyTorch。首次大模型下载需要额外磁盘和网络。阅读与 Crossref 检索均可直接使用便携运行时。

```powershell
.\install-local.ps1
```

在“设置”中配置模型商、模型和论文检索密钥，按电脑的设备选择 CPU 或可用的 CUDA 设备。使用下列命令下载并验证重排模型。关闭当前服务，再双击启动器，它会优先采用同目录的完整 `.venv` 环境。完整环境配置见 [本地运行说明](RUN_LOCAL.md)。

```powershell
.\run-local.ps1 -PrepareReranker
```

## 校验发行包

本发行包附有同名 `.sha256` 文件。下载后可以在文件所在目录运行下列命令，比对输出与配套校验文件。包内的 `FILES.sha256.json` 列有每一个打包文件的摘要。

```powershell
Get-FileHash .\CLinkRAG-Windows-x64.zip -Algorithm SHA256
```

## 开发者构建和验收

先配置项目的完整开发环境，确保当前版本代码与文档已加入 Git 索引，然后在仓库根目录执行下列命令。首轮发行构建会下载固定版本的 CPython 和 pypdf，并与预置 SHA-256 比对。构建器从已锁定的环境复制 PyYAML、Requests 及其 HTTP 依赖的纯 Python 模块、CA 数据和各自许可证。运行 ZIP 中的程序无需下载这些依赖。

```powershell
.\.venv\Scripts\python.exe tools/build_windows.py
.\.venv\Scripts\python.exe tools/verify_windows.py ..\CLinkRAG-Windows-x64.zip
```

发行验收会在含中文与空格的临时路径实际解压，逐项验证文件摘要，清除模型密钥并从 PATH 移除 Python，再启动真正的 CMD 入口。检查覆盖端口冲突、重复启动、旧命令行入口复用、首页、设置、空历史、离线检索与字符偏移、文本 PDF 页码和两种导出。验收使用 `--no-browser` 读取实际 HTTP 响应。加上 `--online` 会额外执行一次真实 Crossref 查询。浏览器视觉与交互验收见项目总报告。

发行包面向 **Windows x64**。本次测试环境为 Windows x64 主机上的全新目录，使用包内解释器和隔离 PATH。这些结果覆盖所列操作，其他系统版本需要在目标机器复验。

在旧版提交 `85d7ca8`，把原 `start-ui.ps1` 放进一个没有 `.venv` 的独立目录实际执行，进程以代码 1 退出并报告 “Missing .venv”。新版包在相同的无虚拟环境条件下完成真实文献查询与导出。旧版 PowerShell 命令也可以使用发行包随附的解释器。

## 随包运行时来源

| 组件 | 版本与来源 |
| --- | --- |
| CPython | [Python 官方 3.14.10 发行页](https://www.python.org/downloads/release/python-31410/)，Windows embeddable package (64-bit)，SHA-256 `90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159`。许可证随包位于 `runtime/LICENSE.txt` |
| pypdf | [PyPI 官方 6.21.4 发行页](https://pypi.org/project/pypdf/6.21.4/)，通用 Python wheel，SHA-256 `33e4fb41ca352810eb4e9838aa0d82d6888a5f8bf682f43e99cce5faa666255c` |
| 其余 Python 库 | 版本见项目的 [Windows 依赖锁](requirements-windows.lock.txt)。每个库的元数据和上游许可证随包位于 `runtime/vendor/*.dist-info` |
