from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel

class EntityState(BaseModel):
    id: str
    attributes: Dict[str, Any]
    status: str = "active"

class SceneIR(BaseModel):
    id: str
    location: str
    time_of_day: str
    characters: List[str]
    description: str

class Shot(BaseModel):
    id: str
    scene_id: str
    prompt: str
    camera_movement: str
    duration: float
    keyframe_url: Optional[str] = None
    video_url: Optional[str] = None
    status: str = "pending" # pending, storyboarded, animated, qa_failed, approved

class PipelineState(TypedDict):
    # Narrative Context
    novel_text: str
    current_chapter_id: str
    
    # L3 Memory: Persistent Entity Graph
    entity_graph: Dict[str, EntityState]
    
    # L2 Scene Graph: Sliding Window
    scenes: List[SceneIR]
    current_scene_index: int
    
    # L1 Working Register: Current Shot Plan
    shot_list: List[Shot]
    current_shot_index: int
    
    # QA & Loop Routing
    retry_count: int
    last_error: Optional[str]
    
    # Final Output
    approved_clips: List[str] # Paths to local .mp4 files
