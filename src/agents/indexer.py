"""
Text Segmentation Agent for Novel Preprocessing.

Segments the novel by natural chapters and creates a chapter database
with LLM-extracted metadata for retrieval.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

from src.pipeline.state import PipelineState
from src.pipeline.chapters import Chapter, ChapterDB, ChapterMetadata
from src.config import load_config, ConfigLoader
from src.providers.factory import ProviderFactory
from src.utils.json_utils import extract_json
from src.schemas import CHAPTER_METADATA_SCHEMA, CHAPTER_BOUNDARY_SCHEMA
from src.agents.prompts import INDEXER_SYSTEM_PROMPT


def detect_chapter_boundaries(
    text: str, provider
) -> List[tuple[int, int, Optional[str], Optional[int]]]:
    """Use LLM to detect chapter boundaries in the novel text."""

    prompt = f"""Analyze the following novel text and identify all chapter boundaries.

Novel text (first 100k chars):
---
{text[:100000]}
---

Identify each chapter by:
1. Its sequential number (1, 2, 3, etc.)
2. Its title if present
3. The exact start marker text (first 50 characters of the chapter start)

Return the chapters in order as they appear in the text."""

    try:
        chapters_data = provider.generate_structured(
            prompt=prompt, 
            response_schema=CHAPTER_BOUNDARY_SCHEMA,
            system_prompt=INDEXER_SYSTEM_PROMPT
        )

        boundaries = []
        for i, ch in enumerate(chapters_data):
            start_marker = ch.get("start_marker", "")
            # Find the position of the start marker in the text
            start_pos = text.find(start_marker)
            if start_pos == -1:
                # Fallback: estimate position based on chapter number
                start_pos = (len(text) // len(chapters_data)) * i

            # Find end position (start of next chapter or end of text)
            if i + 1 < len(chapters_data):
                next_marker = chapters_data[i + 1].get("start_marker", "")
                end_pos = text.find(next_marker)
                if end_pos == -1:
                    end_pos = (len(text) // len(chapters_data)) * (i + 1)
            else:
                end_pos = len(text)

            boundaries.append(
                (
                    start_pos,
                    end_pos,
                    ch.get("chapter_title"),
                    ch.get("chapter_number", i + 1),
                )
            )

        return boundaries

    except Exception as e:
        print(f"    LLM chapter detection failed: {e}")
        # Fallback: treat entire text as single chapter
        return [(0, len(text), None, 1)]


def extract_chapter_metadata(
    chapter_text: str, chapter_num: int, provider
) -> ChapterMetadata:
    prompt = f"""Analyze Chapter {chapter_num} and extract key metadata.

Chapter text (first 3000 chars):
---
{chapter_text[:100000]}
---

Extract the chapter metadata following the JSON schema."""

    try:
        data = provider.generate_structured(
            prompt=prompt, response_schema=CHAPTER_METADATA_SCHEMA
        )

        title = data.get("chapter_title", "N/A")
        title_preview = title[:30] if title else "N/A"
        print(
            f"      Extracted: title={title_preview}... chars={len(data.get('characters', []))} events={len(data.get('plot_events', []))}"
        )

        return ChapterMetadata(
            chapter_number=chapter_num,
            chapter_title=data.get("chapter_title"),
            summary=data.get("summary"),
            characters=data.get("characters", []),
            locations=data.get("locations", []),
            plot_events=data.get("plot_events", []),
            emotional_tone=data.get("emotional_tone"),
            key_scenes=data.get("key_scenes", []),
        )
    except Exception as e:
        print(f"      Metadata extraction failed: {e}")
        return ChapterMetadata(chapter_number=chapter_num)


def match_chapters_with_llm(
    query: str, chapters: List[Chapter], provider
) -> List[tuple[Chapter, float]]:

    summaries = []
    for ch in chapters:
        meta = ch.metadata
        num = meta.chapter_number or "?"
        title = meta.chapter_title or "Untitled"
        chars = ", ".join(meta.characters[:5]) if meta.characters else "N/A"
        events = ", ".join(meta.plot_events[:3]) if meta.plot_events else "N/A"
        summaries.append(
            f"Chapter {num} ({title}): Characters=[{chars}], Events=[{events}]"
        )

    prompt = f"""
