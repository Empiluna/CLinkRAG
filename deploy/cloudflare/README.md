# Cloudflare Containers 部署

本分支把现有 Python 研究服务放进 Cloudflare Container，入口 Worker 负责访问口令和 `clinkrag.hifuu.space` 路由。默认模型服务保持本地项目当前的 DeepSeek 官方接口与 `deepseek-flash` 模型；在线论文检索沿用 Semantic Scholar API。CPU 版 BGE 重排模型在镜像构建时下载，研究记录和模型设置写入 R2。日常开发仍在 `local` 分支进行。

## 部署前

1. 为账号开通 Workers Paid；Containers 不能在当前免费套餐中运行。
2. 在同一 Cloudflare 账号创建专用 R2 存储桶，例如 `clinkrag-data`，创建仅限这个桶、只授予对象读写权限的 R2 API 凭据。
3. 在此分支运行 `npm ci`，确保 Docker Desktop 的 Linux 引擎已启动。
4. 用 `npx wrangler login` 登录这个 Cloudflare 账号。以下每项均通过交互式 `npx wrangler secret put <名称>` 填入，不写入文件或命令参数：
   - `APP_PASSWORD`：至少 16 字符的网页访问口令，用户名固定为 `admin`。
   - `DEEPSEEK_API_KEY`：当前 DeepSeek API 密钥。
   - `S2_API_KEY`：当前 Semantic Scholar API 密钥。
   - `R2_ACCOUNT_ID`：Cloudflare 账号 ID。
   - `R2_BUCKET_NAME`：专用 R2 存储桶名称。
   - `AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`：该桶的 R2 API 凭据。
5. 运行 `npm run deploy`。`wrangler.jsonc` 会把 Worker 发布到 `clinkrag.hifuu.space`；该域名必须属于当前账号且不能已有冲突的 CNAME 记录。

首次构建会安装 CPU PyTorch 和下载 BGE 权重，时间和镜像体积均较大。部署后检查 `/health`、新建研究、研究结束后的历史记录、重启后的历史保留以及删除，再正式使用。网页使用 HTTPS Basic Auth；所有页面与 API 请求均需口令。不要把本地 `config.local.yaml` 或 `results/` 上传到仓库或镜像。

R2 通过 FUSE 挂载为文件系统。Cloudflare 明确说明这种挂载不具备完整 POSIX 语义；正式上线前必须验证本项目的临时文件替换、追加事件和删除行为。镜像与线上访问尚未在此账号完成实测，不能仅凭部署配置判断研究历史已经可靠持久化。
