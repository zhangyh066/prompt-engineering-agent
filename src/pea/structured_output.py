import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from pea.exceptions import InvalidResponseError

ModelT = TypeVar("ModelT", bound=BaseModel)


class StructuredOutputParser:
    @staticmethod
    def parse(model_type: type[ModelT], content: str) -> ModelT:
        stripped = content.strip()
        fence = re.fullmatch(
            r"```(?:json)?\s*(.*?)\s*```",
            stripped,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if fence:
            stripped = fence.group(1)
        try:
            return model_type.model_validate_json(stripped)
        except ValidationError as error:
            raise InvalidResponseError(
                f"structured output does not match {model_type.__name__}"
            ) from error
