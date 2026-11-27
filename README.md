# PEA · Prompt Engineering Agent

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/Code-MIT-green)](LICENSE)

本地优先的 Prompt 诊断、生成、评估和版本管理工作台。PEA 不只改写文本，而是把意图分析、诊断、策略、执行评估、迭代和证据保存连接成完整工作流。

**当前版本：0.2.0 Beta。** 适合本地试用与评测工程开发，不承诺在所有模型和任务上自动优于原始 Prompt。

## 核心能力

- **诊断与策略**：任务分类、八维诊断、约束冲突检测和动态策略选择。
- **可控生成**：详细/均衡/简洁偏好，以及保守/均衡/探索模式。
- **探索与反证**：复杂任务可生成替代假设、反对证据和方案切换条件。
- **Agent 工作流**：LangGraph 状态、澄清中断、条件路由、有界迭代和最佳版本。
- **多模型接入**：Mock、OpenAI-compatible、Anthropic 与目标模型适配。
- **证据与历史**：静态/动态评估、SQLite 版本、diff、Token、成本和耗时。
- **产品界面**：优化工作台、历史版本、评测中心和系统状态。
- **开放接口**：FastAPI、JSON/Markdown 导出和 Promptfoo 桥接。

## 快速开始

要求 Python 3.12+ 与 uv 0.11.19。

```bash
uv sync --extra dev
```

终端一启动 API：

```bash
uv run uvicorn pea.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

终端二启动界面：

```bash
uv run streamlit run src/pea/ui/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
```

访问：

- 产品界面：http://127.0.0.1:8501
- OpenAPI：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

默认使用 Mock，不需要 API Key，也不会自动产生模型费用。

## CLI 示例

```bash
uv run pea --optimize "写一份新员工入职指南，输出 Markdown。"
uv run pea --optimize "写一条生日祝福，输出一句话。" --workflow
uv run pea --mock
uv run pea --validate-benchmark
```

## 系统结构

```text
Streamlit / CLI / FastAPI
          ↓
     WorkflowRunner
          ↓
意图 → 诊断 → 策略 → 生成 → 评估 → Refiner
          ↓
模型适配 / SQLite 历史 / 评测与导出
          ↓
Mock · OpenAI-compatible · Anthropic
```

## 真实模型配置

```bash
OPENAI_API_BASE=https://your-endpoint/v1
OPENAI_API_KEY=your-key
OPENAI_MODEL=your-model
PEA_ENABLE_REAL_PROVIDERS=True
PEA_COST_BUDGET_USD=your-approved-budget
```

不要将真实密钥写入仓库。API 默认面向本地单实例使用，公网或多用户部署前需另行实现认证、授权、TLS 和数据隔离。

## 测试与构建

```bash
uv run pytest
uv build
```

当前发布基线为 **198 项测试**，另覆盖真实浏览器工作台、偏好提交、历史、评测与系统状态。GitHub Actions 配置保存在 `.github/workflows/ci.yml`；首次发布账号还需授予 `workflow` 权限后才能激活远端工作流。

## 文档

| 文档 | 内容 |
|---|---|
| [产品需求](docs/PRD.md) | 用户、范围、功能与验收要求 |
| [路线图](ROADMAP.md) | 后续语义工作台、策略记忆与团队能力 |
| [架构](ARCHITECTURE.md) | 模块、状态、评估和存储设计 |
| [API](API.md) | HTTP 与 Python 接口 |
| [部署](docs/DEPLOYMENT.md) | 本地与 Docker 配置 |
| [产品短板分析](docs/PRODUCT_CRITIQUE.md) | 语义、反事实、经验和协作演进方向 |
| [Harness 评测](docs/HARNESS_EVALUATION.md) | 公共数据与 Promptfoo 对照 |
| [模拟最终报告](docs/SIMULATION_FINAL_REPORT.md) | 模拟边界与完整结果 |
| [贡献指南](CONTRIBUTING.md) | 开发、测试与评审规范 |
| [安全说明](SECURITY.md) | 默认安全边界与漏洞报告 |

## 数据与许可证

代码使用 [MIT License](LICENSE)。第三方数据及适配样例保留原许可，具体来源、哈希与限制见 [外部数据说明](benchmarks/EXTERNAL_DATASETS.md)。Dolly 样例为 CC BY-SA 3.0。

## 当前限制

- 生成仍有确定性规则基线，语义规划与可编辑 Blueprint 在路线图中。
- 模拟评测不等于真实 API、真实人工或外部产品优越性证据。
- 当前为本地单实例 SQLite 与内存澄清检查点。
- Docker 配置已提供，但镜像运行需在目标环境独立验证。

欢迎通过 Issue、Pull Request 或安全公告参与改进。
