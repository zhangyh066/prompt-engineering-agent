# Promptfoo 独立对照

从项目根目录生成配置：

```bash
uv run python -c "from pathlib import Path; from pea.evaluation.external_data import load_external_cases; from pea.evaluation.promptfoo_bridge import write_promptfoo_config; write_promptfoo_config(load_external_cases(), Path('benchmarks/promptfoo/promptfooconfig.yaml'))"
```

确保项目 `.venv` 的 Python 位于 PATH，然后在本目录运行：

```bash
PROMPTFOO_DISABLE_TELEMETRY=1 PROMPTFOO_DISABLE_UPDATE=1 npx --yes promptfoo@0.126.0 eval -c promptfooconfig.yaml --no-cache
```

Provider 只调用本地确定性 PEA，不调用外部模型。82 个场景包括 80 条公共提示词和 2 个 PEA 缺陷变异场景。该配置用于结构和缺陷回归，不是开放任务质量排行榜。
