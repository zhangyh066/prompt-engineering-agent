# Sprint 0 环境检查报告

检查日期：2026-11-26（本机 Asia/Shanghai）。

## 检查结果

| 项目 | 结果 | 处理方式 |
|---|---|---|
| 操作系统 | Windows 10 10.0.18363，AMD64；Git Bash 为 MINGW64 | 使用 Windows 兼容路径和命令 |
| Python | 3.13.5，Anaconda 发行版，`D:\ANACONDA\python.exe` | 满足 3.12+；项目使用隔离 `.venv` |
| pip | 26.1.1 | 可用 |
| uv | 0.11.19 | 用于虚拟环境、依赖解析和锁定 |
| Git | 2.51.0.windows.1 | 可用；当前目录尚不是 Git 仓库 |
| 项目目录 | `D:\prompt agent`，检查时为空 | 无既有代码，无覆盖风险 |
| Docker | 未在 PATH 中发现 | 不阻塞 Sprint 0；Sprint 6 前需安装或提供替代验收环境 |
| 项目资源 | 无既有代码、数据、文档或项目内配置可复用 | 从零初始化 |

## 全局 Python 包

全局 Anaconda 环境已有 LangGraph 1.0.6、Pydantic 2.10.3、FastAPI 0.136.1、Streamlit 1.45.1、SQLAlchemy 2.0.39、Pytest 8.3.4；LiteLLM 未安装。这些版本与本次选定版本不同，因此**不复用全局包作为项目运行环境**，避免污染全局环境或产生隐式依赖。

## 模型 API 配置

仅检查环境变量是否存在，未读取或输出密钥值：

- OpenAI：未配置。
- Anthropic：未配置。
- Gemini / Google：未配置。
- DeepSeek：未配置。
- OpenRouter：未配置。
- Azure OpenAI：未配置。
- `LITELLM_MODEL`、`PEA_MODEL`：未配置。
- 项目目录为空，不存在项目内 `.env`。

因此 Sprint 0 不执行真实模型调用，不产生模型 API 费用。Sprint 1 的模型接入与 Mock 测试可以在没有密钥的情况下继续工程开发，但真实多提供商验收需要项目负责人后续提供合法测试凭证。

## 结论

环境满足 Sprint 0 开发条件。主要限制是没有模型 API 和 Docker；两者均不影响当前基础工程、依赖兼容性和启动自检。
