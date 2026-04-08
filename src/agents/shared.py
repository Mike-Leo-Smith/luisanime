"""Shared utilities for AFP agents.

Consolidates duplicated patterns across cinematographer, lead_animator,
production_designer, and previs_artist into reusable functions.
"""

from typing import Dict, List, Optional, Tuple

from src.pipeline.workspace import AgenticWorkspace


DEFAULT_MASTER_STYLE = "Cinematic, high fidelity."


def extract_scene_id(shot_id: str) -> Optional[str]:
    """Extracts scene_id from a shot_id (e.g. 'scene_01_SHOT_001' -> 'scene_01')."""
    parts = shot_id.rsplit("_SHOT_", 1)
    return parts[0] if len(parts) == 2 else None


def load_master_style(workspace: AgenticWorkspace) -> str:
    """Reads master_style.md from lore bible, returns default if missing."""
    try:
        return workspace.read_file("03_lore_bible/master_style.md")
    except FileNotFoundError:
        return DEFAULT_MASTER_STYLE


def load_style_preset(project_config: Dict) -> Tuple[str, str, str]:
    """Returns (style_key, prompt_prefix, prompt_suffix) from project config."""
    style_key = project_config.get("video", {}).get("style", "cinematic")
    preset = project_config.get("style_presets", {}).get(style_key, {})
    prefix = preset.get("prompt_prefix", "")
    suffix = preset.get("prompt_suffix", "")
    return style_key, prefix, suffix


def fetch_lore_context(
    workspace: AgenticWorkspace, entities: List[str], log_prefix: str = ""
) -> str:
    """Retrieves lore descriptions for the given entities from the lore bible."""
    if log_prefix:
        print(f"{log_prefix} Gathering lore for {entities}...")
    context = []
    for entity in entities:
        try:
            lore = workspace.read_file(f"03_lore_bible/{entity}.md")
            context.append(lore)
        except FileNotFoundError:
            pass
    return "\n".join(context)


def fetch_design_references(
    workspace: AgenticWorkspace,
    entities: List[str],
    scene_id: Optional[str] = None,
) -> List[str]:
    """Fetches entity design image paths, preferring scene-specific over global."""
    designs = []
    for entity in entities:
        if scene_id:
            scene_path = f"03_lore_bible/designs/scenes/{scene_id}/{entity}.png"
            if workspace.exists(scene_path):
                designs.append(scene_path)
                continue
        path = f"03_lore_bible/designs/{entity}.png"
        if workspace.exists(path):
            designs.append(path)
    return designs


def fetch_location_references(
    workspace: AgenticWorkspace,
    scene_json_path: str,
    scene_id: Optional[str] = None,
    log_prefix: str = "",
) -> List[str]:
    """Fetches location design image paths from the scene JSON."""
    refs = []
    try:
        scene_data = workspace.read_json(scene_json_path)
        location = scene_data.get("physical_location", "")
        if location:
            safe_name = location.replace("/", "_").replace("\\", "_")
            if scene_id:
                scene_loc_path = (
                    f"03_lore_bible/designs/scenes/{scene_id}/locations/{safe_name}.png"
                )
                if workspace.exists(scene_loc_path):
                    refs.append(scene_loc_path)
                    if log_prefix:
                        print(
                            f"{log_prefix} Found scene location design: {scene_loc_path}"
                        )
                    return refs
            path = f"03_lore_bible/designs/locations/{safe_name}.png"
            if workspace.exists(path):
                refs.append(path)
                if log_prefix:
                    print(f"{log_prefix} Found location design: {path}")
    except Exception as e:
        if log_prefix:
            print(f"{log_prefix} Could not load location design: {e}")
    return refs


def fetch_all_design_references(
    workspace: AgenticWorkspace,
    entities: List[str],
    scene_json_path: Optional[str],
    scene_id: Optional[str] = None,
    log_prefix: str = "",
    return_physical: bool = False,
) -> List[str]:
    """Fetches both entity and location design references.

    When return_physical=True, returns physical filesystem paths.
    Otherwise returns virtual workspace paths.
    """
    designs = fetch_design_references(workspace, entities, scene_id=scene_id)
    if scene_json_path:
        designs += fetch_location_references(
            workspace, scene_json_path, scene_id=scene_id, log_prefix=log_prefix
        )
    if return_physical:
        return [workspace.get_physical_path(p) for p in designs]
    return designs


