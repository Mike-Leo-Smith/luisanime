from src.core.state import PipelineState, SceneIR
from src.schemas import SCENE_SCHEMA
from src.agents.utils import get_llm_provider, get_chapter_db
from src.agents.prompts import SCREENWRITER_SYSTEM_PROMPT


def screenwriter(state: PipelineState) -> PipelineState:
    print("--- SCREENWRITER: Chunking Scenes ---")

    provider = get_llm_provider(state, "screenwriter")
    chapter_db = get_chapter_db(state)

    if chapter_db and len(chapter_db.chapters) > 0:
        print(f"  Using {len(chapter_db.chapters)} chapters for scene extraction")

        all_scenes = []
        for chapter in chapter_db.get_all_chapters():
            print(f"    Processing {chapter.id}...")

            user_prompt = f"""Chapter: {chapter.metadata.chapter_title or chapter.id}
Characters: {", ".join(chapter.metadata.characters[:10]) if chapter.metadata.characters else "N/A"}

Text:
---
{chapter.text[:100000]}
---

Break this chapter into scenes following the schema."""

            try:
                scenes_data = provider.generate_structured(
                    prompt=user_prompt,
                    response_schema=SCENE_SCHEMA,
                    system_prompt=SCREENWRITER_SYSTEM_PROMPT,
                )
                for s in scenes_data:
                    s["chapter_id"] = chapter.id
                all_scenes.extend(scenes_data)
            except Exception as e:
                print(f"      Error extracting from {chapter.id}: {e}")

        state["scenes"] = [SceneIR(**s) for s in all_scenes]
        print(f"  Extracted {len(all_scenes)} scenes total")
    else:
        user_prompt = f"""Text: {state["novel_text"]}

Break this text into scenes following the schema."""

        try:
            scenes_data = provider.generate_structured(
                prompt=user_prompt,
                response_schema=SCENE_SCHEMA,
                system_prompt=SCREENWRITER_SYSTEM_PROMPT,
            )
            state["scenes"] = [SceneIR(**s) for s in scenes_data]
        except Exception as e:
            print(f"Error parsing Screenwriter response: {e}")
            state["last_error"] = str(e)

    return state
