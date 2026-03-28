import json
from typing import Dict, Any
from src.pipeline.state import PipelineState
from src.schemas import ART_STYLE_SCHEMA
from src.agents.prompts import ART_DIRECTOR_SYSTEM_PROMPT, GLOBAL_ART_DIRECTOR_SYSTEM_PROMPT
from src.agents.utils import (
    get_llm_provider, 
    get_image_provider, 
    get_production_scene_path, 
    get_runtime_path,
    save_agent_metadata,
    retry_with_backoff
)

@retry_with_backoff(retries=3)
def _generate_global_spec(provider, prompt, system_prompt):
    return provider.generate_structured(
        prompt=prompt,
        response_schema=ART_STYLE_SCHEMA,
        system_prompt=system_prompt
    )

@retry_with_backoff(retries=3)
def _generate_ref_image(image_gen, prompt):
    return image_gen.generate_image(prompt)

def global_art_director(state: PipelineState) -> Dict:
    print("🌍 [Global Art Director] Establishing Master Visual Bible...")
    
    save_path = get_runtime_path(state, "style", "master_art_spec.json")
    if save_path.exists():
        print(f"  [Bypass] Loading existing Master Visual Bible from {save_path}")
        return {"master_art_spec": json.loads(save_path.read_text(encoding="utf-8"))}

    provider = get_llm_provider(state, "director")
    image_gen = get_image_provider(state, "storyboarder")
    
    style_dir = get_runtime_path(state, "style")
    style_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Generate Global Spec
        prompt = f"Establish Master Visual Style for: {state.get('style', 'anime')} adaptation. Lore: {state.get('l3_graph_mutations', [])}"
        result = _generate_global_spec(provider, prompt, GLOBAL_ART_DIRECTOR_SYSTEM_PROMPT)
        
        save_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        
        # 2. Generate Master Character Reference Sheets
        style_base = f"{state.get('style', 'anime')} style. Palette: {result['palette']['primary']}. {result['palette']['lighting_mood']}"
        for char in result.get("character_consistency", [])[:5]:
            char_name = char['name']
            version = char.get('version_name', 'default')
            print(f"  Creating Master Character Sheet: {char_name} ({version})...")
            char_prompt = f"MASTER CHARACTER SHEET: {char_name}, {version} version. {', '.join(char['visual_markers'])}. {style_base}."
            char_resp = _generate_ref_image(image_gen, char_prompt)
            safe_name = f"{char_name}_{version}".replace(" ", "_")
            (style_dir / f"master_char_{safe_name}.png").write_bytes(char_resp.image_bytes)

        return {"master_art_spec": result}
    except Exception as e:
        print(f"  [Global Art Director ERROR] {e}")
        return {"last_error": str(e)}

def art_director_node(state: PipelineState) -> Dict:
    print("🎨 [Art Director] Refining style for the current scene...")
    
    master_spec = state.get("master_art_spec", {})
    scenes = state.get("scene_ir_blocks", [])
    if not scenes: return {"last_error": "No scenes found"}
    
    idx = state.get("current_scene_index", 0)
    scene = scenes[idx]
    scene_id = scene["scene_id"]
    
    scene_art_dir = get_production_scene_path(state, scene_id, "art_style")
    if (scene_art_dir / "art_style.json").exists() and not state.get("style_redefinition_required"):
        print(f"  [Bypass] Loading existing scene art style from {scene_art_dir}")
        return {"art_style_spec": json.loads((scene_art_dir / "art_style.json").read_text(encoding="utf-8"))}

    provider = get_llm_provider(state, "director")
    image_gen = get_image_provider(state, "storyboarder")
    
    scene_art_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Generate Scene-Specific Spec
        redef_note = "🚨 REDEFINITION REQUIRED: Previous style attempts failed." if state.get("style_redefinition_required") else ""
        prompt = f"Refine Art Style for Scene {scene_id}: {scene}. Base Master Style: {master_spec}. {redef_note}"
        result = _generate_global_spec(provider, prompt, ART_DIRECTOR_SYSTEM_PROMPT)
        
        (scene_art_dir / "art_style.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))

        # 2. Generate Visual References
        print(f"  Generating references for scene {scene_id}...")
        style_base = f"{state.get('style', 'anime')} style. Palette: {result['palette']['primary']}. {result['palette']['lighting_mood']}"
        
        # Scenario Reference
        scen_resp = _generate_ref_image(image_gen, f"{style_base}. Background concept art of {scene['environment']['location']}. Consistency with Master Palette.")
        (scene_art_dir / "ref_environment.png").write_bytes(scen_resp.image_bytes)
        
        # Localized Character References
        master_chars = {c['name']: c for c in master_spec.get('character_consistency', [])}
        for char in result.get("character_consistency", [])[:2]:
            char_name = char['name']
            version = char.get('version_name', 'default')
            m_char = master_chars.get(char_name, {})
            all_markers = list(set(char.get('visual_markers', []) + m_char.get('visual_markers', [])))
            
            char_prompt = f"SCENE REFERENCE: {char_name}, {version}. {', '.join(all_markers)}. {style_base}. Action: {scene.get('chronological_actions', ['standing'])[0]}"
            char_resp = _generate_ref_image(image_gen, char_prompt)
            (scene_art_dir / f"ref_char_{char_name}_{version}.png").write_bytes(char_resp.image_bytes)

        return {
            "art_style_spec": result,
            "style_redefinition_required": False
        }
    except Exception as e:
        print(f"  [Art Director ERROR] {e}")
        return {"last_error": str(e)}
