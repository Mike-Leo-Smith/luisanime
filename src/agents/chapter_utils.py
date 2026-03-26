from pathlib import Path
from typing import Optional
from src.core.state import PipelineState
from src.agents.indexer import ChapterDB


def get_chapter_db(state: PipelineState) -> Optional[ChapterDB]:
    project_dir = state.get("project_dir")
    if not project_dir:
        return None
    memory_dir = Path(project_dir) / "index"
    toc_path = memory_dir / "toc.json"
    if not toc_path.exists():
        return None
    db_path = memory_dir / "chapters.json"
    return ChapterDB(db_path)
