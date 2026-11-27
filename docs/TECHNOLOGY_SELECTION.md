# Sprint 0 技术选型报告

调研日期：2026-11-26。版本以当日官方 PyPI 页面为准，概念与用法以项目官方文档为准。

## 核心依赖

| 技术 | 当前稳定版 | 本项目选择 | 官方兼容信息与用途 |
|---|---:|---:|---|
| LangGraph | 1.2.24 | `==1.2.24` | PyPI 要求 Python >=3.10 并列出 3.13；用于共享状态、节点、边、条件控制、持久化和人工中断 |
| Pydantic | 2.14.4 | `==2.14.4` | v2 文档以 Python 3.10+ 类型注解为基础；用于核心数据校验、序列化和 JSON Schema |
| FastAPI | 0.165.0 | `==0.165.0` | 基于 Python 类型提示、Starlette 和 Pydantic；Sprint 5 提供 HTTP API |
| LiteLLM | 1.111.0 | `==1.111.0` | Python SDK 通过统一 `completion()` 接口支持 OpenAI、Anthropic 等提供商，并提供统一响应、异常和成本信息 |

核心四项使用精确版本，辅助直接依赖使用明确兼容范围；所有直接和传递依赖由 `uv.lock` 固定。uv 为隔离项目环境选择 CPython 3.12.13，实际安装与导入结果记录在 `TEST_REPORT.md`。

## 其余技术

- `pydantic-settings >=2.12,<3`，本次锁定 2.16.3：Sprint 1 的统一配置和环境变量读取。
- `SQLAlchemy >=2.0.46,<2.1`，本次锁定 2.0.58：Sprint 5 的 SQLite ORM。
- `Streamlit >=1.50,<2`，本次锁定 1.67.0：Sprint 5 的交互界面。
- `Uvicorn >=0.38,<1`，本次锁定 0.54.0：FastAPI ASGI 运行服务器。
- `Pytest >=9,<10`，本次锁定 9.2.0：单元、集成、工作流与异常测试。
- SQLite：Python 标准库和 SQLAlchemy 支持，无独立数据库服务成本。
- Docker：最终部署目标，本阶段不创建未经验证的部署配置。

准确解析版本以 `uv.lock` 为准，避免手工猜测辅助包最新版本。

## 选型依据

### LangGraph

官方文档明确其定位是低级编排框架和运行时，通过共享状态、节点和边组合确定性与 LLM 步骤；支持持久化、故障恢复、流式输出和 human-in-the-loop，同时不强制固定 Agent 架构。这符合 PEA 的条件路由、澄清暂停、评估迭代和最大次数控制需求。Sprint 3 只建立一个主图和专业节点，不增加无意义的多 Agent 层级。

官方资料：
- https://docs.langchain.com/oss/python/langgraph/overview
- https://pypi.org/project/langgraph/

### Pydantic

Pydantic v2 的 `BaseModel` 通过带类型注解的字段定义结构，在构造时验证并转换数据，支持序列化与 JSON Schema。它适合作为节点输入输出、评估报告和 API 数据契约，避免各模块传递无约束字典。

官方资料：
- https://docs.pydantic.dev/latest/concepts/models/
- https://pypi.org/project/pydantic/

### LiteLLM

采用 **Python SDK 直接接入**，不部署额外 LiteLLM Proxy，避免引入不必要的服务和运维复杂度。Gateway 作为本项目内部统一接口，底层 LiteLLM 负责提供商协议、响应和异常归一化；重试、预算、超时和调用记录由项目自身明确控制。Sprint 1 已实现 OpenAI 与 Anthropic 适配，模型 ID 通过配置提供；当前只有假模块验证，真实调用需密钥且单独验收。

官方资料：
- https://docs.litellm.ai/docs/
- https://pypi.org/project/litellm/

### FastAPI

FastAPI 与 Pydantic 数据契约自然衔接，并提供 OpenAPI 文档。按阶段要求到 Sprint 5 才实现业务端点，本阶段只验证安装兼容性，不创建空壳 API 冒充产品功能。

官方资料：
- https://fastapi.tiangolo.com/tutorial/first-steps/
- https://pypi.org/project/fastapi/

## 成本、风险与控制

- 当前无真实模型调用，外部模型费用为 0。
- LangGraph 与 LiteLLM 迭代较快：固定核心版本、提交锁文件，升级时单独运行兼容性测试。
- LiteLLM 完整发行版依赖较多：先采用稳定完整 SDK；是否改用精简 `litellm-core` 留待有实际需求后评估，本阶段不更换方案。
- 系统 Python 为 3.13.5，项目使用 uv 管理的 CPython 3.12.13；Sprint 0 的依赖安装和启动测试通过，Sprint 1 的 42 项单元、集成和异常测试通过。
- Sprint 1 已默认设置 `LITELLM_LOCAL_MODEL_COST_MAP=True` 并延迟导入 LiteLLM。当前安装版本源码明确支持该开关；真实导入验证未再出现远程价格表警告。本地 SDK 导入本次约 5.286s，只发生在首次真实后端使用时，普通诊断和 Mock 不受影响。价格表时效性随 SDK 版本管理。
- 当前技术栈没有明显不兼容证据，因此不推荐更换核心技术栈，也无需额外付费服务。
