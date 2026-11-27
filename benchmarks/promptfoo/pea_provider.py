from pea.agents import StructuredPromptOptimizer
from pea.models import PromptOptimizationRequest


def call_api(prompt, options, context):
    result = StructuredPromptOptimizer().optimize(
        PromptOptimizationRequest(
            user_request="Optimize this prompt without changing its intent.",
            raw_prompt=prompt,
        )
    )
    return {"output": result.generated_prompt.content}
