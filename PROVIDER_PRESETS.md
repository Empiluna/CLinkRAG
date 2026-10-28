# 具体服务预设与 Claude 原生支持

官方文档核对日期：2026-10-19。预设只填入配置，不代表账号已开通模型。用户现有配置和密钥未被开发测试改写。

| 服务 | 预设模型 ID | 默认 Base URL |
| --- | --- | --- |
| Claude / Anthropic | `claude-sonnet-5-5`、`claude-haiku-5-5`、`claude-opus-5-5`、`claude-fable-5-1`、`claude-sonnet-5`、`claude-opus-4-6`、`claude-sonnet-4-6`、`claude-haiku-4-5` | `https://api.anthropic.com` |
| DeepSeek | `deepseek-flash`、`deepseek-v4-pro` | `https://api.deepseek.com` |
| OpenAI | `gpt-6.1-sol`、`gpt-6-astra`、`gpt-6-luna`、`gpt-6-sol`、`gpt-5.6-sol`、`gpt-5.6-terra`、`gpt-5.6-luna`、`gpt-5.5`、`gpt-5.4`、`gpt-5.4-mini` | `https://api.openai.com/v1` |
| 通义千问 / 百炼北京 | `qwen3.8-max`、`qwen3.7-plus`、`qwen3.6-plus`、`qwen3.5-plus`、`qwen3.5-flash`、`qwen-plus`、`qwen-flash` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |

模型 ID 和地址均可手动编辑；自定义 OpenAI 协议网关继续受支持。使用原生 Anthropic 协议的网关选择 Claude 并编辑地址。已保存的自定义配置在打开页面时不会被默认值覆盖。环境变量覆盖的字段在页面中锁定，选择预设也不会替换该字段。

## 原生 Claude 适配

使用 `/v1/messages`、`x-api-key` 与 `anthropic-version: 2023-06-01`，system 单独传入，不使用 OpenAI Chat Completions 请求格式。支持文本块合并、原生 usage / stop_reason 记录、有限次数重试和超时处理。拒绝跨地址重定向，错误信息不回显认证信息。

当前各研究阶段的 JSON 结构不同，适配器采用 JSON 提示约束加本地对象解析校验，并处理 Markdown 围栏、截断与无效输出。**未声称使用原生固定 JSON Schema 约束保证格式**。近期 Claude 模型不接受任意 temperature / top_p，因此使用服务原生采样默认值；CLinkRAG 的模型事件记录实际传输参数，跨服务对照实验不能假定采样设置相同。

OpenAI 的 GPT-5.4 两个预设使用 `max_completion_tokens` 与 `reasoning_effort=none`，避免沿用不适合的新旧参数组合。通义千问使用独立 `QWEN_API_KEY`，设置 `enable_thinking=false`。Claude 与百炼不会回退使用 OpenAI 的密钥。

百炼预设采用仍受支持的北京公共域名。可按控制台信息修改为业务空间专属域名；密钥需与所选地域一致。

## 官方来源

- [Claude 模型列表](https://platform.claude.com/docs/en/models/overview) 与 [Messages API](https://platform.claude.com/docs/en/api/messages/create)：原生认证、响应块和采样参数限制。
- [DeepSeek 首次调用](https://api-docs.deepseek.com/)：官方地址、Flash 与 V4 Pro 模型 ID。
- [GPT-5.4 Mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini)、[GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4)：模型 ID、Chat Completions 支持与 reasoning none。
- [百炼 OpenAI 兼容接口](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)、[思考模式](https://help.aliyun.com/zh/model-studio/deep-thinking)：域名、地域、模型与非思考模式。

## 前一轮验证（扩充预设之前）

- 后端 58 项测试通过，包括 Claude 原生请求、密钥隔离、JSON 解析、截断、重试、保存重载、OpenAI 参数适配与百炼独立配置。
- 新预设浏览器测试 20 项通过；原模型设置浏览器回归 26 项通过；工作台产品回归 51 项通过，本轮共 97 项浏览器检查。保存请求模拟，不改用户配置；预设测试将环境覆盖清单设为空以验证标准自动填充路径。
- 新增在线研究追踪装配测试，同时修复原追踪器引用旧 `FlagReranker` 名称的问题，改为包装共享重排工厂。
- 本次未发送真实 Claude / OpenAI / 百炼生成请求，未验证这些账号的在线模型权限；没有付费 API 调用。

实现：`longans/llms/anthropic_model.py`、`debug_ui/model_presets.py`；测试：`tests/test_claude_presets.py`、`tests/provider-browser.cjs`；截图：`results/provider-presets/`。

## 预设扩充说明

按用户要求，本轮仅扩充模型目录和分组，没有运行测试，也没有调用生成 API。OpenAI 官方目录与弃用公告仍列出 GPT-5.4 Mini，保留为较早型号；不将其作为当前默认首选。新预设的账号权限与实际输出尚未逐一验证。来源：[官方模型目录](https://developers.openai.com/api/docs/models)、[GPT-5.4 Mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini)、[弃用公告](https://developers.openai.com/api/docs/deprecations)。
