from pea.config import ProviderConfig
from pea.models import GeneratedPrompt, IntentAnalysis
from pea.models.adapter import AdaptedPrompt, TargetModel
from pea.models.llm import ChatMessage


class ModelAdapter:
    def adapt(
        self,
        generated: GeneratedPrompt,
        intent: IntentAnalysis,
        target: TargetModel,
    ) -> AdaptedPrompt:
        ProviderConfig(provider=target.provider, model=target.model).litellm_model
        content = generated.content
        messages: list[ChatMessage]
        changes = []
        warnings = []

        role_marker = "## 专业视角\n"
        if content.startswith(role_marker) and "\n\n" in content:
            role_section, remainder = content.split("\n\n", 1)
            role = role_section.removeprefix(role_marker)
            if target.supports_system_message:
                messages = [
                    ChatMessage(role="system", content=role),
                    ChatMessage(role="user", content=remainder),
                ]
                changes.append("将专业视角拆分为目标模型支持的 system 消息")
            else:
                messages = [ChatMessage(role="user", content=content)]
                warnings.append("目标模型声明不支持 system 消息，专业视角保留在用户消息中")
        else:
            messages = [ChatMessage(role="user", content=content)]

        requires_json = any("json" in item.lower() for item in intent.output_requirements)
        if requires_json and not target.supports_json_mode:
            last = messages[-1]
            updated = last.model_copy(
                update={
                    "content": (
                        f"{last.content}\n\n直接输出合法 JSON；不要使用 Markdown 代码围栏，"
                        "不要在 JSON 前后添加解释。"
                    )
                }
            )
            messages[-1] = updated
            changes.append("未声明 JSON 模式时使用保守 JSON 指令，并禁止代码围栏")

        return AdaptedPrompt(
            provider=target.provider,
            model=target.model,
            messages=messages,
            max_output_tokens=target.max_output_tokens,
            changes=changes,
            warnings=warnings,
        )
