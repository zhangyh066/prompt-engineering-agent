import json
import os
from typing import Any

import httpx
import streamlit as st

API_BASE_URL = os.getenv("PEA_API_BASE_URL", "http://127.0.0.1:8000")

STATUS_LABELS = {
    "completed": "已完成",
    "needs_clarification": "等待补充",
    "failed": "执行失败",
    "cancelled": "已取消",
    "running": "运行中",
}
DETAIL_OPTIONS = {"均衡": "balanced", "详细": "detailed", "简洁": "concise"}
EXPLORATION_OPTIONS = {"均衡": "balanced", "探索": "exploratory", "保守": "conservative"}


def request_api(method: str, path: str, **kwargs: Any) -> httpx.Response:
    try:
        response = httpx.request(
            method,
            f"{API_BASE_URL.rstrip('/')}{path}",
            timeout=120.0,
            **kwargs,
        )
        response.raise_for_status()
        return response
    except httpx.HTTPStatusError as error:
        try:
            detail = error.response.json().get("detail", error.response.text)
        except ValueError:
            detail = error.response.text
        raise RuntimeError(f"API {error.response.status_code}: {detail}") from error
    except httpx.HTTPError as error:
        raise RuntimeError(f"无法连接 API：{API_BASE_URL}") from error


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root { --pea-ink:#14213d; --pea-blue:#3157d5; --pea-mint:#0c8f78; }
        .stApp { background:#f4f6fb; color:var(--pea-ink); }
        [data-testid="stSidebar"] { background:#111a2e; }
        [data-testid="stSidebar"] * { color:#e8edf8; }
        [data-testid="stSidebar"] .stRadio label { padding:.35rem .1rem; }
        .pea-brand { font-size:1.7rem; font-weight:800; letter-spacing:.08em; margin-bottom:.2rem; }
        .pea-brand-sub { color:#9eacd0; font-size:.82rem; margin-bottom:1.5rem; line-height:1.5; }
        .pea-hero { background:linear-gradient(120deg,#172554 0%,#3157d5 62%,#0c8f78 140%);
          color:white; padding:1.6rem 1.8rem; border-radius:18px; margin-bottom:1.2rem;
          box-shadow:0 12px 30px rgba(30,55,120,.13); }
        .pea-hero h1 { color:white; font-size:1.75rem; margin:0 0 .45rem 0; }
        .pea-hero p { color:#dce5ff; margin:0; max-width:850px; line-height:1.65; }
        .pea-kicker { color:#b7c8ff; text-transform:uppercase; letter-spacing:.15em;
          font-size:.68rem; font-weight:700; margin-bottom:.55rem; }
        .pea-status { display:inline-block; border-radius:999px; padding:.25rem .7rem;
          font-size:.78rem; font-weight:700; background:#e4ebff; color:#3157d5; }
        .pea-status.ok { background:#dff5ed; color:#087761; }
        .pea-status.warn { background:#fff0d6; color:#9a5a00; }
        .pea-status.bad { background:#ffe3e6; color:#ad2636; }
        .pea-muted { color:#667085; font-size:.86rem; }
        .pea-section { font-size:1.08rem; font-weight:750; margin:.7rem 0 .4rem 0; }
        [data-testid="stForm"] { background:white; border:1px solid #e3e8f2;
          border-radius:16px; padding:1.1rem 1.2rem; box-shadow:0 5px 18px rgba(20,35,70,.04); }
        [data-testid="stMetric"] { background:white; border:1px solid #e4e9f2;
          padding:.85rem 1rem; border-radius:14px; }
        .stButton>button, .stDownloadButton>button { border-radius:10px; font-weight:650; }
        .stTabs [data-baseweb="tab-list"] { gap:.35rem; }
        .stTabs [data-baseweb="tab"] { background:#e9edf6; border-radius:9px 9px 0 0; }
        code, pre { font-size:.82rem !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(kicker: str, title: str, description: str) -> None:
    st.markdown(
        f'<div class="pea-hero"><div class="pea-kicker">{kicker}</div>'
        f"<h1>{title}</h1><p>{description}</p></div>",
        unsafe_allow_html=True,
    )


def render_status(status: str) -> None:
    css_class = "ok" if status == "completed" else "bad" if status == "failed" else "warn"
    st.markdown(
        f'<span class="pea-status {css_class}">{STATUS_LABELS.get(status, status)}</span>',
        unsafe_allow_html=True,
    )


def result_metrics(result: dict[str, Any]) -> None:
    evaluation = result.get("final_evaluation") or {}
    columns = st.columns(4)
    columns[0].metric("最佳评分", f"{evaluation.get('score', 0):.1%}")
    columns[1].metric("生成版本", len(result.get("iterations", [])))
    columns[2].metric("动态评估", evaluation.get("dynamic_status", "not_run"))
    cost = evaluation.get("cost_usd")
    columns[3].metric("记录成本 USD", cost if cost is not None else "未知")


def render_clarification(result: dict[str, Any]) -> None:
    st.warning("信息不足。补充后将从同一工作流检查点继续。")
    with st.form("clarification_form"):
        answers = {}
        for index, question in enumerate(result["clarification_questions"], start=1):
            answers[f"q{index}"] = st.text_area(question, key=f"clarification_{index}")
        submitted = st.form_submit_button("提交补充并继续", type="primary")
    if submitted:
        response = request_api(
            "POST",
            f"/api/v1/optimizations/{result['thread_id']}/clarifications",
            json={"answers": answers},
        )
        st.session_state["workflow_result"] = response.json()
        st.rerun()


def render_result(result: dict[str, Any]) -> None:
    status = result["status"]
    left, right = st.columns([1, 4])
    with left:
        render_status(status)
    with right:
        st.caption(f"运行 ID · {result['thread_id']}")
    if status == "needs_clarification":
        render_clarification(result)
        return
    if status == "failed":
        st.error(result.get("error") or "工作流执行失败")
        return
    if status == "cancelled":
        st.info("任务已在节点边界取消。")
        return

    result_metrics(result)
    optimization = result.get("optimization")
    if not optimization:
        return
    preferences = result["request"].get("preferences", {})
    st.caption(
        f"详略：{preferences.get('detail_level', 'balanced')} · "
        f"探索：{preferences.get('exploration_level', 'balanced')}"
    )
    prompt_tab, analysis_tab, evaluation_tab, adapter_tab = st.tabs(
        ["Prompt 对比", "诊断与策略", "评估与版本", "模型适配"]
    )
    with prompt_tab:
        original = result["request"].get("raw_prompt") or result["request"]["user_request"]
        original_col, optimized_col = st.columns(2)
        original_col.markdown('<div class="pea-section">原始输入</div>', unsafe_allow_html=True)
        original_col.code(original, language=None)
        optimized_col.markdown('<div class="pea-section">最终最佳 Prompt</div>', unsafe_allow_html=True)
        optimized_col.code(optimization["generated_prompt"]["content"], language=None)
        with st.expander("查看每项修改理由"):
            for change in optimization["generated_prompt"]["changes"]:
                st.write(f"**{change['description']}**\n\n{change['reason']}")
        st.download_button(
            "下载本次完整结果 JSON",
            json.dumps(result, ensure_ascii=False, indent=2),
            file_name=f"pea-{result['thread_id']}.json",
            mime="application/json",
        )
    with analysis_tab:
        intent = optimization["intent"]
        diagnosis = optimization["diagnosis"]
        cols = st.columns(3)
        cols[0].metric("任务类型", intent["task_type"])
        cols[1].metric("复杂度", intent["complexity"])
        cols[2].metric("诊断分", f"{diagnosis['overall_score']:.1f}")
        st.write("八维诊断")
        st.dataframe(diagnosis["assessments"], use_container_width=True)
        st.write("策略选择")
        st.dataframe(optimization["strategy_plan"]["selected"], use_container_width=True)
    with evaluation_tab:
        evaluation = result["final_evaluation"]
        if evaluation["unverified_aspects"]:
            st.info("未验证指标：" + "、".join(evaluation["unverified_aspects"]))
        st.dataframe(evaluation["metrics"], use_container_width=True)
        for warning in result.get("warnings", []):
            st.warning(warning)
        for record in result["iterations"]:
            with st.expander(
                f"版本 {record['iteration']} · 得分 {record['evaluation']['score']:.1%}"
            ):
                st.code(record["prompt"]["content"], language=None)
                st.json(record["evaluation"])
    with adapter_tab:
        adapted = result.get("adapted_prompt")
        if adapted:
            st.write(f"目标：{adapted['provider']} / {adapted['model']}")
            for message in adapted["messages"]:
                st.write(f"**{message['role']}**")
                st.code(message["content"], language=None)
            st.json(adapted["changes"])
        else:
            st.info("本次未指定目标模型适配。可在优化表单的高级设置中启用。")


def optimization_page() -> None:
    page_header(
        "PROMPT WORKBENCH",
        "优化工作台",
        "从原始需求到可执行 Prompt：查看诊断、策略、迭代证据和目标模型适配。默认使用 OpenAI 接入，未配置时可切换 Mock。",
    )
    with st.form("optimization_form"):
        user_request = st.text_area(
            "你想完成什么任务？",
            placeholder="例如：为客户写一封项目延期邮件，保留原因、日期和具体补救措施。",
            height=115,
        )
        raw_prompt = st.text_area("原始 Prompt（可选）", height=135)
        detail, exploration, iterations = st.columns(3)
        detail_label = detail.radio("信息详略", list(DETAIL_OPTIONS), horizontal=True)
        exploration_label = exploration.radio("思考方式", list(EXPLORATION_OPTIONS), horizontal=True)
        max_iterations = iterations.selectbox("最大生成次数", [1, 2, 3], index=2)
        provider, dynamic = st.columns([1, 1])
        provider_name = provider.selectbox("执行提供商", ["openai", "anthropic", "mock"])
        dynamic_enabled = dynamic.checkbox("启用动态原/优化对照", value=False)
        with st.expander("目标模型适配（可选）"):
            target_enabled = st.checkbox("生成目标模型适配版本")
            target_provider = st.selectbox("目标提供商", ["openai", "anthropic"])
            target_model_name = st.text_input("目标模型 ID", placeholder="由你的模型配置决定")
            target_system = st.checkbox("支持 system 消息", value=True)
            target_json = st.checkbox("声明支持 JSON 模式", value=False)
            target_tokens = st.number_input("最大输出 Token", 1, 32000, 2000)
        submitted = st.form_submit_button("开始优化", type="primary", use_container_width=True)

    if submitted:
        if not user_request.strip():
            st.error("请先描述要完成的任务。")
        elif target_enabled and not target_model_name.strip():
            st.error("启用模型适配时需要填写目标模型 ID。")
        else:
            target_model = None
            if target_enabled:
                target_model = {
                    "provider": target_provider,
                    "model": target_model_name.strip(),
                    "supports_system_message": target_system,
                    "supports_json_mode": target_json,
                    "max_output_tokens": target_tokens,
                }
            payload = {
                "user_request": user_request,
                "raw_prompt": raw_prompt or None,
                "preferences": {
                    "detail_level": DETAIL_OPTIONS[detail_label],
                    "exploration_level": EXPLORATION_OPTIONS[exploration_label],
                },
                "provider": provider_name,
                "max_iterations": max_iterations,
                "dynamic_evaluation": dynamic_enabled,
                "target_model": target_model,
            }
            try:
                with st.spinner("正在分析、生成并评估 Prompt..."):
                    response = request_api("POST", "/api/v1/optimizations", json=payload)
                st.session_state["workflow_result"] = response.json()
            except RuntimeError as error:
                st.error(str(error))

    if "workflow_result" in st.session_state:
        if st.button("清除当前结果"):
            del st.session_state["workflow_result"]
            st.rerun()
        try:
            render_result(st.session_state["workflow_result"])
        except RuntimeError as error:
            st.error(str(error))


def history_page() -> None:
    page_header("VERSION INTELLIGENCE", "历史与版本", "比较每次生成的内容、策略和评估变化，并导出可审计报告。")
    try:
        history = request_api("GET", "/api/v1/history", params={"limit": 100}).json()
        if not history:
            st.info("暂无历史记录。先在优化工作台创建一次运行。")
            return
        table = [
            {
                "运行": item["run_id"][:8],
                "任务": item["task_type"] or "待定",
                "状态": STATUS_LABELS.get(item["status"], item["status"]),
                "版本": item["version_count"],
                "Token": item["total_tokens"],
                "成本": item["total_cost_usd"],
            }
            for item in history
        ]
        st.dataframe(table, use_container_width=True)
        selected = st.selectbox(
            "选择运行",
            history,
            format_func=lambda item: f"{item['run_id'][:8]} · {item['user_request'][:45]}",
        )
        run_id = selected["run_id"]
        detail = request_api("GET", f"/api/v1/history/{run_id}").json()
        cols = st.columns(4)
        cols[0].metric("版本", selected["version_count"])
        cols[1].metric("Token", selected["total_tokens"] if selected["total_tokens"] is not None else "未知")
        cols[2].metric("成本", selected["total_cost_usd"] or "未知")
        cols[3].metric("任务", selected["task_type"] or "待定")
        versions = detail["versions"]
        if len(versions) >= 2:
            left_col, right_col = st.columns(2)
            left = left_col.selectbox("起始版本", versions, key="history_left")
            right = right_col.selectbox("目标版本", versions, index=len(versions) - 1, key="history_right")
            comparison = request_api(
                "GET",
                f"/api/v1/history/{run_id}/compare",
                params={"left": left["version"], "right": right["version"]},
            ).json()
            st.metric("分数变化", f"{comparison['score_change']:+.2%}")
            st.code(comparison["unified_diff"], language="diff")
        for version in versions:
            with st.expander(f"版本 {version['version']}{' · 最佳' if version['is_best'] else ''}"):
                st.code(version["content"], language=None)
        json_export = request_api("GET", f"/api/v1/history/{run_id}/export", params={"format": "json"})
        markdown_export = request_api("GET", f"/api/v1/history/{run_id}/export", params={"format": "markdown"})
        download_cols = st.columns(2)
        download_cols[0].download_button("下载 JSON 报告", json_export.content, file_name=f"pea-{run_id}.json")
        download_cols[1].download_button("下载 Markdown 报告", markdown_export.content, file_name=f"pea-{run_id}.md")
    except RuntimeError as error:
        st.error(str(error))


def evaluation_page() -> None:
    page_header("EVIDENCE CENTER", "评测中心", "分别查看数据审核状态、公共结构审计和未验证边界，避免用单一分数代替质量。")
    try:
        with st.spinner("正在运行公共结构审计..."):
            benchmark = request_api("GET", "/api/v1/benchmarks/status").json()
            audit = request_api("GET", "/api/v1/evaluations/public-audit").json()
        st.markdown('<div class="pea-section">中文 Benchmark</div>', unsafe_allow_html=True)
        cols = st.columns(4)
        cols[0].metric("任务总数", benchmark["total"])
        cols[1].metric("唯一 ID", benchmark["unique_task_ids"])
        cols[2].metric("待人工审核", benchmark["pending_human_review"])
        cols[3].metric("真实实验就绪", "是" if benchmark["ready_for_real_model_experiments"] else "否")
        st.dataframe(
            [{"类别": key, "数量": value} for key, value in benchmark["distribution"].items()],
            use_container_width=True,
        )
        st.markdown('<div class="pea-section">Dolly 公共结构审计</div>', unsafe_allow_html=True)
        audit_cols = st.columns(4)
        audit_cols[0].metric("公共样例", audit["public_cases"])
        audit_cols[1].metric("目标保留", f"{audit['goal_preservation_rate']:.1%}")
        audit_cols[2].metric("输出结构", f"{audit['output_structure_rate']:.1%}")
        audit_cols[3].metric("平均膨胀", f"{audit['mean_prompt_expansion_ratio']:.2f}×")
        st.write("已知缺陷检测")
        mutation_cols = st.columns(len(audit["mutation_detection"]))
        for column, (name, value) in zip(mutation_cols, audit["mutation_detection"].items()):
            column.metric(name, f"{value:.0%}")
        if not audit["semantic_quality_measured"]:
            st.warning("公共审计只验证结构与已知缺陷，不测量开放任务语义质量或产品优越性。")
    except RuntimeError as error:
        st.error(str(error))


def status_page() -> None:
    page_header("LOCAL PRODUCT", "系统状态", "查看本地服务、运行边界和产品文档。密钥与内部配置值不会在此展示。")
    try:
        health = request_api("GET", "/health").json()
        cols = st.columns(3)
        cols[0].metric("API 状态", health["status"])
        cols[1].metric("产品阶段", health["stage"])
        cols[2].metric("默认执行", "OpenAI")
        st.write("API 地址")
        st.code(API_BASE_URL, language=None)
        st.info("真实模型调用需要管理员同时配置提供商、密钥、真实开关和成本预算。界面不接收或展示密钥。")
        st.link_button("打开 OpenAPI 文档", f"{API_BASE_URL.rstrip('/')}/docs")
        st.write("产品边界")
        st.write("- 本地单实例 SQLite 与内存澄清检查点。")
        st.write("- 结构评估不等于语义质量；模拟评测不等于真实 API 结果。")
        st.write("- 取消在节点边界生效，不能强制中断正在阻塞的网络请求。")
    except RuntimeError as error:
        st.error(str(error))


def main() -> None:
    st.set_page_config(page_title="PEA · Prompt Engineering Agent", layout="wide")
    apply_theme()
    st.sidebar.markdown(
        '<div class="pea-brand">PEA</div><div class="pea-brand-sub">Prompt Engineering Agent<br>诊断 · 策略 · 生成 · 证据</div>',
        unsafe_allow_html=True,
    )
    page = st.sidebar.radio("工作区", ["优化工作台", "历史与版本", "评测中心", "系统状态"])
    st.sidebar.caption("默认 OpenAI · 可选 Mock")
    if page == "优化工作台":
        optimization_page()
    elif page == "历史与版本":
        history_page()
    elif page == "评测中心":
        evaluation_page()
    else:
        status_page()


if __name__ == "__main__":
    main()
