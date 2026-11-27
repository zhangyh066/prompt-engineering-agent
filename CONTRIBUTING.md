# 贡献指南

## 开发环境

要求 Python 3.12+ 和 uv 0.11.19。

```bash
uv sync --extra dev
uv run pytest
uv build
```

启动本地产品：

```bash
uv run uvicorn pea.api.app:create_app --factory --host 127.0.0.1 --port 8000
uv run streamlit run src/pea/ui/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
```

## 项目结构

- `src/pea/agents/`：意图、诊断、策略、生成与 Refiner。
- `src/pea/workflow/`：LangGraph 状态、路由、中断和取消。
- `src/pea/gateway/`：统一模型调用与提供商适配。
- `src/pea/evaluation/`：评估、公共数据、实验和统计。
- `src/pea/storage/`：SQLAlchemy、历史版本和导出。
- `src/pea/api/`、`src/pea/ui/`：产品接口与界面。
- `tests/`：单元、集成、异常、工作流和 API 测试。

## 修改原则

1. 先阅读相关模块和测试，优先复用现有接口。
2. 核心数据使用 Pydantic，业务模块不得直接调用提供商 SDK。
3. 不用硬编码 Prompt 或密钥替代配置与数据契约。
4. 不为展示 Agent 能力增加无意义 Agent。
5. 新功能需有与风险匹配的测试；失败路径不得被静默吞掉。
6. 真实模型测试需要明确预算并记录模型、参数和成本。
7. 不得把 Mock、LLM 子 Agent 或模拟人工写成真实质量证据。
8. 修改公开行为时同步 README、API、架构、开发日志和测试报告。

## 提交与评审

建议使用清晰的小提交，标题说明行为变化，例如：

- `feat: add editable prompt blueprint`
- `fix: preserve embedded context during diagnosis`
- `docs: clarify benchmark review requirements`

提交前确认：

- `uv run pytest` 通过。
- `uv build` 通过。
- 没有 `.env`、密钥、数据库或本地缓存进入版本控制。
- 新增数据具有来源、许可和审核状态。
- 测试结果真实记录，未删除关键断言来掩盖失败。
