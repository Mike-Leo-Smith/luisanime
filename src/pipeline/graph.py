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


def route_macro_loop(state: AFCState) -> Literal["director", "__end__"]:
    if state.get("unprocessed_scenes") and not state.get("escalation_required"):
        return "director"
    return "__end__"


def route_after_script_coordinator(
    state: AFCState,
) -> Literal["production_designer", "editor"]:
    if state.get("active_shot_plan") or state.get("unprocessed_shots"):
        return "production_designer"
    return "editor"


def route_after_continuity_supervisor(
    state: AFCState,
) -> Literal["lead_animator", "cinematographer", "script_coordinator", "director"]:
    current_render = state.get("current_render_path")
    feedback = state.get("continuity_feedback")
    is_render_phase = current_render is not None and feedback is not None

    if is_render_phase:
        if not feedback:
            return "script_coordinator"
        else:
            retry_count = state.get("render_retry_count", 0)
            if retry_count >= 3:
                print("🚨 [CIRCUIT BREAKER] Escalate to Director")
                return "director"
            return "lead_animator"
    else:
        if not feedback:
            return "lead_animator"
        else:
            return "cinematographer"


workflow = StateGraph(AFCState)

workflow.add_node("showrunner", showrunner_node)
workflow.add_node("screenwriter", screenwriter_node)
workflow.add_node("production_designer", production_designer_node)
workflow.add_node("director", director_node)
workflow.add_node("script_coordinator", script_coordinator_node)
workflow.add_node("cinematographer", cinematographer_node)
workflow.add_node("lead_animator", lead_animator_node)
workflow.add_node("continuity_supervisor", continuity_supervisor_node)
workflow.add_node("editor", editor_node)

workflow.add_edge(START, "screenwriter")
workflow.add_edge("screenwriter", "showrunner")

workflow.add_conditional_edges(
    "showrunner", route_macro_loop, {"director": "director", "__end__": END}
)
workflow.add_edge("director", "script_coordinator")

workflow.add_conditional_edges(
    "script_coordinator",
    route_after_script_coordinator,
    {"production_designer": "production_designer", "editor": "editor"},
)

workflow.add_edge("production_designer", "cinematographer")
workflow.add_edge("cinematographer", "continuity_supervisor")
workflow.add_edge("lead_animator", "continuity_supervisor")

workflow.add_conditional_edges(
    "continuity_supervisor",
    route_after_continuity_supervisor,
    {
        "lead_animator": "lead_animator",
        "cinematographer": "cinematographer",
        "script_coordinator": "script_coordinator",
        "director": "director",
    },
)

workflow.add_edge("editor", "showrunner")

app = workflow.compile()
