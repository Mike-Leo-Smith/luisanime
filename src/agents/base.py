from typing import Dict, Any, List, Optional
from src.pipeline.state import AFCState
from src.pipeline.workspace import AgenticWorkspace
from src.providers.base import BaseLLMProvider, BaseImageProvider, BaseVideoProvider
from src.providers.factory import ProviderFactory

class BaseAgent:
    def __init__(self, workspace: AgenticWorkspace, 
                 llm: Optional[BaseLLMProvider] = None,
                 image_gen: Optional[BaseImageProvider] = None,
                 video_gen: Optional[BaseVideoProvider] = None,
                 project_config: Optional[Dict[str, Any]] = None):
        self.workspace = workspace
        self.llm = llm
        self.image_gen = image_gen
        self.video_gen = video_gen
        self.project_config = project_config or {}

    def log_prompt(self, agent_name: str, shot_id: str, prompt: str, custom_path: Optional[str] = None):
        """Logs the generation prompt to a file."""
        log_entry = f"[{agent_name}] SHOT: {shot_id}\nPROMPT: {prompt}\n{'-'*40}"
        self.workspace.append_file("06_logs/generation_prompts.log", log_entry)
        
        if custom_path:
            self.workspace.write_file(custom_path, prompt)

    @classmethod
    def from_config(cls, workspace: AgenticWorkspace, project_config: Dict[str, Any]):
        """Initializes agent with providers resolved from project configuration."""
        import re
        # Convert CamelCase to snake_case
        name = cls.__name__.replace("Agent", "")
        agent_name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
        
        agent_cfg = project_config.get("agents", {}).get(agent_name, {})
        
        models_cfg = project_config.get("models", {})
        
        def resolve_provider_cfg(type_key: str):
            model_name = agent_cfg.get(type_key)
            if not model_name:
                # Fallback to default model names if not specified per agent
                if type_key == "llm": model_name = "gemini-flash"
                elif type_key == "image": model_name = "gemini-image"
                elif type_key == "video": model_name = "minimax-video"
            
            return models_cfg.get(model_name, {})

        llm_cfg = resolve_provider_cfg("llm")
        image_cfg = resolve_provider_cfg("image")
        video_cfg = resolve_provider_cfg("video")
        
        llm = ProviderFactory.create_llm(llm_cfg) if llm_cfg else None
        image_gen = ProviderFactory.create_image(image_cfg) if image_cfg else None
        video_gen = ProviderFactory.create_video(video_cfg) if video_cfg else None
            
        return cls(workspace, llm, image_gen, video_gen, project_config)

class BaseOrchestrator(BaseAgent):
    pass

class BaseCreative(BaseAgent):
    pass

class BaseState(BaseAgent):
    pass

class BaseExecutor(BaseAgent):
    pass

class BaseQA(BaseAgent):
    pass

class BaseCompiler(BaseAgent):
    pass
