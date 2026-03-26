import os
from pathlib import Path
from typing import Optional, Dict, Any
import yaml
from dotenv import load_dotenv

load_dotenv()


class ConfigLoader:
    ROOT_CONFIG = Path("config.yaml")

    @classmethod
    def load(cls, project_path: Optional[Path | str] = None) -> Dict[str, Any]:
        config_paths = []

        if project_path:
            project_path = Path(project_path)
            project_config = project_path / "config.yaml"
            if project_config.exists():
                config_paths.append(project_config)

        if cls.ROOT_CONFIG.exists():
            config_paths.append(cls.ROOT_CONFIG)

        if not config_paths:
            raise FileNotFoundError("No config.yaml found")

        merged = {}
        for path in reversed(config_paths):
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data:
                    merged = cls._deep_merge(merged, data)

        merged = cls._resolve_env_vars(merged)
        return merged

    @classmethod
    def _deep_merge(cls, base: Dict, override: Dict) -> Dict:
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = cls._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @classmethod
    def _resolve_env_vars(cls, obj: Any) -> Any:
        if isinstance(obj, str) and obj.startswith("ENV:"):
            env_var = obj[4:]
            return os.getenv(env_var) or f"MISSING_ENV_{env_var}"
        elif isinstance(obj, dict):
            return {k: cls._resolve_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [cls._resolve_env_vars(item) for item in obj]
        return obj

    @classmethod
    def get_agent_config(
        cls, config: Dict[str, Any], agent_name: str
    ) -> Dict[str, Any]:
        """
        Get agent configuration with model reference resolved.

        Resolution order:
        1. Find model reference from agents.{agent_name}.model
        2. Get model defaults from models.{model_name}
        3. Apply agent-specific parameter overrides
        """
        agents = config.get("agents", {})
        models = config.get("models", {})

        agent_cfg = agents.get(agent_name, {})

        if not agent_cfg:
            raise ValueError(
                f"Agent '{agent_name}' not found in config. "
                f"Available agents: {list(agents.keys())}"
            )

        # Get model reference
        model_name = agent_cfg.get("model")
        if not model_name:
            raise ValueError(
                f"Agent '{agent_name}' must specify a model reference. "
                f"Example: model: gemini-flash"
            )

        # Get model definition
        model_def = models.get(model_name, {})
        if not model_def:
            raise ValueError(
                f"Model '{model_name}' referenced by agent '{agent_name}' not found. "
                f"Available models: {list(models.keys())}"
            )

        # Start with model definition
        merged = model_def.copy()

        # Apply agent-specific overrides (excluding 'model' key)
        for key, value in agent_cfg.items():
            if key != "model":
                merged[key] = value

        return merged


def load_config(project_path: Optional[Path] = None) -> Dict[str, Any]:
    return ConfigLoader.load(project_path)


if __name__ == "__main__":
    cfg = load_config()
    print(f"Project: {cfg['project']['name']}")
    print(f"Director: {ConfigLoader.get_agent_config(cfg, 'director')}")
    print(f"Indexer: {ConfigLoader.get_agent_config(cfg, 'indexer')}")
