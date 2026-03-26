import os
from pathlib import Path
from typing import Optional, Dict, Any
import yaml
from dotenv import load_dotenv

load_dotenv()


class ConfigLoader:
    ROOT_CONFIG = Path("config.yaml")

    @classmethod
    def load(cls, project_path: Optional[Path] = None) -> Dict[str, Any]:
        config_paths = []

        env_config = os.getenv("CONFIG_PATH")
        if env_config:
            config_paths.append(Path(env_config))

        if project_path:
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
        agents = config.get("agents", {})
        agent_cfg = agents.get(agent_name, {})

        if not agent_cfg:
            raise ValueError(
                f"Agent '{agent_name}' not found in config. "
                f"Available agents: {list(agents.keys())}"
            )

        if "provider" not in agent_cfg:
            raise ValueError(
                f"Agent '{agent_name}' must specify a provider in config. "
                f"Each agent MUST have its own provider configuration."
            )

        return agent_cfg


def load_config(project_path: Optional[Path] = None) -> Dict[str, Any]:
    return ConfigLoader.load(project_path)


if __name__ == "__main__":
    cfg = load_config()
    print(f"Project: {cfg['project']['name']}")
    print(f"Director: {cfg['agents']['director']}")
