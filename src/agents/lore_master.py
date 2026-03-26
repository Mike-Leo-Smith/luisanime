"""Lore Master Agent - Chapter Segmentation and Entity Extraction.

This agent:
1. Segments the novel into chapters using LLM-based detection
2. Extracts chapter metadata (title, characters, events, etc.)
3. Extracts entities (characters, locations, items) from each chapter
4. Saves chapters, TOC, and entities to assets/lore/
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.core.state import PipelineState, EntityState
from src.config import load_config, ConfigLoader
from src.providers.factory import ProviderFactory
from src.schemas import (
    CHAPTER_BOUNDARY_SCHEMA,
    CHAPTER_METADATA_SCHEMA,
    ENTITY_SCHEMA,
)
from src.agents.prompts import LORE_MASTER_SYSTEM_PROMPT


@dataclass
class ChapterMetadata:
    """Metadata for a chapter extracted by LLM."""

    chapter_number: Optional[int] = None
    chapter_title: Optional[str] = None
    summary: Optional[str] = None
    characters: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    plot_events: List[str] = field(default_factory=list)
    emotional_tone: Optional[str] = None
    key_scenes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_number": self.chapter_number,
            "chapter_title": self.chapter_title,
            "summary": self.summary,
            "characters": self.characters,
            "locations": self.locations,
            "plot_events": self.plot_events,
            "emotional_tone": self.emotional_tone,
            "key_scenes": self.key_scenes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChapterMetadata":
        return cls(
            chapter_number=data.get("chapter_number"),
            chapter_title=data.get("chapter_title"),
            summary=data.get("summary"),
            characters=data.get("characters", []),
            locations=data.get("locations", []),
            plot_events=data.get("plot_events", []),
            emotional_tone=data.get("emotional_tone"),
            key_scenes=data.get("key_scenes", []),
        )


class Chapter:
    """Represents a natural chapter from the novel."""

    def __init__(
        self,
        id: str,
        text: str,
        start_pos: int,
        end_pos: int,
        metadata: Optional[ChapterMetadata] = None,
    ):
        self.id = id
        self.text = text
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.metadata = metadata or ChapterMetadata()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text_preview": self.text[:500] + "..."
            if len(self.text) > 500
            else self.text,
            "full_text_length": len(self.text),
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "metadata": self.metadata.to_dict(),
        }


class ChapterDB:
    """Database for storing chapters with metadata."""

    def __init__(self, lore_dir: Path):
        self.lore_dir = lore_dir
        self.chapters_dir = lore_dir / "chapters"
        self.toc_path = lore_dir / "toc.json"
        self.chapters: Dict[str, Chapter] = {}
        self.metadata: Dict[str, Any] = {
            "total_chapters": 0,
            "total_chars": 0,
        }
        self._load()

    def _load(self):
        """Load from TOC and individual chapter files."""
        if self.toc_path.exists():
            toc = json.loads(self.toc_path.read_text(encoding="utf-8"))
            self.metadata = toc.get("metadata", self.metadata)

            for ch_info in toc.get("chapters", []):
                chapter_id = ch_info["id"]
                chapter_path = self.chapters_dir / f"{chapter_id}.json"
                text_path = self.chapters_dir / f"{chapter_id}.txt"

                if chapter_path.exists():
                    data = json.loads(chapter_path.read_text(encoding="utf-8"))
                    full_text = ""
                    if text_path.exists():
                        full_text = text_path.read_text(encoding="utf-8")

                    self.chapters[chapter_id] = Chapter(
                        id=chapter_id,
                        text=full_text,
                        start_pos=data.get("start_pos", 0),
                        end_pos=data.get("end_pos", 0),
                        metadata=ChapterMetadata.from_dict(data.get("metadata", {})),
                    )

    def save(self):
        """Save TOC and individual chapter files."""
        self.chapters_dir.mkdir(parents=True, exist_ok=True)

        for chapter_id, chapter in self.chapters.items():
            chapter_path = self.chapters_dir / f"{chapter_id}.json"
            chapter_path.write_text(
                json.dumps(chapter.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            text_path = self.chapters_dir / f"{chapter_id}.txt"
            text_path.write_text(chapter.text, encoding="utf-8")

        self.metadata["total_chapters"] = len(self.chapters)

        toc = {
            "metadata": self.metadata,
            "chapters": [
                {
                    "id": ch.id,
                    "file": f"{ch.id}.json",
                    "text_file": f"{ch.id}.txt",
                    "title": ch.metadata.chapter_title,
                    "number": ch.metadata.chapter_number,
                    "char_count": len(ch.text),
                }
                for ch in self.get_all_chapters()
            ],
        }

        self.toc_path.write_text(
            json.dumps(toc, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add_chapter(self, chapter: Chapter):
        self.chapters[chapter.id] = chapter
        self.metadata["total_chapters"] = len(self.chapters)

    def get_chapter(self, chapter_id: str) -> Optional[Chapter]:
        return self.chapters.get(chapter_id)

    def get_all_chapters(self) -> List[Chapter]:
        return sorted(self.chapters.values(), key=lambda c: c.start_pos)


def detect_chapter_boundaries(text: str, provider) -> List[tuple]:
    """Use LLM to detect chapter boundaries."""

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
            prompt=prompt, response_schema=CHAPTER_BOUNDARY_SCHEMA
        )

        boundaries = []
        for i, ch in enumerate(chapters_data):
            start_marker = ch.get("start_marker", "")
            start_pos = text.find(start_marker)
            if start_pos == -1:
                start_pos = (len(text) // len(chapters_data)) * i

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
        return [(0, len(text), None, 1)]


def extract_chapter_metadata(
    chapter_text: str, chapter_num: int, provider
) -> ChapterMetadata:
    """Extract metadata from a chapter."""

    prompt = f"""Analyze Chapter {chapter_num} and extract key metadata.

