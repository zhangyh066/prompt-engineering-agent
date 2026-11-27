from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version
import os
import platform
import sys

from pea import __version__

PROVIDER_ENV_VARS = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
}

CORE_DEPENDENCIES = ("langgraph", "pydantic", "fastapi", "litellm")


def detect_model_providers(
    environ: Mapping[str, str] | None = None,
) -> dict[str, bool]:
    source = os.environ if environ is None else environ
    return {
        provider: any(source.get(name, "").strip() for name in names)
        for provider, names in PROVIDER_ENV_VARS.items()
    }


def get_dependency_versions() -> dict[str, str]:
    versions = {}
    for package in CORE_DEPENDENCIES:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "not installed"
    return versions


def collect_bootstrap_status() -> dict[str, object]:
    return {
        "application": "Prompt Engineering Agent",
        "version": __version__,
        "stage": "Beta",
        "python": platform.python_version(),
        "python_supported": sys.version_info >= (3, 12),
        "platform": platform.platform(),
        "dependencies": get_dependency_versions(),
        "model_providers_configured": detect_model_providers(),
        "real_model_call_performed": False,
    }
