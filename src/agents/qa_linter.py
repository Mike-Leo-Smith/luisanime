from src.core.state import PipelineState
from src.schemas import QA_SCHEMA
from src.agents.utils import get_llm_provider


def qa_linter(state: PipelineState) -> PipelineState:
    idx = state["current_shot_index"]
    shot = state["shot_list"][idx]

    print(f"--- QA LINTER: Inspecting Shot {shot.id} ---")

    provider = get_llm_provider(state, "qa_linter")

    prompt = f"""Inspect the following generated video clip against the intended prompt.

Intended Prompt: {shot.prompt}
Video Path: {shot.video_url}

Perform the following checks:
1. Topological Check: Are there limb melting or multi-finger mutations?
2. Consistency Check: Does the character match the established visual reference?
3. Physical Hallucination: Are there impossible physics or fluid-like rigid bodies?

Return your assessment following the JSON schema."""

    try:
        qa_result = provider.generate_structured(
            prompt=prompt, response_schema=QA_SCHEMA
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
