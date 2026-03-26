from src.core.state import PipelineState, Shot
from src.schemas import SHOT_SCHEMA
from src.agents.utils import get_llm_provider
from src.agents.chapter_utils import get_chapter_db


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
                context = f"""
Chapter Context:
- Title: {chapter.metadata.chapter_title or "N/A"}
- Summary: {chapter.metadata.summary or "N/A"}
- Key Events: {", ".join(chapter.metadata.plot_events[:5]) if chapter.metadata.plot_events else "N/A"}
"""

    prompt = f"""Acting as a Film Director, convert the following scene description into a detailed Shot List for animation.
{context}

Scene: {current_scene.description}
Location: {current_scene.location}
Time of Day: {current_scene.time_of_day}
Characters: {", ".join(current_scene.characters)}

Rule: Decompose complex physical interactions into safe, renderable montages.

Generate shots with scene_id: {current_scene.id}"""

    try:
        shots_data = provider.generate_structured(
            prompt=prompt, response_schema=SHOT_SCHEMA
        )
        state["shot_list"] = [Shot(**s) for s in shots_data]
        state["current_shot_index"] = 0
    except Exception as e:
        print(f"Error parsing Director response: {e}")
        state["last_error"] = str(e)

    return state
