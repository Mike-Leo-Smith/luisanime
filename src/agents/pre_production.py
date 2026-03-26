from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from src.core.state import PipelineState, EntityState, SceneIR, Shot
from src.utils.json_utils import extract_json
from src.config import load_config


def lore_master(state: PipelineState) -> PipelineState:
    print("--- LORE MASTER: Extracting Entities ---")

    config = load_config()
    model_cfg = config.control_plane.agents["director_node"]

    llm = ChatGoogleGenerativeAI(
        model=model_cfg.model,
        google_api_key=model_cfg.api_key,
        temperature=model_cfg.temperature,
    )

    prompt = f"""
    Extract key entities (characters, locations, unique items) from the following text.
    For each entity, specify its type (character, location, item) and a brief description.
    Return the result as a JSON object where keys are entity names.
    
    Text: {state["novel_text"]}
    
    Format:
    {{
        "Entity Name": {{"type": "character/location/item", "description": "..."}}
    }}
    """

    response = llm.invoke([HumanMessage(content=prompt)])

    try:
        entities = extract_json(response.content)
        for name, info in entities.items():
            state["entity_graph"][name] = EntityState(id=name, attributes=info)
    except Exception as e:
        print(f"Error parsing Lore Master response: {e}")
        state["last_error"] = str(e)

    return state


def screenwriter(state: PipelineState) -> PipelineState:
    print("--- SCREENWRITER: Chunking Scenes ---")

    config = load_config()
    model_cfg = config.control_plane.agents["director_node"]

    llm = ChatGoogleGenerativeAI(
        model=model_cfg.model,
        google_api_key=model_cfg.api_key,
        temperature=model_cfg.temperature,
    )

    prompt = f"""
    Break the following novel text into a series of logical scenes.
    For each scene, provide:
    - id: unique scene identifier (e.g., scene_1)
    - location: where the scene takes place
    - time_of_day: e.g., Day, Night, Dusk
    - characters: list of character names present
    - description: a concise summary of what happens in the scene.
    
    Text: {state["novel_text"]}
    
    Return the result as a JSON array of scene objects.
    """

    response = llm.invoke([HumanMessage(content=prompt)])

    try:
        scenes_data = extract_json(response.content)
        state["scenes"] = [SceneIR(**s) for s in scenes_data]
    except Exception as e:
        print(f"Error parsing Screenwriter response: {e}")
        state["last_error"] = str(e)

    return state


def director(state: PipelineState) -> PipelineState:
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
        temperature=model_cfg.temperature,
    )

    prompt = f"""
    Acting as a Film Director, convert the following scene description into a detailed Shot List for animation.
    
    Scene: {current_scene.description}
    Location: {current_scene.location}
    Time of Day: {current_scene.time_of_day}
    Characters: {", ".join(current_scene.characters)}
    
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
        shots_data = extract_json(response.content)
        state["shot_list"] = [Shot(**s) for s in shots_data]
        state["current_shot_index"] = 0

    except Exception as e:
        print(f"Error parsing Director response: {e}")
        state["last_error"] = str(e)

    return state
