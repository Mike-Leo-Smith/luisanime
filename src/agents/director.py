from src.core.state import PipelineState, Shot
from src.schemas import SHOT_SCHEMA
from src.agents.utils import get_llm_provider, get_chapter_db
from src.agents.prompts import DIRECTOR_SYSTEM_PROMPT


def director(state: PipelineState) -> PipelineState:
    print("--- DIRECTOR: Generating Shot List ---")

    if not state["scenes"]:
        print("No scenes found to direct.")
        return state

    current_scene = state["scenes"][state["current_scene_index"]]
    provider = get_llm_provider(state, "director")
    chapter_db = get_chapter_db(state)

    context = ""
    if chapter_db:
        chapter_id = getattr(current_scene, "chapter_id", None)
        if chapter_id:
            chapter = chapter_db.get_chapter(chapter_id)
            if chapter:
                context = f"""Chapter: {chapter.metadata.chapter_title or "N/A"}
Summary: {chapter.metadata.summary or "N/A"}
"""

    user_prompt = f"""{context}
Scene: {current_scene.description}
Location: {current_scene.location}
Time of Day: {current_scene.time_of_day}
Characters: {", ".join(current_scene.characters)}
Scene ID: {current_scene.id}

Convert this scene into a detailed shot list following the schema."""

    try:
        shots_data = provider.generate_structured(
            prompt=user_prompt,
            response_schema=SHOT_SCHEMA,
            system_prompt=DIRECTOR_SYSTEM_PROMPT,
        )
        state["shot_list"] = [Shot(**s) for s in shots_data]
        state["current_shot_index"] = 0
    except Exception as e:
        print(f"Error parsing Director response: {e}")
        state["last_error"] = str(e)

    return state
