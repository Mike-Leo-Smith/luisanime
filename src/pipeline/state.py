from typing import TypedDict, List, Optional, Dict, Any, Annotated
import operator
from pydantic import BaseModel, Field


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
    # Continuity linkage
    ending_composition_description: str = ""
    is_continuation: bool = False


class AFCState(TypedDict):
    workspace_root: Annotated[str, lambda x, y: y]
    project_config: Annotated[Dict[str, Any], lambda x, y: y]
    ledger: Annotated[FinancialLedger, lambda x, y: y]
    novel_text: Annotated[str, lambda x, y: y]

    # Macro Queue (Scenes) - Replace with new list
    unprocessed_scenes: Annotated[List[str], lambda x, y: y]
    current_scene_path: Annotated[Optional[str], lambda x, y: y]

    # Micro Queue (Shots)
    unprocessed_shots: Annotated[List[ShotExecutionPlan], lambda x, y: y]
    active_shot_plan: Annotated[Optional[ShotExecutionPlan], lambda x, y: y]

    # Media State (Active Shot)
    current_proxy_path: Annotated[Optional[str], lambda x, y: y]
    current_keyframe_path: Annotated[Optional[str], lambda x, y: y]
    current_render_path: Annotated[Optional[str], lambda x, y: y]

    # Asset Assembly
    scene_dailies_paths: Annotated[
        List[str], lambda x, y: y
    ]  # Use replacement to allow clearing
    completed_scenes_paths: Annotated[List[str], operator.add]

    # Feedback & Escalation
    previs_retry_count: Annotated[int, lambda x, y: y]
    render_retry_count: Annotated[int, lambda x, y: y]
    continuity_feedback: Annotated[Optional[str], lambda x, y: y]
    escalation_required: Annotated[bool, lambda x, y: y]
