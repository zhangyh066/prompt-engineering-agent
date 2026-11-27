# API 文档

## 当前范围

Sprint 5 提供 FastAPI HTTP API、Streamlit UI、Python API 与 CLI。默认仅允许本地 Mock；真实提供商必须显式启用。

## HTTP API

启动：

```bash
uv run uvicorn pea.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

| 方法与路径 | 说明 |
|---|---|
| `GET /health` | 服务健康状态 |
| `POST /api/v1/optimizations` | 创建优化；返回 `WorkflowResult` |
| `POST /api/v1/optimizations/{run_id}/clarifications` | 以 `{"answers":{"q1":"..."}}` 恢复澄清 |
| `POST /api/v1/optimizations/{run_id}/cancel` | 请求取消活跃任务，返回 202 |
| `GET /api/v1/benchmarks/status` | 100 条 Benchmark 分布与审核状态 |
| `GET /api/v1/evaluations/public-audit` | 80 条公共 Prompt 结构与变异审计 |
| `GET /api/v1/history?limit=50&offset=0&run_status=completed` | 历史分页与状态筛选 |
| `GET /api/v1/history/{run_id}` | 原始输入、最终版本和全部评估 |
| `GET /api/v1/history/{run_id}/compare?left=1&right=2` | 统一 diff、分数和策略变化 |
| `GET /api/v1/history/{run_id}/export?format=json` | 下载 JSON |
| `GET /api/v1/history/{run_id}/export?format=markdown` | 下载 Markdown |

创建优化示例：

```json
{
  "user_request": "写一条生日祝福，输出一句话。",
  "raw_prompt": null,
  "preferences": {"detail_level": "balanced", "exploration_level": "balanced"},
  "provider": "mock",
  "max_iterations": 3,
  "dynamic_evaluation": false,
  "target_model": null
}
```

`provider` 仅支持 `mock`、`openai`、`anthropic`。真实提供商默认返回 403；设置 `PEA_ENABLE_REAL_PROVIDERS=True` 后仍需合法模型和密钥。未找到运行或版本返回 404，非法请求返回 422，配置不完整返回 400。

OpenAPI 文档：`/docs`。API 没有多用户认证，应绑定 `127.0.0.1`，不得直接暴露公网。`PEA_TRUSTED_HOSTS` 配置可信 Host；声明请求体上限 64 KiB，响应包含 `Cache-Control: no-store` 与安全响应头。

## CLI

```bash
uv run pea
uv run pea --mock
uv run pea --validate-benchmark
uv run pea --optimize "写一份新员工入职指南，输出 Markdown。"
uv run pea --optimize "写一条生日祝福，输出一句话。" --workflow
uv run pea --optimize "优化 Prompt" --raw-prompt "写一封客户回访邮件，不超过200字。" --workflow
```

- `--optimize REQUEST`：执行确定性优化管线。
- `--raw-prompt TEXT`：提供原始 Prompt，必须与 `--optimize` 同用。
- `--workflow`：通过 LangGraph 执行，必须与 `--optimize` 同用。
- `--mock`：执行本地 Gateway Mock，与 `--optimize` 互斥。
- `--validate-benchmark`：校验 100 条任务及审核门禁，不执行模型调用。
- 无参数：输出 Sprint 4 环境与依赖诊断。

CLI 默认不执行动态模型评估。需要澄清时输出 `needs_clarification`、`clarification_questions` 和 `thread_id`；当前须在相同 Python 进程中恢复。

## 工作流 Python API

```python
from pea.models import PromptOptimizationRequest, Provider
from pea.workflow import WorkflowRunner

runner = WorkflowRunner()
result = runner.run(
    PromptOptimizationRequest(user_request="写一条生日祝福，输出一句话。"),
    max_iterations=3,
    dynamic_evaluation=False,
    provider=Provider.MOCK,
)
```

### 澄清恢复

```python
if result.status == "needs_clarification":
    result = runner.resume(
        result.thread_id,
        {"q1": "写一封客户回访邮件，不超过200字，输出邮件正文。"},
    )
```

答案键从 `q1` 开始，必须与问题数量完全一致，值不能为空白。恢复值由 `ClarificationAnswers` 校验。相同 `WorkflowRunner` 和 `thread_id` 是内存 Checkpointer 恢复的必要条件。

### 取消

```python
runner.cancel()
```

取消在下一节点边界生效，不能强制终止正在阻塞的模型请求。取消后状态为 `cancelled`，不再继续生成、评估或修订。

### `WorkflowResult`

| 字段 | 内容 |
|---|---|
| `status` | `running`、`needs_clarification`、`completed`、`failed`、`cancelled` |
| `thread_id` | 当前 Checkpointer 线程标识 |
| `optimization` | 最终最佳 `PromptOptimizationResult`；未完成时为空 |
| `iterations` | 每轮 Prompt、策略与评估记录，最多三轮 |
| `final_evaluation` | 最佳版本的评估，不一定等于最后一轮 |
| `clarification_questions` | 必要澄清问题 |
| `warnings` | 动态评估失败等警告 |
| `error` | 脱敏后的失败信息 |

达到三次上限仍返回 `completed` 和当前最佳版本，但 `final_evaluation.passed` 保留真实结果，可能为 `false`。

## Evaluator API

```python
from pea.evaluation import PromptEvaluator
from pea.gateway import create_gateway

