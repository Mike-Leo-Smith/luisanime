from typing import TypedDict, List, Dict, Any, Optional

class PipelineState(TypedDict):
    # --- Input Data ---
    project_dir: str
    style: str
    config: Dict[str, Any]
    novel_text: str
    current_chapter_id: str
    
    # --- Phase 1: AST & Style Compilation ---
    l3_graph_mutations: List[Dict[str, Any]] # Output from Lore Master
    scene_ir_blocks: List[Dict[str, Any]]    # Output from Screenwriter
    current_scene_index: int
    
    shot_list_ast: List[Dict[str, Any]]      # Output from Director
    current_shot_index: int
    
    master_art_spec: Optional[Dict[str, Any]] # Global style / character sheets
    art_style_spec: Optional[Dict[str, Any]] # Output from Art Director
    
    # --- Phase 2: Rasterization & Double-QA Loop ---
    # Image Layer (Storyboard)
    current_keyframe_url: Optional[str]
    image_retry_count: int
    image_qa_feedback: Optional[str]
    failed_frames: List[str]                  # ["begin"], ["end"], or ["begin", "end"]
    
    # Video Layer (Animation)
    current_video_candidate_url: Optional[str]
    video_retry_count: int
    video_qa_feedback: Optional[str]
    
    # --- Circuit Breaker Flags ---
    physics_downgrade_required: bool
    style_redefinition_required: bool
    
    # --- Output Data ---
    approved_video_assets: List[str]         # Passed all linters
    final_video_path: Optional[str]
    last_error: Optional[str]
