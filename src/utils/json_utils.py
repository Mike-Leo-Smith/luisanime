import json
from typing import Any


def extract_json(content: Any) -> Any:
    """Robustly extracts JSON from LLM response."""
    if isinstance(content, dict):
        content = content.get("text", str(content))
    elif isinstance(content, list):
        # Handle list of parts, some might be strings, some dicts
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(part.get("text", ""))
        content = "".join(parts)

    print(f"DEBUG: Processed content for extraction: {content}")

    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()

    return json.loads(content)