evaluator = PromptEvaluator(create_gateway(), threshold=0.85)
```

默认 `WorkflowRunner` 只做静态评估。要向工作流启用 Mock 动态评估：

```python
from pea.config import Settings
from pea.gateway import LLMGateway

settings = Settings()
gateway = LLMGateway(settings)
runner = WorkflowRunner(evaluator=PromptEvaluator(gateway))
result = runner.run(request, dynamic_evaluation=True, provider=Provider.MOCK)
```

动态评估首次执行原始与优化 Prompt，后续迭代复用原始基线，仅执行新候选。检查：
- 非空结果。
- JSON 是否可解析。
- Markdown/表格结构是否存在。
- 是否满足可解析的长度上下限。

`EvaluationReport` 区分 `static_score`、`dynamic_score` 和 `baseline_dynamic_score`，并记录输出、Token、耗时与成本。`task_completion`、`content_accuracy` 始终在规则动态评估中列为未验证。

动态失败不会伪装成通过：`dynamic_status=failed`，报告中包含警告；如果静态已达标，工作流可完成但保留警告。预算导致的第二次调用失败会停止后续调用。

## Prompt 优化 API

```python
from pea.agents import StructuredPromptOptimizer
from pea.models import PromptOptimizationRequest

result = StructuredPromptOptimizer().optimize(
    PromptOptimizationRequest(
        user_request="优化 Prompt",
        raw_prompt="写一封客户回访邮件，不超过200字，输出邮件正文。",
    )
)
optimized_text = result.generated_prompt.content
json_result = result.model_dump_json(indent=2)
```

`PromptOptimizationResult` 包含原始请求、意图、八维诊断、策略计划、优化 Prompt 和逐项修改理由。`generation_method` 当前为 `deterministic`。

```python
from pea.structured_output import StructuredOutputParser
from pea.models import PromptOptimizationResult

restored = StructuredOutputParser.parse(PromptOptimizationResult, json_result)
```

解析器接受纯 JSON 或 JSON 代码围栏，非法结构抛出 `InvalidResponseError`。

## LLM Gateway API

```python
from pea.gateway import create_gateway
from pea.models import ChatMessage, CompletionRequest, Provider

response = create_gateway().complete(
    CompletionRequest(
        provider=Provider.MOCK,
        messages=[ChatMessage(role="user", content="Hello")],
        temperature=0.0,
        max_tokens=100,
        timeout_seconds=10.0,
    )
)
```

响应包含模型、内容、Token 来源、成本、耗时和尝试次数。`gateway.call_count` 包含失败与重试；`gateway.total_cost_usd` 仅累计已知成本。

统一异常包括 `ConfigurationError`、`AuthenticationError`、`RateLimitError`、`ProviderTimeoutError`、`ProviderUnavailableError`、`InvalidResponseError`、`BudgetExceededError` 和 `ProviderError`，均继承 `LLMError` 并提供 `provider`、`retryable`。

## Benchmark 与对照实验 API

```python
from pea.evaluation.benchmark import BenchmarkLoader
from pea.evaluation.experiment import ExperimentRunner
from pea.models import Provider

tasks = BenchmarkLoader().load()
report = ExperimentRunner(gateway).run(
    tasks,
    provider=Provider.MOCK,
    repetitions=2,
    max_tasks=2,
    allow_draft=True,
)
```

`allow_draft=True` 仅允许 Mock。真实提供商要求 100 条任务全部具有人工审核状态、审核人和时间。报告按 `original`、`generic`、`adaptive` 汇总质量检查、稳定性、Token、成本和耗时；`quality_claim_allowed=false` 时不得据此宣传优化有效。

## Model Adapter API

```python
from pea.adapters import ModelAdapter
from pea.models.adapter import TargetModel
from pea.models import Provider

target = TargetModel(
    provider=Provider.OPENAI,
    model="configured-model-id",
    supports_system_message=True,
    supports_json_mode=False,
    max_output_tokens=1000,
)
adapted = ModelAdapter().adapt(
    result.optimization.generated_prompt,
    result.optimization.intent,
    target,
)
completion_request = adapted.to_completion_request()
```

也可将 `target_model=target` 传给 `WorkflowRunner.run()`，最终通过 `WorkflowResult.adapted_prompt` 获取。适配仅改变消息结构与输出要求，不执行真实模型请求。

## 配置与限制

OpenAI 需要 `OPENAI_API_KEY`、`OPENAI_MODEL`；OpenAI-compatible 服务可额外设置 `OPENAI_API_BASE`，例如 `https://host/v1`。Anthropic 需要 `ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL`。默认 `PEA_DEFAULT_PROVIDER=mock`，`PEA_LITELLM_LOCAL_MODEL_COST_MAP=True`。

当前没有真实模型联调结果，规则动态评估不构成真实质量证明。Streamlit 通过上述 HTTP API 工作，数据库路径由 `PEA_DATABASE_PATH` 配置。
