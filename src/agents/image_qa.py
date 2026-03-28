from typing import Dict, List
from src.pipeline.state import PipelineState
from src.schemas import QA_EVALUATION_SCHEMA
from src.agents.utils import get_llm_provider, get_production_shot_path, save_agent_metadata
from src.agents.prompts import IMAGE_QA_SYSTEM_PROMPT

def image_qa_node(state: PipelineState) -> Dict:
    """Evaluates the static keyframe for visual fidelity and prompt adherence."""
    idx = state["current_shot_index"]
    shot = state["shot_list_ast"][idx]
    scene_id = shot["scene_id"]
    shot_id = shot["shot_id"]
    
    print(f"🧐 [ImageQA] Analyzing keyframe for Shot {shot_id}...")
    
    shot_dir = get_production_shot_path(state, scene_id, shot_id)
    kb_path = shot_dir / "keyframe_begin.png"
    
    if not kb_path.exists():
        return {"image_qa_feedback": "Missing keyframe", "image_retry_count": state.get("image_retry_count", 0) + 1}

    provider = get_llm_provider(state, "image_qa")
    
    user_prompt = f"""
Intended Visual: {shot['visual_payload']['prompt_begin']}
QA Checklist: {shot['qa_checklist']}

Analyze the provided image.
Verify:
1. Does the frame match prompt_begin?
2. Is the character identity consistent with the story?
3. STYLE CHECK: Is this a SINGLE cinematic frame? Reject if it looks like a manga/comic panel, has text, or has sketch lines.
4. LANGUAGE CHECK: Is your 'reasoning' and 'mitigation_suggestion' in ENGLISH?
"""

    try:
        result = provider.generate_structured(
            prompt=user_prompt,
            response_schema=QA_EVALUATION_SCHEMA,
            system_prompt=IMAGE_QA_SYSTEM_PROMPT,
            media_path=str(kb_path)
        )
        
        # Save Report
        save_agent_metadata(shot_path := get_production_shot_path(state, scene_id, shot_id) / f"qa_report_image_take_{state.get('image_retry_count', 0)}.json", result)

        if result["is_pass"]:
            return {"image_qa_feedback": None, "image_retry_count": 0, "failed_frames": []}
        else:
            print(f"  [ImageQA REJECT] {result['failure_details']['failure_reason']}")
            return {
                "image_retry_count": state.get("image_retry_count", 0) + 1,
                "image_qa_feedback": result["failure_details"]["mitigation_suggestion"],
                "failed_frames": ["begin"]
            }
    except Exception as e:
        print(f"  [ImageQA Error] {e}")
        return {"image_qa_feedback": f"Error: {e}", "image_retry_count": state.get("image_retry_count", 0) + 1}
