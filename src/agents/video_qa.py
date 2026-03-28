from typing import Dict, List
from src.pipeline.state import PipelineState
from src.schemas import QA_EVALUATION_SCHEMA
from src.agents.utils import (
    get_llm_provider, 
    get_production_shot_path, 
    save_agent_metadata,
    sample_frames
)
from src.agents.prompts import VIDEO_QA_SYSTEM_PROMPT

def video_qa_node(state: PipelineState) -> Dict:
    """Evaluates the dynamic Video animation using sampled frames for token efficiency."""
    idx = state["current_shot_index"]
    shot = state["shot_list_ast"][idx]
    scene_id = shot["scene_id"]
    shot_id = shot["shot_id"]
    
    print(f"🧐 [VideoQA] Analyzing animation snapshots for Shot {shot_id}...")
    
    video_url = state.get("current_video_candidate_url")
    if not video_url:
        return {"video_qa_feedback": "Missing video", "video_retry_count": state.get("video_retry_count", 0) + 1}

    # --- Sample Frames for Token-Efficient Analysis ---
    shot_path = get_production_shot_path(state, scene_id, shot_id)
    qa_samples_dir = shot_path / "qa_samples"
    frame_paths = sample_frames(video_url, qa_samples_dir, num_frames=3)
    
    if not frame_paths:
        return {"video_qa_feedback": "Frame sampling failed", "video_retry_count": state.get("video_retry_count", 0) + 1}

    provider = get_llm_provider(state, "video_qa")
    
    user_prompt = f"""
Intended Shot Progression:
START: {shot['visual_payload']['prompt_begin']}
END: {shot['visual_payload']['prompt_end']}

QA Checklist: {shot['qa_checklist']}

The provided images are snapshots from the 0%, 50%, and 100% marks of the animation.
Verify:
1. Narrative Flow: Does the movement from Image 1 to Image 3 follow the intended progression?
2. Temporal Artifacts: Do characters or settings warp or 'melt' between samples?
3. Identity: Is the character and outfit consistent across all samples?
"""

    try:
        result = provider.generate_structured(
            prompt=user_prompt,
            response_schema=QA_EVALUATION_SCHEMA,
            system_prompt=VIDEO_QA_SYSTEM_PROMPT,
            media_path=[str(p) for p in frame_paths]
        )

        # Save Report
        save_agent_metadata(shot_path / f"qa_report_video_take_{state.get('video_retry_count', 0)}.json", result)

        if result["is_pass"]:
            approved = state.get("approved_video_assets", [])
            approved.append(video_url)
            return {
                "approved_video_assets": approved,
                "video_qa_feedback": None,
                "video_retry_count": 0
            }
        else:
            print(f"  [VideoQA REJECT] {result['failure_details']['failure_reason']}")
            return {
                "video_retry_count": state.get("video_retry_count", 0) + 1,
                "video_qa_feedback": result["failure_details"]["mitigation_suggestion"]
            }
    except Exception as e:
        print(f"  [VideoQA Error] {e}")
        return {"video_qa_feedback": f"Error: {e}", "video_retry_count": state.get("video_retry_count", 0) + 1}
