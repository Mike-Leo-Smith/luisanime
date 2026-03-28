import os

os.makedirs('src/pipeline', exist_ok=True)
os.makedirs('src/agents', exist_ok=True)

with open('src/pipeline/state.py', 'w') as f:
    f.write('''from typing import TypedDict, List, Optional
from pydantic import BaseModel

class FinancialLedger(BaseModel):
    project_budget_usd: float = 100.0
    accumulated_cost_usd: float = 0.0

class ShotExecutionPlan(BaseModel):
    shot_id: str
    target_duration_ms: int
    camera_movement: str
    action_description: str
    active_entities: List[str]

class AFCState(TypedDict):
    workspace_root: str
    ledger: FinancialLedger
    
    # Macro Queue (Scenes)
    unprocessed_scenes: List[str]  # Paths to scene.json files
    current_scene_path: Optional[str]
    
    # Micro Queue (Shots)
    unprocessed_shots: List[ShotExecutionPlan]
    active_shot_plan: Optional[ShotExecutionPlan]
    
    # Media State (Active Shot)
    current_proxy_path: Optional[str]
    current_keyframe_path: Optional[str]
    current_render_path: Optional[str]
    
    # Asset Assembly
    scene_dailies_paths: List[str]      # Completed shots for the current scene
    completed_scenes_paths: List[str]   # Completed master scenes
    
    # Feedback & Escalation
    previs_retry_count: int
    render_retry_count: int
    continuity_feedback: Optional[str]
    escalation_required: bool
''')

with open('src/schemas.py', 'w') as f:
    f.write('''from pydantic import BaseModel, Field
from typing import List, Optional

class MediaPipeValidationReport(BaseModel):
    status: str = Field(description="Enum: PASS, FAIL_ANATOMY")
    anomaly_frame_index: Optional[int] = Field(None, description="The exact frame number where the topological collapse or failure occurred.")
    bone_length_variance: Optional[float] = Field(None, description="The maximum detected percentage change in bone length (must remain < 5%).")
    finger_count_max: Optional[int] = Field(None, description="The maximum number of distinct distal phalanges detected (must be <= 5 per hand).")
    rigid_prop_curvature: Optional[float] = Field(None, description="Degree of deviation from the Hough Line Transform vector.")

class FFMPEGTimelineTrack(BaseModel):
    source_path: str
    start_time_ms: int
    end_time_ms: int
    clip_id: str

class FFMPEGAudioTrack(BaseModel):
    source_path: str
    insert_time_ms: int
    volume_db: float

class FFMPEGTimelineJSON(BaseModel):
    timeline_id: str
    resolution: dict = Field(description="Specifies width and height based on the global project configuration.")
    video_tracks: List[FFMPEGTimelineTrack]
    audio_tracks: List[FFMPEGAudioTrack]
    transitions: List[dict] = Field(default_factory=list, description="Defines cross-fades or hard cuts between sequential clip_ids.")
''')

