import os
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
import yaml

class Provider(str, Enum):
    GOOGLE = "google"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    HAILUO = "hailuo"
    LUMA = "luma"
    RUNWAY = "runway"

class ModelConfig(BaseModel):
    provider: Provider
    model: str
    api_key: str
    temperature: float = 0.7

    @validator("api_key", pre=True)
    def resolve_env_vars(cls, v):
        if isinstance(v, str) and v.startswith("ENV:"):
            env_var = v[4:]
            val = os.getenv(env_var)
            if not val:
                # In a real production system, you might want to raise an error
                # but for now we'll just return the ENV name for debugging
                return f"MISSING_ENV_{env_var}"
            return val
        return v

class ProjectConfig(BaseModel):
    name: str
    workspace_dir: str
    log_level: str = "INFO"

class MemoryDBConfig(BaseModel):
    type: str
    url: str

class ControlPlaneConfig(BaseModel):
    memory_db: MemoryDBConfig
    agents: Dict[str, ModelConfig]

class PipelineSettings(BaseModel):
    max_retries_per_shot: int = 3
    candidates_per_take: int = 3

class AnimatorConfig(BaseModel):
    provider: str
    model: str
    api_key: str
    pipeline_settings: PipelineSettings

    @validator("api_key", pre=True)
    def resolve_env_vars(cls, v):
        if isinstance(v, str) and v.startswith("ENV:"):
            env_var = v[4:]
            val = os.getenv(env_var)
            if not val:
                return f"MISSING_ENV_{env_var}"
            return val
        return v

class RenderPlaneConfig(BaseModel):
    storyboarder: ModelConfig
    animator: AnimatorConfig

class PostProcessingConfig(BaseModel):
    lip_sync: Dict[str, str]

class GlobalConfig(BaseModel):
    project: ProjectConfig
    control_plane: ControlPlaneConfig
    render_plane: RenderPlaneConfig
    post_processing: PostProcessingConfig

def load_config(path: str = "config.yaml") -> GlobalConfig:
    with open(path, "r") as f:
        config_data = yaml.safe_load(f)
    return GlobalConfig(**config_data)

if __name__ == "__main__":
    # Test loading
    config = load_config()
    print(f"Project Name: {config.project.name}")
    print(f"Director Model: {config.control_plane.agents['director_node'].model}")
