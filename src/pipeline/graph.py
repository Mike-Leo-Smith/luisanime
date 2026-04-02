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
    unprocessed = state.get("unprocessed_scenes", [])
    escalation = state.get("escalation_required", False)
    print(f"\n{'=' * 60}")
    print(f"🔀 [ROUTER] route_macro_loop")
    print(f"   unprocessed_scenes: {len(unprocessed)} remaining — {unprocessed}")
    print(f"   escalation_required: {escalation}")
    if unprocessed and not escalation:
        print(f"   ➡️  DECISION: Route to 'director' (scenes remain)")
        print(f"{'=' * 60}\n")
        return "director"
    reason = "no scenes left" if not unprocessed else "escalation required"
    print(f"   ➡️  DECISION: Route to '__end__' ({reason})")
    print(f"{'=' * 60}\n")
    return "__end__"


def route_after_script_coordinator(
    state: AFCState,
) -> Literal["production_designer", "editor"]:
    active_shot = state.get("active_shot_plan")
    unprocessed = state.get("unprocessed_shots", [])
    print(f"\n{'=' * 60}")
    print(f"🔀 [ROUTER] route_after_script_coordinator")
    print(f"   active_shot_plan: {active_shot.shot_id if active_shot else None}")
    print(f"   unprocessed_shots: {len(unprocessed)} remaining")
    if active_shot or unprocessed:
        print(f"   ➡️  DECISION: Route to 'production_designer' (shots to process)")
        print(f"{'=' * 60}\n")
        return "production_designer"
    print(f"   ➡️  DECISION: Route to 'editor' (all shots done for this scene)")
    print(f"{'=' * 60}\n")
    return "editor"


def route_after_continuity_supervisor(
    state: AFCState,
) -> Literal["lead_animator", "cinematographer", "script_coordinator", "director"]:
    current_render = state.get("current_render_path")
    feedback = state.get("continuity_feedback")
    current_keyframe = state.get("current_keyframe_path")
    is_render_phase = current_render is not None
    render_retries = state.get("render_retry_count", 0)
    keyframe_retries = state.get("keyframe_retry_count", 0)

    print(f"\n{'=' * 60}")
    print(f"🔀 [ROUTER] route_after_continuity_supervisor")
    print(f"   current_render_path: {current_render}")
    print(f"   current_keyframe_path: {current_keyframe}")
    print(f"   continuity_feedback: {feedback[:100] if feedback else None}")
    print(f"   is_render_phase: {is_render_phase}")
    print(f"   render_retry_count: {render_retries}")
    print(f"   keyframe_retry_count: {keyframe_retries}")

    if is_render_phase:
        if not feedback:
            print(
                f"   ➡️  DECISION: Route to 'script_coordinator' (render approved, next shot)"
            )
            print(f"{'=' * 60}\n")
            return "script_coordinator"
        else:
            if render_retries >= 3:
                print(
                    f"   🚨 [CIRCUIT BREAKER] render_retry_count={render_retries} >= 3"
                )
                print(
                    f"   ➡️  DECISION: Route to 'director' (escalate for simplification)"
                )
                print(f"{'=' * 60}\n")
                return "director"
            print(
                f"   ➡️  DECISION: Route to 'lead_animator' (re-render, retry #{render_retries + 1})"
            )
            print(f"{'=' * 60}\n")
            return "lead_animator"
    else:
        if not feedback:
            print(
                f"   ➡️  DECISION: Route to 'lead_animator' (keyframe approved, generate video)"
            )
            print(f"{'=' * 60}\n")
            return "lead_animator"
        else:
            if keyframe_retries >= 3:
                print(
                    f"   🚨 [CIRCUIT BREAKER] keyframe_retry_count={keyframe_retries} >= 3"
                )
                print(
                    f"   ➡️  DECISION: Route to 'director' (escalate for simplification)"
                )
                print(f"{'=' * 60}\n")
                return "director"
            print(
                f"   ➡️  DECISION: Route to 'cinematographer' (keyframe rejected, regenerate)"
            )
            print(f"{'=' * 60}\n")
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
