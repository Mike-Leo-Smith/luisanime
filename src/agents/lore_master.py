from typing import Dict, List, Any
from pathlib import Path
import json
from src.pipeline.state import PipelineState
from src.schemas import L3_PATCH_SCHEMA
from src.agents.utils import get_llm_provider, get_chapter_db, get_runtime_path

def lore_master(state: PipelineState) -> Dict:
    print("📚 [Lore Master] Extracting physical mutations and inventory changes...")
    
    save_path = get_runtime_path(state, "lore", "mutations.json")
    if save_path.exists():
        print(f"  [Bypass] Loading existing lore from {save_path}")
        return {
            "l3_graph_mutations": json.loads(save_path.read_text(encoding="utf-8"))
        }

    chapter_db = get_chapter_db(state)
    if not chapter_db:
        return {"last_error": "Chapter DB not found"}

    provider = get_llm_provider(state, "lore_master")
    
    all_mutations = []
    chapters = chapter_db.get_all_chapters()
    
    system_prompt = """You are the Lore Master, a deterministic state-tracking engine. 
Your only function is to extract permanent physical mutations (injuries, clothing changes) 
and inventory changes (weapons broken, items acquired) from the text.
Rule 1: Do not invent lore. If it is not explicitly stated, do not record it.
Rule 2: Output state changes as discrete JSON patches."""

    for chapter in chapters:
        print(f"  Processing {chapter.id}...")
        user_prompt = f"""
New Chapter Text:
---
{chapter.text[:10000]}
---

Extract state mutations following the L3_PATCH_SCHEMA."""

        try:
            result = provider.generate_structured(
                prompt=user_prompt,
                response_schema=L3_PATCH_SCHEMA,
                system_prompt=system_prompt
            )
            all_mutations.extend(result.get("mutations", []))
        except Exception as e:
            print(f"    [Lore Master Warning] Failed chapter {chapter.id}: {e}")

    # Save to disk for persistence using systematic path
    save_path = get_runtime_path(state, "lore", "mutations.json")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(json.dumps(all_mutations, indent=2, ensure_ascii=False))

    return {
        "l3_graph_mutations": all_mutations
    }
