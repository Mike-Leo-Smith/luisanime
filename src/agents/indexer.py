"""
Text Segmentation Agent for Novel Preprocessing.

Segments the novel by natural chapters and creates a chapter database
with LLM-extracted metadata for retrieval.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

from src.core.state import PipelineState
from src.config import load_config, ConfigLoader
from src.providers.factory import ProviderFactory
from src.utils.json_utils import extract_json
from src.schemas import CHAPTER_METADATA_SCHEMA


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
        embedding: Optional[List[float]] = None,
        metadata: Optional[ChapterMetadata] = None,
    ):
        self.id = id
        self.text = text
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.embedding = embedding or []
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
            "embedding": self.embedding,
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], full_text: str = "") -> "Chapter":
        return cls(
            id=data["id"],
            text=full_text or data.get("text", "") or data.get("text_preview", ""),
            start_pos=data["start_pos"],
            end_pos=data["end_pos"],
            embedding=data.get("embedding", []),
            metadata=ChapterMetadata.from_dict(data.get("metadata", {})),
        )


class ChapterDB:
    """Database for storing chapters with metadata - each chapter in separate file."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.chapters_dir = db_path.parent / "chapters"
        self.toc_path = db_path.parent / "toc.json"
        self.chapters: Dict[str, Chapter] = {}
        self.metadata: Dict[str, Any] = {
            "total_chapters": 0,
            "total_chars": 0,
            "chapter_files": [],
        }
        self._load()

    def _load(self):
        """Load from TOC and individual chapter files."""
        if self.toc_path.exists():
            toc = json.loads(self.toc_path.read_text(encoding="utf-8"))
            self.metadata = toc.get("metadata", self.metadata)

            for chapter_file in self.metadata.get("chapter_files", []):
                chapter_path = self.chapters_dir / chapter_file
                if chapter_path.exists():
                    data = json.loads(chapter_path.read_text(encoding="utf-8"))
                    chapter_id = data["id"]
                    text_path = self.chapters_dir / f"{chapter_id}.txt"
                    full_text = ""
                    if text_path.exists():
                        full_text = text_path.read_text(encoding="utf-8")
                    self.chapters[chapter_id] = Chapter.from_dict(data, full_text)

    def save(self):
        """Save TOC and individual chapter files."""
        self.chapters_dir.mkdir(parents=True, exist_ok=True)

        chapter_files = []
        for chapter_id, chapter in self.chapters.items():
            chapter_file = f"{chapter_id}.json"
            chapter_path = self.chapters_dir / chapter_file

            chapter_path.write_text(
                json.dumps(chapter.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            text_path = self.chapters_dir / f"{chapter_id}.txt"
            text_path.write_text(chapter.text, encoding="utf-8")

            chapter_files.append(chapter_file)

        self.metadata["chapter_files"] = chapter_files
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

    def get_selected_chapters(self, chapter_numbers: List[int]) -> List[Chapter]:
        selected = []
        for ch in self.get_all_chapters():
            if ch.metadata.chapter_number in chapter_numbers:
                selected.append(ch)
        return selected


def detect_chapter_boundaries(
    text: str,
) -> List[tuple[int, int, Optional[str], Optional[int]]]:
    patterns = [
        r"(?:^|\n\n)(?:Chapter|CHAPTER)[\s]+(\d+|\w+)[\s]*[:\-\.]?[\s]*([^\n]*)",
        r"(?:^|\n\n)第[\s]*(\d+|[一二三四五六七八九十百]+)[\s]*章[\s]*[:\-\.]?\s*([^\n]*)",
        r"(?:^|\n\n)Chapter[\s]+([IVXLC]+)[\s]*[:\-\.]?\s*([^\n]*)",
    ]

    chapter_starts = []

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.MULTILINE):
            chapter_num = match.group(1)
            chapter_title = match.group(2).strip()

            try:
                chapter_number = int(chapter_num)
            except ValueError:
                chapter_number = None

            chapter_starts.append((match.start(), chapter_number, chapter_title))

    if not chapter_starts:
        return [(0, len(text), None, 1)]

    chapter_starts.sort(key=lambda x: x[0])

    boundaries = []
    for i, (start, num, title) in enumerate(chapter_starts):
        end = chapter_starts[i + 1][0] if i + 1 < len(chapter_starts) else len(text)
        boundaries.append((start, end, title, num if num else i + 1))

    return boundaries


def extract_chapter_metadata(
    chapter_text: str, chapter_num: int, provider
) -> ChapterMetadata:
    prompt = f"""Analyze Chapter {chapter_num} and extract key metadata.

Chapter text (first 3000 chars):
---
{chapter_text[:3000]}
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


def text_segmenter(state: PipelineState) -> PipelineState:
    """Segment novel by natural chapters and extract metadata."""
    print("--- INDEXER: Chapter-Based Segmentation ---")

    project_dir = state.get("project_dir", "./workspace")
    db_path = Path(project_dir) / "memory" / "chapters.json"

    if db_path.parent.exists() and (db_path.parent / "toc.json").exists():
        print(f"  Chapter database already exists at {db_path.parent}")
        return state

    novel_text = state["novel_text"]
    if not novel_text:
        print("  No novel text to segment")
        state["last_error"] = "No novel text provided"
        return state

    print(f"  Full novel length: {len(novel_text)} characters")

    print("  Detecting chapter boundaries...")
    boundaries = detect_chapter_boundaries(novel_text)
    print(f"  Found {len(boundaries)} chapter(s)")

    db = ChapterDB(db_path)

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
    config = load_config(Path(project_dir) if project_dir else None)
    model_cfg = ConfigLoader.get_agent_config(config, "indexer")
    provider = ProviderFactory.create_llm(model_cfg)

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

    if "natural_language" in segment_selection:
        print("  Applying natural language selection...")
        all_matches = []
        for query in segment_selection["natural_language"]:
            print(f"    Query: '{query}'")
            matches = match_chapters_with_llm(query, db.get_all_chapters(), provider)
            all_matches.extend(matches)

        if all_matches:
            all_matches.sort(key=lambda x: x[1], reverse=True)
            seen = set()
            selected_chapters = []
            for ch, score in all_matches:
                if ch.id not in seen:
                    selected_chapters.append(ch)
                    seen.add(ch.id)
                    print(f"      Match: {ch.id} (score: {score:.2f})")

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

    return state


def retrieve_chapter_context(
    scene_description: str, db: ChapterDB, provider, num_chapters: int = 2
) -> str:
    """Retrieve most relevant chapter context for a scene."""
    matches = match_chapters_with_llm(
        scene_description, db.get_all_chapters(), provider
    )

    if not matches:
        return ""

    top_chapters = [ch for ch, _ in matches[:num_chapters]]
    context = "\n\n".join(
        [c.text[:2000] + "..." if len(c.text) > 2000 else c.text for c in top_chapters]
    )

    return context