Chapter text:
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
            f"      Metadata: title={title_preview}... chars={len(data.get('characters', []))} events={len(data.get('plot_events', []))}"
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


def extract_entities(chapter: Chapter, provider) -> Dict[str, Dict]:
    """Extract entities from a chapter."""

    user_prompt = f"""Chapter: {chapter.metadata.chapter_title or chapter.id}
Summary: {chapter.metadata.summary or "N/A"}

Text:
---
{chapter.text[:100000]}
---

Extract all entities (characters, locations, items) from this chapter."""

    entities = {}
    try:
        entities_data = provider.generate_structured(
            prompt=user_prompt,
            response_schema=ENTITY_SCHEMA,
            system_prompt=LORE_MASTER_SYSTEM_PROMPT,
        )

        for entity in entities_data:
            name = entity.get("name")
            if name:
                entities[name] = {
                    "type": entity.get("entity_type"),
                    "description": entity.get("description"),
                }

        print(f"      Found {len(entities)} entities")
    except Exception as e:
        print(f"      Error extracting entities: {e}")

    return entities


def lore_master(state: PipelineState) -> PipelineState:
    """Main lore master function - segments chapters and extracts entities."""
    print("--- LORE MASTER: Chapter Segmentation & Entity Extraction ---")

    project_dir = state.get("project_dir")
    if not project_dir:
        state["last_error"] = "No project directory"
        return state

    lore_dir = Path(project_dir) / "assets" / "lore"
    lore_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(Path(project_dir))
    model_cfg = ConfigLoader.get_agent_config(config, "lore_master")
    provider = ProviderFactory.create_llm(model_cfg)

    db = ChapterDB(lore_dir)
    if db.chapters:
        print(f"  Using existing {len(db.chapters)} chapters from {lore_dir}")
    else:
        novel_text = state["novel_text"]
        if not novel_text:
            state["last_error"] = "No novel text provided"
            return state

        print(f"  Full novel length: {len(novel_text)} characters")
        print("  Detecting chapter boundaries using LLM...")

        boundaries = detect_chapter_boundaries(novel_text, provider)
        print(f"  Found {len(boundaries)} chapter(s)")

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
        print(f"  Saved {len(db.chapters)} chapters")

    print("  Extracting chapter metadata and entities...")

    all_entities: Dict[str, Dict] = {}
    chapters_list = db.get_all_chapters()
    total = len(chapters_list)

    for i, chapter in enumerate(chapters_list, 1):
        progress = (i / total) * 100
        print(f"    [{i}/{total} {progress:.1f}%] {chapter.id}...")

        if not chapter.metadata.summary:
            chapter.metadata = extract_chapter_metadata(
                chapter.text, chapter.metadata.chapter_number or i, provider
            )

        chapter_entities = extract_entities(chapter, provider)
        for name, info in chapter_entities.items():
            if name not in all_entities:
                all_entities[name] = info

        db.save()

    entities_path = lore_dir / "entities.json"
    entities_path.write_text(
        json.dumps(all_entities, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for name, info in all_entities.items():
        state["entity_graph"][name] = EntityState(id=name, attributes=info)

    print(f"\n  Complete!")
    print(f"    Chapters: {len(db.chapters)}")
    print(f"    Unique entities: {len(all_entities)}")
    print(f"    TOC: {db.toc_path}")
    print(f"    Entities: {entities_path}")

    return state
