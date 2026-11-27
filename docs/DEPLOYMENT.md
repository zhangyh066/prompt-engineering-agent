# 部署指南

## 交付状态

本地 Python 安装、FastAPI、Streamlit 和真实浏览器流程已验证。Dockerfile 与 Compose 已提供，但本机没有容器工具，**镜像构建和容器运行尚未验证**。

## 本地运行

要求 Python 3.12+ 和 uv 0.11.19。

```bash
uv sync --locked
uv run pytest
```

终端一：

```bash
uv run uvicorn pea.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

终端二：

```bash
uv run streamlit run src/pea/ui/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
```

- UI：http://127.0.0.1:8501
- OpenAPI：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health
- 数据库：默认 `data/pea.db`，由 `PEA_DATABASE_PATH` 修改。

## 配置与安全

复制 `.env.example` 为 `.env` 或设置进程环境变量。默认 `mock`，不产生模型费用。

真实提供商需要同时满足：

1. 设置 `PEA_ENABLE_REAL_PROVIDERS=True`。
2. 配置 `OPENAI_API_KEY`、`OPENAI_MODEL` 或 `ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL`。
3. 使用 OpenAI-compatible 服务时，额外设置 `OPENAI_API_BASE`，例如 `https://host/v1`。
3. 使用 OpenAI-compatible 服务时，额外设置 `OPENAI_API_BASE`，例如 `https://host/v1`。
4. 明确真实测试预算、模型和任务范围。

API 安全措施：

- 默认可信 Host 为 `127.0.0.1,localhost,testserver`，容器服务名为 `api` 时需通过 `PEA_TRUSTED_HOSTS` 添加。
- POST/PUT/PATCH 声明的请求体最大 64 KiB。
- 响应包含 `Cache-Control: no-store`、`X-Content-Type-Options`、`X-Frame-Options` 和 `Referrer-Policy`。
- 不启用 CORS，不输出模型密钥。
- 当前无多用户认证，不能绑定公网地址直接提供服务。

## Docker 配置

`Dockerfile` 提供 `api` 和 `ui` 两个目标，使用 Python 3.12 slim、锁定依赖、非 root 用户和 `/data` 数据目录。

构建：

```bash
docker build --target api -t pea-api:0.2.0 .
docker build --target ui -t pea-ui:0.2.0 .
```

或启动 Compose：

```bash
docker compose up --build
```

Compose 默认：

- API 仅映射到 `127.0.0.1:8000`。
- UI 仅映射到 `127.0.0.1:8501`。
- UI 通过内部地址 `http://api:8000` 调用 API。
- SQLite 数据保存在命名卷 `pea-data`。
- `PEA_ENABLE_REAL_PROVIDERS` 默认为 `False`。
- 密钥只从宿主环境读取，不写入 Dockerfile 或镜像。

停止：

```bash
docker compose down
```

保留 `pea-data` 可保留历史。`docker compose down -v` 会删除数据卷，除非明确需要删除全部历史，否则不要使用。

## 健康检查与排障

```bash
curl http://127.0.0.1:8000/health
docker compose ps
docker compose logs api
docker compose logs ui
```

Windows 用户可使用浏览器访问健康检查。若 UI 无法连接 API，检查 `PEA_API_BASE_URL`、容器网络和 `PEA_TRUSTED_HOSTS`。若真实模型被拒绝，检查显式开关、模型 ID 和密钥配置是否存在。

## 备份与恢复

本地停止写入后备份 `data/pea.db`。Docker 环境停止 API 写入后备份命名卷。恢复前先在测试环境验证数据库可读；当前版本未提供在线迁移或跨版本恢复保证。

## 生产边界

当前交付是单实例本地产品。多用户认证、TLS、访问控制、迁移、水平扩展、持久化 LangGraph Checkpointer 和集中预算需要另行架构设计与审核，不能仅靠公网暴露当前容器完成生产化。
