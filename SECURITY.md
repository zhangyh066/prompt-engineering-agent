# 安全说明

## 默认安全边界

PEA 当前定位为本地单实例产品，不是可直接暴露公网的多租户服务。

- 默认提供商为 Mock，真实模型调用需要显式开关和预算。
- 密钥仅通过环境变量或本地 `.env` 提供，`.env` 被 Git 忽略。
- API 默认应绑定 `127.0.0.1`，不启用 CORS。
- 提供可信 Host、请求大小限制、安全响应头和 `Cache-Control: no-store`。
- 日志不主动记录 Prompt 内容或模型密钥。
- Docker 端口默认绑定本机，容器使用非 root 用户。

## 数据注意事项

SQLite 会保存原始需求、Prompt、输出和评估报告。不要在示例或公开 Benchmark 中提交真实客户数据、个人信息、凭证或商业机密。

公开数据样例的来源和许可分别记录在 `benchmarks/EXTERNAL_DATASETS.md` 与资源 provenance 文件中。

## 报告漏洞

请使用项目 GitHub 仓库的 Private Vulnerability Reporting / Security Advisory 功能报告安全问题，不要在公开 Issue 中附带可利用细节、真实密钥或敏感数据。

报告应包含影响版本、复现条件、潜在影响和可行的修复方向。

## 生产化提醒

公网或多用户部署前必须另行实现和评审身份认证、授权、TLS、审计、数据隔离、速率限制和持久化任务恢复。当前本机安全默认值不能替代这些能力。
