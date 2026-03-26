from src.core.state import PipelineState, EntityState
from src.schemas import ENTITY_SCHEMA
from src.agents.utils import get_llm_provider
from src.agents.chapter_utils import get_chapter_db


def lore_master(state: PipelineState) -> PipelineState:
    print("--- LORE MASTER: Extracting Entities ---")

    provider = get_llm_provider(state, "lore_master")
    chapter_db = get_chapter_db(state)

    if chapter_db and len(chapter_db.chapters) > 0:
        print(f"  Using {len(chapter_db.chapters)} chapters for entity extraction")

        all_entities = {}
        chapters_list = chapter_db.get_all_chapters()
        total = len(chapters_list)
        for i, chapter in enumerate(chapters_list, 1):
            progress = (i / total) * 100
            print(f"    [{i}/{total} {progress:.1f}%] Processing {chapter.id}...")

            prompt = f"""Extract key entities (characters, locations, unique items) from the following chapter.
For each entity, specify its type (character, location, item) and a brief description.

Chapter: {chapter.metadata.chapter_title or chapter.id}
Summary: {chapter.metadata.summary or "N/A"}

Text:
---
{chapter.text[:3000]}
---"""

            try:
                entities = provider.generate_structured(
                    prompt=prompt, response_schema=ENTITY_SCHEMA
                )
                print(f"      Found {len(entities)} entities")
                for entity in entities:
                    name = entity.get("name")
                    if name and name not in all_entities:
                        all_entities[name] = {
                            "type": entity.get("entity_type"),
                            "description": entity.get("description"),
                        }
            except Exception as e:
                print(f"      Error extracting from {chapter.id}: {e}")

        for name, info in all_entities.items():
            state["entity_graph"][name] = EntityState(id=name, attributes=info)

        print(f"  Extracted {len(all_entities)} unique entities")
    else:
        prompt = f"""Extract key entities (characters, locations, unique items) from the following text.
For each entity, specify its type (character, location, item) and a brief description.

Text: {state["novel_text"]}"""

        try:
            entities = provider.generate_structured(
                prompt=prompt, response_schema=ENTITY_SCHEMA
            )
            for entity in entities:
                name = entity.get("name")
                if name:
                    state["entity_graph"][name] = EntityState(
                        id=name,
                        attributes={
                            "type": entity.get("entity_type"),
                            "description": entity.get("description"),
                        },
                    )
        except Exception as e:
            print(f"Error parsing Lore Master response: {e}")
            state["last_error"] = str(e)

    return state
