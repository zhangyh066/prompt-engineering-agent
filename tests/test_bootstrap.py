from pea.bootstrap import (
    CORE_DEPENDENCIES,
    collect_bootstrap_status,
    detect_model_providers,
    get_dependency_versions,
)


def test_detect_model_providers_returns_only_presence() -> None:
    result = detect_model_providers(
        {
            "OPENAI_API_KEY": "test-openai-secret",
            "ANTHROPIC_API_KEY": "test-anthropic-secret",
        }
    )

    assert result == {"openai": True, "anthropic": True}
    assert "test-openai-secret" not in repr(result)
    assert "test-anthropic-secret" not in repr(result)


def test_detect_model_providers_ignores_whitespace() -> None:
    result = detect_model_providers({"OPENAI_API_KEY": "   "})

    assert result["openai"] is False


def test_core_dependencies_are_installed_at_selected_versions() -> None:
    versions = get_dependency_versions()

    assert set(versions) == set(CORE_DEPENDENCIES)
    assert versions == {
        "langgraph": "1.2.24",
        "pydantic": "2.14.4",
        "fastapi": "0.165.0",
        "litellm": "1.111.0",
    }


def test_bootstrap_status_has_safe_diagnostic_fields() -> None:
    status = collect_bootstrap_status()

    assert status["application"] == "Prompt Engineering Agent"
    assert status["stage"] == "Beta"
    assert status["python_supported"] is True
    assert status["real_model_call_performed"] is False
