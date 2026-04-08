from typing import TypedDict, List, Optional, Dict, Any, Annotated
import json
import operator
import os
from pydantic import BaseModel, Field


def _replace(existing, new):
    """Last-writer-wins reducer for LangGraph state channels.

    Must be a named function — anonymous lambdas create distinct objects
    per field which breaks LangGraph's channel deduplication on Python 3.14+.
    """
    return new


class FinancialLedger(BaseModel):
    project_budget_usd: float = 100.0
    accumulated_cost_usd: float = 0.0


class ShotExecutionPlan(BaseModel):
    shot_id: str
    target_duration_ms: int
    camera_movement: str  # High-level tag
    detailed_camera_plan: str = ""  # Detailed movement instructions
    action_description: str
    active_entities: List[str]
    # New detailed fields for visual fidelity
    staging_description: str = ""  # Character positions and environmental layout
    character_poses: Dict[str, str] = Field(
        default_factory=dict
    )  # Map of entity_id to specific pose/expression
    setting_details: str = ""  # Period-accurate details, lighting cues from prose
    era_context: str = ""  # Identified era for this specific scene/shot
    # Dialogue lines spoken during this shot
    dialogue: List[Dict[str, str]] = Field(
        default_factory=list
    )  # List of {speaker, line, emotion}
    # Editing logic — structured fields for shot variation enforcement
    shot_scale: str = ""  # One of: extreme_wide, wide, medium, close, extreme_close
    camera_angle: str = ""  # e.g. "eye-level frontal", "low-angle 45-degree side"
    # Spatial Layering Protocol — structured FG/MG/BG composition
    spatial_composition: Dict[str, str] = Field(
        default_factory=dict
    )  # Keys: framing_type, foreground_element, midground_subject, background_element, depth_of_field, composition_technique
    focus_subject: str = ""
    # Continuity linkage
    ending_composition_description: str = ""
    is_continuation: bool = False


class AFCState(TypedDict):
    workspace_root: Annotated[str, _replace]
    project_config: Annotated[Dict[str, Any], _replace]
    ledger: Annotated[FinancialLedger, _replace]
    novel_text: Annotated[str, _replace]

    unprocessed_scenes: Annotated[List[str], _replace]
    current_scene_path: Annotated[Optional[str], _replace]

    unprocessed_shots: Annotated[List[ShotExecutionPlan], _replace]
    active_shot_plan: Annotated[Optional[ShotExecutionPlan], _replace]

    current_proxy_path: Annotated[Optional[str], _replace]
    current_keyframe_path: Annotated[Optional[str], _replace]
    current_storyboard_path: Annotated[Optional[str], _replace]
    current_render_path: Annotated[Optional[str], _replace]

    scene_dailies_paths: Annotated[List[str], _replace]
    completed_scenes_paths: Annotated[List[str], operator.add]

    keyframe_retry_count: Annotated[int, _replace]
    render_retry_count: Annotated[int, _replace]
    continuity_feedback: Annotated[Optional[str], _replace]
    escalation_required: Annotated[bool, _replace]
    keyframe_is_reused_frame: Annotated[bool, _replace]


# ── Checkpoint save/load ──────────────────────────────────────────

CHECKPOINT_FILENAME = "checkpoint.json"


def save_checkpoint(workspace_root: str, state: AFCState) -> str:
    """Persist pipeline progress to disk after each completed shot/scene.

    Only serialises the fields needed to reconstruct a resume-able state.
    Returns the path to the checkpoint file.
    """
    data = {
        "unprocessed_scenes": state.get("unprocessed_scenes", []),
        "current_scene_path": state.get("current_scene_path"),
        "completed_scenes_paths": state.get("completed_scenes_paths", []),
        "scene_dailies_paths": state.get("scene_dailies_paths", []),
        "unprocessed_shots": [
            s.model_dump() for s in state.get("unprocessed_shots", [])
        ],
        "active_shot_plan": (
            state["active_shot_plan"].model_dump()
            if state.get("active_shot_plan")
            else None
        ),
    }
    ckpt_path = os.path.join(workspace_root, CHECKPOINT_FILENAME)
    with open(ckpt_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"💾 [Checkpoint] Saved to {ckpt_path}")
    return ckpt_path


def load_checkpoint(workspace_root: str) -> Optional[Dict[str, Any]]:
    """Load a checkpoint file if it exists. Returns None if not found."""
    ckpt_path = os.path.join(workspace_root, CHECKPOINT_FILENAME)
    if not os.path.exists(ckpt_path):
        return None
    with open(ckpt_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"💾 [Checkpoint] Loaded from {ckpt_path}")
    return data
