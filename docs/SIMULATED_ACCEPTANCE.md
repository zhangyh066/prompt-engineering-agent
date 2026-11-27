# 模拟验收记录

## 验收性质

项目负责人已决定先以模拟方式通过流程验收，正式人工审核、真实模型实验和 Docker 运行证据在开发完成后补。

本记录只表示：**模拟流程验收通过**。它不代表人工审核已完成、真实 OpenAI/Anthropic 质量已验证或容器已部署。

## 100 条 Benchmark 模拟

实际执行 `ExperimentRunner`，使用 100 条草稿、MockBackend、三组对照和单次运行：

| 指标 | 结果 |
|---|---:|
| 实验状态 | `completed` |
| 完成任务 | 100 / 100 |
| Mock 调用 | 404 |
| 数据集人工审核 | `false` |
| 质量声明许可 | `false` |
| 外部模型费用 | 0 |

三组编码检查平均分均为 `0.4916666667`。Mock 输出相同，因此该结果不构成 A/B/C 质量差异证据，尤其不能据此声称自适应组优于原始组。

## OpenAI-compatible API 验证

完整回归最终为 148 passed、1 条 LiteLLM 弃用警告，包构建通过。

支持通过以下变量接入 OpenAI 格式的兼容 API：

```bash
OPENAI_API_BASE=https://your-openai-compatible-endpoint/v1
OPENAI_API_KEY=your-key
OPENAI_MODEL=your-model
```

`OPENAI_API_BASE` 为空时仍使用 OpenAI 默认端点。URL 仅允许 HTTP(S)，不得包含用户名、密码、查询参数或片段。

已在本地随机端口启动一次性 OpenAI 格式 HTTP 服务，通过实际 LiteLLM SDK 验证：

- 请求路径为 `/v1/chat/completions`。
- 模型和消息按 OpenAI 格式发送。
- Authorization Bearer 头正确传递。
- OpenAI 格式响应被归一化为 PEA 响应，Token 为 7。
- 该测试只访问本机服务，不访问外部模型，不产生费用。

## 正式后补事项

1. 人工逐条审核 100 条 Benchmark 并填写真实审核元数据。
2. 配置实际 OpenAI-compatible 服务后，先进行小预算联调，再运行正式 A/B/C 实验。
3. 人工复核语义完成度、事实准确性和业务质量。
4. 在可用 Docker 环境构建、运行并验证持久化和重启。

正式证据补齐前，数据集中的 `pending_human_review`、真实实验门禁和 `quality_claim_allowed=false` 均保持不变，不通过修改状态伪造验收。
