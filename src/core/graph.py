from typing import List, Dict, Any, Union
from langgraph.graph import StateGraph, END
from src.core.state import PipelineState

def lore_master(state: PipelineState) -> PipelineState:
    """Extracts entities and updates L3 memory."""
    print("--- LORE MASTER: Extracting Entities ---")
    # Logic to extract characters, locations, etc.
    return state

def screenwriter(state: PipelineState) -> PipelineState:
    """Chunks text into scenes."""
    print("--- SCREENWRITER: Chunking Scenes ---")
    return state

def director(state: PipelineState) -> PipelineState:
    """Compiles Scene IR into a Shot List JSON."""
    print("--- DIRECTOR: Generating Shot List ---")
    return state

def storyboarder(state: PipelineState) -> PipelineState:
    """Generates the first frame (Keyframe) for the current shot."""
    print(f"--- STORYBOARDER: Generating Keyframe for Shot {state['current_shot_index']} ---")
    return state

def animator(state: PipelineState) -> PipelineState:
    """Generates video from Keyframe and Prompt."""
    print(f"--- ANIMATOR: Generating Video for Shot {state['current_shot_index']} ---")
    return state

def qa_linter(state: PipelineState) -> Union[PipelineState, str]:
    """Inspects the generated video."""
    print(f"--- QA LINTER: Inspecting Shot {state['current_shot_index']} ---")
    # Mock logic: for now, always pass
    return state

def lip_sync_agent(state: PipelineState) -> PipelineState:
    """Applies lip-sync locally to approved clips."""
    print("--- LIP-SYNC: Applying local mouth masking ---")
    return state

def compositor(state: PipelineState) -> PipelineState:
    """Stitches all clips into the final video."""
    print("--- COMPOSITOR: Final Stitching ---")
    return state

# --- Graph Construction ---

workflow = StateGraph(PipelineState)

# Define nodes
workflow.add_node("lore_master", lore_master)
workflow.add_node("screenwriter", screenwriter)
workflow.add_node("director", director)
workflow.add_node("storyboarder", storyboarder)
workflow.add_node("animator", animator)
workflow.add_node("qa_linter", qa_linter)
workflow.add_node("lip_sync", lip_sync_agent)
workflow.add_node("compositor", compositor)

# Define edges
workflow.set_entry_point("lore_master")
workflow.add_edge("lore_master", "screenwriter")
workflow.add_edge("screenwriter", "director")
workflow.add_edge("director", "storyboarder")
workflow.add_edge("storyboarder", "animator")
workflow.add_edge("animator", "qa_linter")

def route_qa(state: PipelineState) -> str:
    """Decides where to go after QA."""
    # Logic for re-rolling or falling back to Director
    # For now, just go to the next shot or finish
    if state['current_shot_index'] < len(state['shot_list']) - 1:
        # Increment index and loop back to storyboarder (next shot)
        # Note: In a real graph, you'd handle the increment in a node
        return "storyboarder"
    else:
        return "lip_sync"

workflow.add_conditional_edges(
    "qa_linter",
    route_qa,
    {
        "storyboarder": "storyboarder",
        "lip_sync": "lip_sync"
    }
)

workflow.add_edge("lip_sync", "compositor")
workflow.add_edge("compositor", END)

# Compile graph
app = workflow.compile()