Find chapters that match this query: "{query}"

Available chapters:
---
{"\n".join(summaries)}
---

Return a JSON array of chapter numbers that best match, with relevance scores (0.0-1.0).
Format: [{{"chapter": 1, "score": 0.95}}, {{"chapter": 5, "score": 0.8}}]
Return ONLY the JSON array.
"""

    try:
        response = provider.generate_text(prompt)
        matches = extract_json(response)
        chapter_map = {
            c.metadata.chapter_number: c for c in chapters if c.metadata.chapter_number
        }
        results = []
        for match in matches:
            ch_num = match.get("chapter")
            score = match.get("score", 0.5)
            if ch_num in chapter_map:
                results.append((chapter_map[ch_num], score))
        return results
    except Exception as e:
        print(f"    LLM matching failed: {e}")
        return []


def text_segmenter(state: PipelineState) -> Dict:
    """Segment novel by natural chapters and extract metadata."""
    print("--- INDEXER: Chapter-Based Segmentation ---")

    project_dir = state.get("project_dir", "./workspace")
    index_dir = Path(project_dir) / "index"

    if index_dir.exists() and (index_dir / "toc.json").exists():
        print(f"  Chapter database already exists at {index_dir}")
        return {}

    novel_text = state["novel_text"]
    if not novel_text:
        print("  No novel text to segment")
        return {"last_error": "No novel text provided"}

    print(f"  Full novel length: {len(novel_text)} characters")

    print("  Detecting chapter boundaries using LLM...")
    config = load_config(Path(project_dir) if project_dir else None)
    model_cfg = ConfigLoader.get_agent_config(config, "indexer")
    provider = ProviderFactory.create_llm(model_cfg)
    boundaries = detect_chapter_boundaries(novel_text, provider)
    print(f"  Found {len(boundaries)} chapter(s)")

    db = ChapterDB(index_dir)

    for i, (start, end, title, num) in enumerate(boundaries):
        chapter_text = novel_text[start:end].strip()
        if not chapter_text:
            continue

        chapter_id = f"chapter_{num:03d}"
        chapter = Chapter(
            id=chapter_id,
            text=chapter_text,
            start_pos=start,
            end_pos=end,
        )
        chapter.metadata.chapter_number = num
        chapter.metadata.chapter_title = title

        db.add_chapter(chapter)
        print(f"    {chapter_id}: {len(chapter_text)} chars")

    db.save()
    print(f"  Saved {len(db.chapters)} chapters to {db.chapters_dir}")

    print("  Extracting chapter metadata using LLM...")
    chapters_list = db.get_all_chapters()
    total = len(chapters_list)
    for i, chapter in enumerate(chapters_list, 1):
        progress = (i / total) * 100
        print(f"    [{i}/{total} {progress:.1f}%] Processing {chapter.id}...")
        chapter.metadata = extract_chapter_metadata(
            chapter.text, chapter.metadata.chapter_number or 0, provider
        )
        db.save()

    print(f"  Metadata extraction complete. TOC: {db.toc_path}")

    segment_selection = config.get("generation", {}).get("segment_selection") or {}
    selected_chapters = db.get_all_chapters()

    if "chapters" in segment_selection:
        chapter_nums = segment_selection["chapters"]
        selected_chapters = db.get_selected_chapters(chapter_nums)
        print(
            f"  Selected {len(selected_chapters)} chapter(s) by number: {chapter_nums}"
        )

    if selected_chapters:
        selected_text = "\n\n".join(
            [c.text for c in sorted(selected_chapters, key=lambda x: x.start_pos)]
        )
        print(
            f"  Final selected text: {len(selected_text)} characters from {len(selected_chapters)} chapter(s)"
        )
        state["novel_text"] = selected_text

    db.metadata["total_chars"] = len(novel_text)
    db.save()

    return {
        "novel_text": state["novel_text"]
    }
