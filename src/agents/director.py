from typing import Dict, Any
from pathlib import Path
import json
from src.pipeline.state import PipelineState
from src.schemas import SHOT_LIST_SCHEMA
from src.agents.utils import get_llm_provider, get_runtime_path
from src.agents.prompts import DIRECTOR_SYSTEM_PROMPT

def director(state: PipelineState) -> Dict:
    print("🎬 [Director] Resolving spatial constraints...")
    
    # Bypass removed to allow schema update (prompt_begin/end)
    # save_path = get_runtime_path(state, "shot_list.json")
    
    scenes = state.get("scene_ir_blocks", [])
    if not scenes:
        print("  Error: No scene IR blocks found.")
        return {"last_error": "No scene IR blocks"}

    idx = state.get("current_scene_index", 0)
    scene = scenes[idx]
    provider = get_llm_provider(state, "director")
    
    fallback_instruction = ""
    if state.get("physics_downgrade_required"):
        fallback_instruction = """🚨 FALLBACK TRIGGERED: MANDATORY DEGRADATION."""

    user_prompt = f"""{fallback_instruction}
Original Prose: {scene.get('source_prose', 'N/A')}
Scene IR: {scene}
L3 Entity Graph: {state.get('l3_graph_mutations', [])}
Master Art Style: {state.get('master_art_spec', {})}

Generate a detailed shot list. 
For each shot, provide high-detail 'prompt_begin' and 'prompt_end'.
Specify:
1. Spatial Layout: Where characters are standing (e.g., 'Dantes is foreground-left, looking towards the ship in the center-background').
2. Acting: Detailed physical poses and expressions (e.g., 'Elara has a hand on her chest, eyes wide with fear').
3. Environment: Specific lighting and atmospheric details from the prose.
"""

    try:
        result = provider.generate_structured(
            prompt=user_prompt,
            response_schema=SHOT_LIST_SCHEMA,
            system_prompt=DIRECTOR_SYSTEM_PROMPT
        )
        
        shots = result.get("shots", [])
        for s in shots:
            s["scene_id"] = scene["scene_id"]
            if not s["shot_id"].startswith(scene["scene_id"]):
                s["shot_id"] = f"{scene['scene_id']}_{s['shot_id']}"
        
        # Save to disk using systematic path
        save_path = get_runtime_path(state, "shot_list.json")
        save_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

        return {
            "shot_list_ast": shots,
            "current_shot_index": 0,
            "image_retry_count": 0,
            "video_retry_count": 0,
            "physics_downgrade_required": False,
            "video_qa_feedback": None
        }
    except Exception as e:
        print(f"  [Director ERROR] {e}")
        return {"last_error": str(e)}
