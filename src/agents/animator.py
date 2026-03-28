from pathlib import Path
from typing import Dict
from src.pipeline.state import PipelineState
from src.agents.utils import get_video_provider, get_production_shot_path
from src.providers.base import VideoGenerationConfig

def animator(state: PipelineState) -> Dict:
    idx = state["current_shot_index"]
    shot = state["shot_list_ast"][idx]
    
    print(f"🎬 [Animator] Rasterizing Shot {shot['shot_id']} (Take {state.get('video_retry_count', 0) + 1})")
    
    if not state.get("current_keyframe_url"):
        return {"last_error": "Missing keyframe for animator"}

    try:
        provider = get_video_provider(state, "animator")
        
        # Load starting keyframe only
        shot_dir = get_production_shot_path(state, shot["scene_id"], shot["shot_id"])
        kb_path = shot_dir / "keyframe_begin.png"
        
        if not kb_path.exists():
            return {"last_error": f"Missing starting keyframe: {kb_path}"}
            
        kb_bytes = kb_path.read_bytes()
        
        # Use prompt_begin as the primary animation prompt
        prompt = shot["visual_payload"]["prompt_begin"]
        
        gen_config = VideoGenerationConfig(
            first_frame=kb_bytes,
            last_frame=None, # Explicitly no end frame constraint
            duration=6 
        )
        
        response = provider.generate_video(prompt, config=gen_config)
        
        # Systematic path: production/{scene_id}/{shot_id}/video.mp4
        shot_dir = get_production_shot_path(state, shot["scene_id"], shot["shot_id"])
        video_path = shot_dir / "video.mp4"
        video_path.write_bytes(response.video_bytes)
        
        return {
            "current_video_candidate_url": str(video_path),
            "video_qa_feedback": None
        }
    except Exception as e:
        print(f"  [Animator ERROR] {e}")
        return {"last_error": str(e)}
