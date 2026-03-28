import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

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
            "text_preview": self.text[:500] + "..." if len(self.text) > 500 else self.text,
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
            start_pos=data.get("start_pos", 0),
            end_pos=data.get("end_pos", 0),
            embedding=data.get("embedding", []),
            metadata=ChapterMetadata.from_dict(data.get("metadata", {})),
        )

class ChapterDB:
    """Database for storing chapters with metadata."""
    def __init__(self, index_dir: Path):
        self.index_dir = index_dir
        self.chapters_dir = index_dir / "chapters"
        self.toc_path = index_dir / "toc.json"
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
            try:
                toc = json.loads(self.toc_path.read_text(encoding="utf-8"))
                self.metadata = toc.get("metadata", self.metadata)
                
                # Try loading from chapters list in TOC
                chapters_info = toc.get("chapters", [])
                for ch_info in chapters_info:
                    chapter_id = ch_info["id"]
                    chapter_path = self.chapters_dir / f"{chapter_id}.json"
                    text_path = self.chapters_dir / f"{chapter_id}.txt"
                    
                    if chapter_path.exists():
                        data = json.loads(chapter_path.read_text(encoding="utf-8"))
                        full_text = ""
                        if text_path.exists():
                            full_text = text_path.read_text(encoding="utf-8")
                        self.chapters[chapter_id] = Chapter.from_dict(data, full_text)
            except Exception as e:
                print(f"Error loading ChapterDB: {e}")

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
