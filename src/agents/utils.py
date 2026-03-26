from pathlib import Path
from typing import Optional
from src.core.state import PipelineState
from src.config import load_config, ConfigLoader
from src.providers.factory import ProviderFactory
from src.agents.indexer import ChapterDB


def load_project_config(state: PipelineState):
    project_dir = state.get("project_dir")
    if project_dir:
        return load_config(Path(project_dir))
    return load_config()


def get_llm_provider(state: PipelineState, agent_name: str):
    config = load_project_config(state)
    model_cfg = ConfigLoader.get_agent_config(config, agent_name)
    return ProviderFactory.create_llm(model_cfg)


def get_image_provider(state: PipelineState, agent_name: str):
    config = load_project_config(state)
    model_cfg = ConfigLoader.get_agent_config(config, agent_name)
    return ProviderFactory.create_image(model_cfg)


def get_video_provider(state: PipelineState, agent_name: str):
    config = load_project_config(state)
    model_cfg = ConfigLoader.get_agent_config(config, agent_name)
    return ProviderFactory.create_video(model_cfg)


def get_chapter_db(state: PipelineState) -> Optional[ChapterDB]:
    project_dir = state.get("project_dir")
    if not project_dir:
        return None
    index_dir = Path(project_dir) / "index"
    toc_path = index_dir / "toc.json"
    if not toc_path.exists():
        return None
    db_path = index_dir / "chapters.json"
    return ChapterDB(db_path)
