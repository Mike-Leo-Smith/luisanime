from langgraph.graph import StateGraph, END
from src.core.state import PipelineState
from src.config import load_config
from src.agents.pre_production import lore_master, screenwriter, director
from src.agents.asset_locking import storyboarder
from src.agents.production import animator, qa_linter
from src.agents.post_production import lip_sync_agent, compositor


workflow = StateGraph(PipelineState)


def advance_shot(state: PipelineState) -> PipelineState:
    state["current_shot_index"] = state["current_shot_index"] + 1
    return state


workflow.add_node("lore_master", lore_master)
workflow.add_node("screenwriter", screenwriter)
workflow.add_node("director", director)
workflow.add_node("storyboarder", storyboarder)
workflow.add_node("animator", animator)
workflow.add_node("qa_linter", qa_linter)
workflow.add_node("advance_shot", advance_shot)
workflow.add_node("lip_sync", lip_sync_agent)
workflow.add_node("compositor", compositor)

workflow.set_entry_point("lore_master")
workflow.add_edge("lore_master", "screenwriter")
workflow.add_edge("screenwriter", "director")
workflow.add_edge("director", "storyboarder")
workflow.add_edge("storyboarder", "animator")
workflow.add_edge("animator", "qa_linter")
workflow.add_edge("advance_shot", "storyboarder")


def route_qa(state: PipelineState) -> str:
    idx = state["current_shot_index"]
    shot = state["shot_list"][idx]

    config = load_config()
    max_retries = config.get("generation", {}).get("max_retries_per_shot", 3)

    if shot.status == "approved":
        if idx < len(state["shot_list"]) - 1:
            return "advance_shot"
        else:
            return "lip_sync"
    else:
        if state["retry_count"] < max_retries:
            return "animator"
        else:
            print(f"Max retries reached for shot {shot.id}. Falling back to Director.")
            return "director"


workflow.add_conditional_edges(
    "qa_linter",
    route_qa,
    {
        "advance_shot": "advance_shot",
        "lip_sync": "lip_sync",
        "animator": "animator",
        "director": "director",
    },
)

workflow.add_edge("lip_sync", "compositor")
workflow.add_edge("compositor", END)

app = workflow.compile()
