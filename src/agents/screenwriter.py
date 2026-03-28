from typing import Dict, List
from pathlib import Path
import json
from src.pipeline.state import PipelineState
from src.schemas import SCENE_IR_SCHEMA
from src.agents.utils import get_llm_provider, get_chapter_db, get_runtime_path

def screenwriter(state: PipelineState) -> Dict:
    print("🎭 [Screenwriter] Compiling prose into Scene IR blocks...")
    
    # Bypass removed to update blocks with prose
    # save_path = get_runtime_path(state, "screenplay", "scenes.json")
    
    chapter_db = get_chapter_db(state)
    provider = get_llm_provider(state, "screenwriter")
    
    all_scenes = []
    
    system_prompt = """You are a compiler frontend parsing prose into Scene Intermediate Representations (IR). 
Rule 1: A new scene block is created only when the continuous time breaks or the location changes.
Rule 2: Condense all prose into objective, chronological physical actions. 
Strip all dialogue tags and internal monologues."""

    chapters = chapter_db.get_all_chapters() if chapter_db else []
    
    for chapter in chapters:
        print(f"  Segmenting {chapter.id}...")
        user_prompt = f"Raw Chapter Text:\n---\n{chapter.text[:15000]}\n---\n\nExtract Scene IR."
        
        try:
            result = provider.generate_structured(
                prompt=user_prompt,
                response_schema=SCENE_IR_SCHEMA,
                system_prompt=system_prompt
            )
            for scene in result.get("scenes", []):
                scene["chapter_id"] = chapter.id
                if not scene["scene_id"].startswith(chapter.id):
                    scene["scene_id"] = f"{chapter.id}_{scene['scene_id']}"
                
                # Find the most relevant prose for this scene (heuristic: simple split or just full chapter if small)
                # For now, we attach the chapter text to help the Director see the 'flavor'
                scene["source_prose"] = chapter.text[:5000] # Limit to help context
                
                all_scenes.append(scene)
        except Exception as e:
            print(f"    [Screenwriter Warning] Failed chapter {chapter.id}: {e}")

    # Save to disk using systematic path
    save_path = get_runtime_path(state, "screenplay", "scenes.json")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(json.dumps(all_scenes, indent=2, ensure_ascii=False))

    return {
        "scene_ir_blocks": all_scenes,
        "current_scene_index": 0
    }
