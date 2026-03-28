from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END
from src.pipeline.state import AFCState
from src.agents.showrunner import showrunner_node
from src.agents.screenwriter import screenwriter_node
from src.agents.production_designer import production_designer_node
from src.agents.director import director_node
from src.agents.script_coordinator import script_coordinator_node
from src.agents.cinematographer import cinematographer_node
from src.agents.lead_animator import lead_animator_node
from src.agents.continuity_supervisor import continuity_supervisor_node
from src.agents.editor import editor_node

# --- Routing Functions ---

def route_macro_loop(state: AFCState) -> Literal["director", "__end__"]:
    """Showrunner routes the macro loop."""
    if state.get("unprocessed_scenes") and not state.get("escalation_required"):
        return "director"
    return "__end__"

def route_after_director(state: AFCState) -> Literal["script_coordinator"]:
    """Director broadcasts narrative events."""
    return "script_coordinator"

def route_after_script_coordinator(state: AFCState) -> Literal["production_designer", "editor"]:
    """Enter micro loop (Lazy Designer) or finish scene."""
    if state.get("active_shot_plan") or state.get("unprocessed_shots"):
        return "production_designer"
    return "editor"

def route_after_keyframe_qa(state: AFCState) -> Literal["lead_animator", "cinematographer"]:
    """QA evaluates Keyframe quality."""
    if state.get("continuity_feedback"):
        # Fail, retry keyframe
        return "cinematographer"
    return "lead_animator"

def route_after_animator_qa(state: AFCState) -> Literal["script_coordinator", "lead_animator", "director"]:
    """QA evaluates Final Render fidelity."""
    if state.get("continuity_feedback"):
        if state.get("render_retry_count", 0) >= 3:
            print("🚨 [CIRCUIT BREAKER] Escalate to Director")
            return "director"
        return "lead_animator"
    return "script_coordinator"

# --- Graph Assembly ---

workflow = StateGraph(AFCState)

# Registration
workflow.add_node("showrunner", showrunner_node)
workflow.add_node("screenwriter", screenwriter_node)
workflow.add_node("production_designer", production_designer_node)
workflow.add_node("director", director_node)
workflow.add_node("script_coordinator", script_coordinator_node)
workflow.add_node("cinematographer", cinematographer_node)
workflow.add_node("lead_animator", lead_animator_node)
workflow.add_node("continuity_supervisor", continuity_supervisor_node)
workflow.add_node("editor", editor_node)

# Static Pipeline Initiation
workflow.add_edge(START, "screenwriter")
workflow.add_edge("screenwriter", "showrunner")

# Macro Loop
workflow.add_conditional_edges("showrunner", route_macro_loop, {
    "director": "director",
    "__end__": END
})

workflow.add_edge("director", "script_coordinator")

# Micro Loop
workflow.add_conditional_edges("script_coordinator", route_after_script_coordinator, {
    "production_designer": "production_designer",
    "editor": "editor"
})

workflow.add_edge("production_designer", "cinematographer")

# Keyframe QA Stage
workflow.add_edge("cinematographer", "continuity_supervisor")

workflow.add_conditional_edges("continuity_supervisor", route_after_keyframe_qa, {
    "lead_animator": "lead_animator",
    "cinematographer": "cinematographer"
})

# Render QA Stage
workflow.add_edge("lead_animator", "continuity_supervisor")

workflow.add_conditional_edges("continuity_supervisor", route_after_animator_qa, {
    "script_coordinator": "script_coordinator", 
    "lead_animator": "lead_animator", 
    "director": "director" 
})

workflow.add_edge("editor", "showrunner")

app = workflow.compile()
