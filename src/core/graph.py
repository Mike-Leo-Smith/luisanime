from typing import List, Dict, Any, Union
from langgraph.graph import StateGraph, END
from src.core.state import PipelineState, EntityState
from src.config import load_config
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
import json

def lore_master(state: PipelineState) -> PipelineState:
    """Extracts entities and updates L3 memory using Gemini."""
    print("--- LORE MASTER: Extracting Entities ---")
    
    config = load_config()
    model_cfg = config.control_plane.agents["director_node"]
    
    llm = ChatGoogleGenerativeAI(
        model=model_cfg.model,
        google_api_key=model_cfg.api_key,
        temperature=model_cfg.temperature
    )
    
    prompt = f"""
    Extract key entities (characters, locations, unique items) from the following text.
    For each entity, specify its type (character, location, item) and a brief description.
    Return the result as a JSON object where keys are entity names.
    
    Text: {state['novel_text']}
    
    Format:
    {{
        "Entity Name": {{"type": "character/location/item", "description": "..."}}
    }}
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    # Simple JSON extraction from response
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        entities = json.loads(content)
        
        for name, info in entities.items():
            state["entity_graph"][name] = EntityState(
                id=name,
                attributes=info
            )
    except Exception as e:
        print(f"Error parsing Lore Master response: {e}")
        state["last_error"] = str(e)
        
    return state

from src.core.state import PipelineState, EntityState, SceneIR

def screenwriter(state: PipelineState) -> PipelineState:
    """Chunks text into scenes using Gemini."""
    print("--- SCREENWRITER: Chunking Scenes ---")
    
    config = load_config()
    model_cfg = config.control_plane.agents["director_node"]
    
    llm = ChatGoogleGenerativeAI(
        model=model_cfg.model,
        google_api_key=model_cfg.api_key,
        temperature=model_cfg.temperature
    )
    
    prompt = f"""
    Break the following novel text into a series of logical scenes.
    For each scene, provide:
    - id: unique scene identifier (e.g., scene_1)
    - location: where the scene takes place
    - time_of_day: e.g., Day, Night, Dusk
    - characters: list of character names present
    - description: a concise summary of what happens in the scene.
    
    Text: {state['novel_text']}
    
    Return the result as a JSON array of scene objects.
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        scenes_data = json.loads(content)
        state["scenes"] = [SceneIR(**s) for s in scenes_data]
    except Exception as e:
        print(f"Error parsing Screenwriter response: {e}")
        state["last_error"] = str(e)
        
    return state

from src.core.state import PipelineState, EntityState, SceneIR, Shot

def director(state: PipelineState) -> PipelineState:
    """Compiles Scene IR into a Shot List JSON using Gemini."""
    print("--- DIRECTOR: Generating Shot List ---")
    
    if not state["scenes"]:
        print("No scenes found to direct.")
        return state
        
    current_scene = state["scenes"][state["current_scene_index"]]
    
    config = load_config()
    model_cfg = config.control_plane.agents["director_node"]
    
    llm = ChatGoogleGenerativeAI(
        model=model_cfg.model,
        google_api_key=model_cfg.api_key,
        temperature=model_cfg.temperature
    )
    
    prompt = f"""
    Acting as a Film Director, convert the following scene description into a detailed Shot List for animation.
    
    Scene: {current_scene.description}
    Location: {current_scene.location}
    Time of Day: {current_scene.time_of_day}
    Characters: {', '.join(current_scene.characters)}
    
    For each shot, provide:
    - id: unique shot identifier (e.g., shot_1_1)
    - scene_id: {current_scene.id}
    - prompt: A highly detailed visual prompt for a video generation model.
    - camera_movement: e.g., Static, Pan Left, Zoom In, Crane Shot.
    - duration: duration in seconds (float).
    
    Rule: Decompose complex physical interactions into safe, renderable montages.
    
    Return the result as a JSON array of shot objects.
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        shots_data = json.loads(content)
        state["shot_list"] = [Shot(**s) for s in shots_data]
        state["current_shot_index"] = 0 # Reset shot index for new list
    except Exception as e:
        print(f"Error parsing Director response: {e}")
        state["last_error"] = str(e)
        
    return state

def generate_image_keyframe(prompt: str, config: Any) -> str:
    """
    Calls an Image Generation API (e.g., Nano Banana 2 via Google).
    Returns the URL of the generated image.
    """
    print(f"--- IMAGE GEN: {prompt} ---")
    # In a real implementation, this would use google-genai or similar
    # For now, return a mock URL
    return f"https://storage.googleapis.com/generated-keyframes/{prompt.replace(' ', '_')[:20]}.jpg"

def storyboarder(state: PipelineState) -> PipelineState:
    """Generates the first frame (Keyframe) for the current shot."""
    idx = state["current_shot_index"]
    shot = state["shot_list"][idx]
    
    print(f"--- STORYBOARDER: Generating Keyframe for Shot {shot.id} ---")
    
    config = load_config()
    
    # Generate the keyframe
    try:
        url = generate_image_keyframe(shot.prompt, config)
        state["shot_list"][idx].keyframe_url = url
        state["shot_list"][idx].status = "storyboarded"
    except Exception as e:
        print(f"Error in storyboarder: {e}")
        state["last_error"] = str(e)
        
    return state

def generate_video_clip(prompt: str, keyframe_url: str, config: Any) -> str:
    """
    Calls a Video Generation API (e.g., Veo, Sora, Kling).
    Returns the URL of the generated video.
    """
    print(f"--- VIDEO GEN: {prompt} ---")
    # In a real implementation, this would use a commercial Video API
    return f"https://storage.googleapis.com/generated-videos/{prompt.replace(' ', '_')[:20]}.mp4"

def animator(state: PipelineState) -> PipelineState:
    """Generates video from Keyframe and Prompt."""
    idx = state["current_shot_index"]
    shot = state["shot_list"][idx]
    
    print(f"--- ANIMATOR: Generating Video for Shot {shot.id} ---")
    
    config = load_config()
    
    try:
        if not shot.keyframe_url:
            raise ValueError(f"Shot {shot.id} is missing a keyframe.")
            
        video_url = generate_video_clip(shot.prompt, shot.keyframe_url, config)
        state["shot_list"][idx].video_url = video_url
        state["shot_list"][idx].status = "animated"
    except Exception as e:
        print(f"Error in animator: {e}")
        state["last_error"] = str(e)
        
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
