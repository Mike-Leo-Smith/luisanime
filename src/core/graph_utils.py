from typing import Any
import json


def extract_json(content: Any) -> Any:
    if isinstance(content, dict):
        content = content.get("text", str(content))
    elif isinstance(content, list):
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
