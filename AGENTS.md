# AGENTS.md

## 项目命令

- 安装：`uv sync --extra dev`
- 测试：`uv run pytest`
- 构建：`uv build`
- API：`uv run uvicorn pea.api.app:create_app --factory --host 127.0.0.1 --port 8000`
- UI：`uv run streamlit run src/pea/ui/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true`

## 架构约定

业务模块通过 Pydantic 契约交互；模型调用必须经过 `LLMGateway`。LangGraph 负责工作流控制，专业节点保持可独立测试。SQLite 保存历史，FastAPI 与 Streamlit 复用应用服务。

## 开发约定

- Python 3.12+，使用类型注解和现有命名风格。
- 新功能添加与风险匹配的测试，不创建无意义 Agent。
- 不读取、复制或提交 `.env`、真实密钥、数据库或本地缓存。
- 真实模型调用需要明确预算；测试显式使用 Mock。
- Mock、子 Agent 和模拟人工必须明确标识，不能作为真实质量证据。
- 修改公开行为时同步 README、API、ARCHITECTURE、DEVELOPMENT_LOG 和 TEST_REPORT。
- 外部数据必须保留来源、许可、哈希与审核状态。

## 发布检查

运行完整测试和构建，检查 Git 状态中无生成缓存与敏感文件。Docker 配置存在不等于镜像已验证，文档不得将计划功能写成已完成。
