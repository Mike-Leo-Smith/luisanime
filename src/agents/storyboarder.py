import json
from pathlib import Path
from typing import Dict, List
from src.pipeline.state import PipelineState
from src.agents.utils import (
    get_llm_provider,
    get_image_provider, 
    get_production_scene_path, 
    get_production_shot_path,
    get_runtime_path,
    pack_images,
    save_agent_metadata
)

def storyboarder(state: PipelineState) -> Dict:
    idx = state["current_shot_index"]
    shot = state["shot_list_ast"][idx]
    scene_id = shot["scene_id"]
    shot_id = shot["shot_id"]
    
    print(f"🖼️ [Storyboarder] Generating Keyframe for Shot {shot_id}...")
    
    # 1. Gather Reference Images
    style_dir = get_runtime_path(state, "style")
    scene_art_dir = get_production_scene_path(state, scene_id, "art_style")
    
    ref_images = []
    ref_descriptions = []
    
    env_ref = scene_art_dir / "ref_environment.png"
    if env_ref.exists(): 
        ref_images.append(env_ref)
        ref_descriptions.append("Image 1: Scene Environment/Location Concept")
    
    char_refs = sorted(list(scene_art_dir.glob("ref_char_*.png")))
    for i, cr in enumerate(char_refs[:2]):
        ref_images.append(cr)
        ref_descriptions.append(f"Image {len(ref_images)}: Character Reference ({cr.stem.replace('ref_char_', '')})")
    
    master_refs = sorted(list(style_dir.glob("master_char_*.png")))
    for mr in master_refs:
        if mr not in ref_images and len(ref_images) < 4:
            ref_images.append(mr)
            ref_descriptions.append(f"Image {len(ref_images)}: Master Design ({mr.stem.replace('master_char_', '')})")

    shot_path = get_production_shot_path(state, scene_id, shot_id)
    image_gen = get_image_provider(state, "storyboarder")
    prompt_architect = get_llm_provider(state, "image_qa") 

    ref_key = "\n".join(ref_descriptions)
    architect_system = """You are a Senior Cinematic Prompt Engineer. 
RULES:
1. SPATIAL REASONING: Define character positions (foreground, background, left, right).
2. ACTING: Specify poses and expressions based on novel prose.
3. GRID INDEXING: Refer to Reference Key (e.g., 'Match character Image 2').
4. STYLE: Force a cinematic video frame anime aesthetic. NO comic panels, grids, or text.
5. LANGUAGE: Prompt must be in ENGLISH. Keep proper names in original language."""

    negative_prompt = "photorealistic, realistic, 3d render, comic panels, grid, text, watermark, signature, blurry, low quality, distorted characters, extra limbs, speech bubbles, multiple views."

    try:
        # --- Generate SINGLE BEGIN frame ---
        img_begin = shot_path / "keyframe_begin.png"
        
        print("  Architecting prompt...")
        packed_ref = shot_path / "packed_references.png"
        pack_images(ref_images, packed_ref)
        
        qa_note = f"Previous QA Feedback: {state.get('image_qa_feedback')}" if state.get('image_qa_feedback') else ""
        arch_prompt = f"Novel Prose: {shot.get('source_prose', 'N/A')}\nScene Action: {shot['visual_payload']['prompt_begin']}\nReference Key:\n{ref_key}\n{qa_note}\nCompose a cinematic prompt."
        
        final_prompt = prompt_architect.generate_text(arch_prompt, system_prompt=architect_system).text
        
        print("  Generating keyframe...")
        resp = image_gen.generate_image(f"SUBJECT REFERENCE: {final_prompt}. NEGATIVE: {negative_prompt}", reference_media=str(packed_ref))
        img_begin.write_bytes(resp.image_bytes)
        
        save_agent_metadata(shot_path / "metadata_begin.json", {"architect_prompt": final_prompt})

        return {
            "current_keyframe_url": str(img_begin),
            "image_qa_feedback": None,
            "failed_frames": []
        }
    except Exception as e:
        print(f"  [Storyboarder ERROR] {e}")
        return {"last_error": str(e)}
