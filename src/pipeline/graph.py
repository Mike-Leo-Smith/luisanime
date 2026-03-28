from typing import Dict, Any
from langgraph.graph import StateGraph, START, END
from src.pipeline.state import PipelineState
from src.agents.indexer import text_segmenter
from src.agents.lore_master import lore_master
from src.agents.screenwriter import screenwriter
from src.agents.director import director
from src.agents.art_director import art_director_node, global_art_director
from src.agents.storyboarder import storyboarder
from src.agents.animator import animator
from src.agents.image_qa import image_qa_node
from src.agents.video_qa import video_qa_node
from src.agents.compositor import lip_sync_agent, compositor

# --- Routing Functions ---

def route_after_image_qa(state: PipelineState) -> str:
    """Storyboard feedback loop with granular retry support."""
    if not state.get("failed_frames"):
        return "animator"
    elif state.get("image_retry_count", 0) >= 3:
        print("🚨 [IMAGE CIRCUIT BREAKER] Image QA failed 3 times. Fallback to Art Director.")
        return "fallback_to_art_director"
    else:
        return "retry_storyboarder"

def fallback_to_art_director(state: PipelineState) -> Dict:
    """Reset counts and force style redefinition."""
    return {
        "image_retry_count": 0,
        "style_redefinition_required": True,
        "failed_frames": ["begin", "end"] # Full reset
    }

def route_after_video_qa(state: PipelineState) -> str:
    """Animation feedback loop."""
    if state.get("video_qa_feedback") is None:
        if state["current_shot_index"] + 1 < len(state["shot_list_ast"]):
            return "next_shot" 
        elif state["current_scene_index"] + 1 < len(state.get("scene_ir_blocks", [])):
            return "next_scene"
        else:
            return "lip_sync"
    elif state.get("video_retry_count", 0) >= 3:
        print("🚨 [VIDEO CIRCUIT BREAKER] Video API failed 3 times. Fallback to Director.")
        return "fallback_to_director"
    else:
        return "animator"

# --- State Advancement Nodes ---

def advance_shot(state: PipelineState) -> Dict:
    return {
        "current_shot_index": state["current_shot_index"] + 1,
        "image_retry_count": 0,
        "video_retry_count": 0,
        "image_qa_feedback": None,
        "video_qa_feedback": None,
        "failed_frames": [],
        "current_keyframe_url": None,
        "current_video_candidate_url": None
    }

def advance_scene(state: PipelineState) -> Dict:
    return {
        "current_scene_index": state["current_scene_index"] + 1,
        "current_shot_index": 0,
        "shot_list_ast": [],
        "physics_downgrade_required": False,
        "style_redefinition_required": False,
        "failed_frames": []
    }

# --- Graph Assembly ---

workflow = StateGraph(PipelineState)

# Registration
workflow.add_node("text_segmenter", text_segmenter)
workflow.add_node("lore_master", lore_master)
workflow.add_node("global_art_director", global_art_director)
workflow.add_node("screenwriter", screenwriter)
workflow.add_node("director", director)
workflow.add_node("art_director", art_director_node)
workflow.add_node("storyboarder", storyboarder)
workflow.add_node("image_qa", image_qa_node)
workflow.add_node("animator", animator)
workflow.add_node("video_qa", video_qa_node)
workflow.add_node("advance_shot", advance_shot)
workflow.add_node("advance_scene", advance_scene)
workflow.add_node("fallback_to_art_director", fallback_to_art_director)
workflow.add_node("lip_sync", lip_sync_agent)
workflow.add_node("compositor", compositor)

# Static Pipeline
workflow.add_edge(START, "text_segmenter")
workflow.add_edge("text_segmenter", "lore_master")
workflow.add_edge("lore_master", "global_art_director")
workflow.add_edge("global_art_director", "screenwriter")
workflow.add_edge("screenwriter", "director")
workflow.add_edge("director", "art_director")
workflow.add_edge("art_director", "storyboarder")

# Double QA Loop
workflow.add_edge("storyboarder", "image_qa")

workflow.add_conditional_edges(
    "image_qa",
    route_after_image_qa,
    {
        "animator": "animator",
        "retry_storyboarder": "storyboarder",
        "fallback_to_art_director": "fallback_to_art_director"
    }
)

workflow.add_edge("fallback_to_art_director", "art_director")

workflow.add_edge("animator", "video_qa")

workflow.add_conditional_edges(
    "video_qa",
    route_after_video_qa,
    {
        "next_shot": "advance_shot",
        "next_scene": "advance_scene",
        "animator": "animator",
        "fallback_to_director": "director",
        "lip_sync": "lip_sync"
    }
)

workflow.add_edge("advance_shot", "storyboarder")
workflow.add_edge("advance_scene", "director")
workflow.add_edge("lip_sync", "compositor")
workflow.add_edge("compositor", END)

app = workflow.compile()
