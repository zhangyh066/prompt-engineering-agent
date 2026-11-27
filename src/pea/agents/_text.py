import re
from collections.abc import Iterable


def split_clauses(text: str) -> list[str]:
    return [
        clause.strip(" \t\r\n-•")
        for clause in re.split(r"[\n。！？!?；;]+", text)
        if clause.strip(" \t\r\n-•")
    ]


def unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def contains_any(text: str, markers: Iterable[str]) -> bool:
    return any(marker in text for marker in markers)


def goal_is_preserved(goal: str, content: str) -> bool:
    objective, separator, context = goal.partition("\n\nContext:")
    return objective in content and (
        not separator or context.strip() in content
    )