def build_clothing_block(
    workspace: AgenticWorkspace,
    character_poses: Dict[str, str],
) -> str:
    """Builds clothing/appearance description block for keyframe/video prompts."""
    clothing_lines = []
    for entity_id, pose in character_poses.items():
        try:
            lore = workspace.read_file(f"03_lore_bible/{entity_id}.md")
            clothing_lines.append(
                f"{entity_id}: {pose}. Appearance from lore: {lore[:1500]}"
            )
        except FileNotFoundError:
            clothing_lines.append(f"{entity_id}: {pose}")
    block = "\n".join(clothing_lines) if clothing_lines else "See INITIAL POSES."
    return block


def build_appearance_block(
    workspace: AgenticWorkspace,
    character_poses: Dict[str, str],
) -> str:
    """Builds appearance description block for video prompts (lead_animator style)."""
    appearance_lines = []
    for entity_id, pose in character_poses.items():
        try:
            lore = workspace.read_file(f"03_lore_bible/{entity_id}.md")
            appearance_lines.append(f"- {entity_id}: {pose}. Appearance: {lore[:1500]}")
        except FileNotFoundError:
            appearance_lines.append(f"- {entity_id}: {pose}")
    block = "\n".join(appearance_lines) if appearance_lines else "See keyframe image."
    return block


def build_dialogue_block_keyframe(dialogue: List[Dict]) -> str:
    """Builds dialogue block for keyframe generation prompts."""
    if not dialogue:
        return ""
    lines = []
    for d in dialogue:
        lines.append(
            f'- {d.get("speaker", "Unknown")} ({d.get("emotion", "neutral")}): "{d.get("line", "")}"'
        )
    return f"""
DIALOGUE IN THIS SHOT (use to inform character expressions and mouth positions):
{chr(10).join(lines)}
Characters who are speaking should have appropriate mouth positions and facial expressions matching their dialogue."""


def build_dialogue_block_video(dialogue: List[Dict]) -> str:
    """Builds dialogue block for video generation prompts."""
    if not dialogue:
        return ""
    lines = []
    for d in dialogue:
        speaker = d.get("speaker", "a character")
        emotion = d.get("emotion", "neutral")
        line = d.get("line", "")
        lines.append(f'- {speaker} ({emotion}): "{line}"')
    return f"""
        DIALOGUE DURING THIS SHOT (include spoken lines EXACTLY as written in quotation marks):
        {chr(10).join(lines)}
        Include each dialogue line as: the character says "exact line here". Describe matching lip movement, facial expressions (physical descriptors), and body language."""


def build_spatial_block(
    spatial_composition: Optional[Dict],
    shot_scale: str = "medium",
    camera_angle: str = "eye-level frontal",
    for_video: bool = False,
) -> str:
    """Builds spatial layering protocol block for prompts.

    for_video=True uses the lead_animator variant; False uses the cinematographer variant.
    """
    sc = spatial_composition or {}
    if not sc.get("framing_type"):
        return ""

    if for_video:
        return f"""
        SPATIAL LAYERING (preserve these depth layers throughout the video):
        Shot Scale: {shot_scale} | Camera Angle: {camera_angle}
        Framing: {sc.get("framing_type", "standard")} | Technique: {sc.get("composition_technique", "standard")}
        (FG) Foreground: {sc.get("foreground_element", "none")}
        (MG) Midground Subject: {sc.get("midground_subject", "primary subject")}
        (BG) Background: {sc.get("background_element", "environment")}
        Depth of Field: {sc.get("depth_of_field", "cinematic")}
        Maintain these spatial layers throughout — FG visible, MG moves as described, BG provides consistent context."""
    else:
        return f"""
SPATIAL LAYERING PROTOCOL — [空间关系与焦段] + [FG] + [MG] + [BG] + [光影与景深控制]:
SHOT SCALE: {shot_scale} | CAMERA ANGLE: {camera_angle}
FRAMING TYPE: {sc.get("framing_type", "standard")}
COMPOSITION TECHNIQUE: {sc.get("composition_technique", "standard")}
(FG) FOREGROUND: {sc.get("foreground_element", "none")} — render with appropriate blur/bokeh per depth of field.
(MG) MIDGROUND SUBJECT: {sc.get("midground_subject", "primary subject in focus")} — sharply focused primary subject.
(BG) BACKGROUND: {sc.get("background_element", "environmental context")} — render at appropriate focus distance.
DEPTH OF FIELD: {sc.get("depth_of_field", "standard cinematic depth")}
Compose so three layers create volumetric depth."""
