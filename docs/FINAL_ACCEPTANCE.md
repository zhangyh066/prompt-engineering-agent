# 最终验收清单

## 结论

**模拟流程验收已通过，正式验收证据按项目负责人决定后补。** 模拟记录见 `docs/SIMULATED_ACCEPTANCE.md`；这不代表人工审核、真实模型效果或 Docker 部署已经实际通过。

| 要求 | 当前证据 | 状态 |
|---|---|---|
| 完整 Agent 工作流 | LangGraph 节点、路由、澄清、评估、Refiner、最佳版本 | 已验证 |
| 多模型提供商 | OpenAI/Anthropic LiteLLM 适配与假模块测试 | 工程通过，真实联调待完成 |
| Prompt 自动诊断 | 八维诊断、冲突检测、优先级 | 已验证 |
| 动态优化策略 | 八策略库、适用条件和成本级别 | 已验证 |
| Prompt 自动生成 | 确定性生成、修改理由和结构化输出 | 已验证规则基线 |
| 静态与动态评估 | 静态指标、Mock 动态原/优化执行 | 工程通过，真实效果待完成 |
| 自动迭代 | 默认最多三次、失败修订、最佳版本 | 已验证 |
| 模型适配 | system/JSON/Token 配置与双提供商测试 | 已验证适配逻辑 |
| Prompt 历史 | SQLite runs 和 prompt_versions | 已验证 |
| 版本比较 | 统一 diff、分数和策略变化 | 已验证 |
| Token 与成本 | Gateway、评估、实验和 SQLite 汇总；未知不伪报为 0 | 已验证 |
| Benchmark 与对照实验 | 100 条草稿、A/B/C Mock 实验和审核门禁 | 人工审核与真实实验待完成 |
| Web 界面 | Streamlit 优化、澄清、历史、比较和下载；真实浏览器验证 | 已验证 |
| 自动化测试 | 单元、集成、异常、工作流、API、构建 | 以 TEST_REPORT 最新结果为准 |
| Docker 部署 | 多目标 Dockerfile、Compose、非 root 和健康检查 | 配置完成，镜像运行待验证 |
| 技术文档 | README、规格、架构、API、部署、日志、测试报告 | 已维护 |

## 最终验收前必须完成

1. 真实审核人逐条审核 100 条 Benchmark，并填写 `review_status=approved`、`reviewer` 和 `reviewed_at`。
2. 项目负责人明确真实模型、最大调用次数、Token/费用预算和实验范围。
3. 在合法凭证下运行 OpenAI、Anthropic 小规模联调，再运行经审核的 A/B/C 对照实验。
4. 人工复核任务完成度、事实准确性和业务质量；不能只依据 Mock、LLM 自评或编码检查。
5. 在 Docker 环境执行 `docker compose up --build`，验证健康检查、UI、SQLite 持久化和重启行为。
6. 若投入多用户或公网使用，另行完成认证、授权、TLS、审计和生产架构评审。

## 当前可验收范围

本地 Mock 产品、规则优化基线、LangGraph 工作流、评估实验工程、历史版本、导出、API、Streamlit 和包构建均已有实际验证。当前不应宣称真实模型质量提升或生产部署已完成。
