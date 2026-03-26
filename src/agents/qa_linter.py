from src.core.state import PipelineState
from src.schemas import QA_SCHEMA
from src.agents.utils import get_llm_provider
from src.agents.prompts import QA_LINTER_SYSTEM_PROMPT


def qa_linter(state: PipelineState) -> PipelineState:
    idx = state["current_shot_index"]
    shot = state["shot_list"][idx]

    print(f"--- QA LINTER: Inspecting Shot {shot.id} ---")

    provider = get_llm_provider(state, "qa_linter")

    user_prompt = f"""Intended Prompt: {shot.prompt}
Video Path: {shot.video_url}

Evaluate this video against the intended prompt."""

    try:
        qa_result = provider.generate_structured(
            prompt=user_prompt,
            response_schema=QA_SCHEMA,
            system_prompt=QA_LINTER_SYSTEM_PROMPT,
        )

        status = qa_result.get("status", "rejected")
        reason = qa_result.get("reason", "No reason provided")
        issues = qa_result.get("issues", [])

        if status == "approved":
            state["shot_list"][idx].status = "approved"
            state["retry_count"] = 0
            if shot.video_url:
                state["approved_clips"].append(shot.video_url)
            print(f"  QA APPROVED")
        else:
            state["shot_list"][idx].status = "qa_failed"
            state["retry_count"] += 1
            print(f"  QA REJECTED: {reason}")
            if issues:
                for issue in issues:
                    print(f"    - {issue}")
    except Exception as e:
        print(f"Error in QA Linter: {e}")
        state["last_error"] = str(e)

    return state
