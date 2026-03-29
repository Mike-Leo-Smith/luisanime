import os
import json
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
import yaml


class ProjectManager:
    """Manages the video project folder structure and metadata."""

    def __init__(self, projects_root: str = "./projects"):
        self.root = Path(projects_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.current_project: Optional[Path] = None
        self.project_config: Dict[str, Any] = {}

    def create_project(
        self, name: str, novel_text: str, config_override: Optional[Dict] = None
    ) -> Path:
        project_path = self.root / name
        if project_path.exists():
            raise ValueError(f"Project '{name}' already exists")

        project_path.mkdir(parents=True)

        # Create AFC specific virtual directory structure (on filesystem for now)
        (project_path / "00_project_config").mkdir(parents=True)
        (project_path / "01_source_material").mkdir(parents=True)
        (project_path / "02_screenplays").mkdir(parents=True)
        (project_path / "03_lore_bible").mkdir(parents=True)
        (project_path / "04_production_slate").mkdir(parents=True)
        (project_path / "05_dailies").mkdir(parents=True)
        (project_path / "06_logs").mkdir(parents=True)

        # Save novel in 01_source_material
        (project_path / "01_source_material" / "novel.txt").write_text(
            novel_text, encoding="utf-8"
        )
        # Backwards compatibility symlink/copy for legacy code
        (project_path / "novel.txt").write_text(novel_text, encoding="utf-8")

        # Load and save config
        template_path = Path("config.yaml.template")
        if template_path.exists():
            config = yaml.safe_load(template_path.read_text(encoding="utf-8"))
        else:
            config = {
                "project_budget_usd": 100.0,
                "global_aspect_ratio": "16:9",
                "fps": 24,
                "resolution": "1080p",
            }

        if config_override:
            config = self._deep_merge(config, config_override)

        with open(
            project_path / "00_project_config" / "config.yaml", "w", encoding="utf-8"
        ) as f:
            yaml.dump(config, f, sort_keys=False)

        # Legacy config for main.py loading
        with open(project_path / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(config, f, sort_keys=False)

        self.current_project = project_path
        self.project_config = config
        return project_path

    def load_project(self, name: str):
        project_path = self.root / name
        if not project_path.exists():
            raise FileNotFoundError(f"Project '{name}' not found")

        self.current_project = project_path
        config_path = project_path / "config.yaml"
        if config_path.exists():
            self.project_config = yaml.safe_load(
                config_path.read_text(encoding="utf-8")
            )

    def get_path(self, *args) -> Path:
        if not self.current_project:
            raise ValueError("No project loaded")
        return self.current_project.joinpath(*args)

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get_stage_summary(self) -> Dict[str, Any]:
        if not self.current_project:
            return {}

        screenplays_dir = self.get_path("02_screenplays")
        total_scenes = (
            len(list(screenplays_dir.glob("*.json"))) if screenplays_dir.exists() else 0
        )

        shots_dir = self.get_path("04_production_slate", "shots")
        total_shots = 0
        shots_by_status = {"Pending": 0, "Storyboarded": 0, "Animated": 0}

        if shots_dir.exists():
            shot_files = list(shots_dir.glob("*.json"))
            total_shots = len(shot_files)

            for shot_file in shot_files:
                try:
                    shot_data = json.loads(shot_file.read_text())
                    shot_id = shot_data.get("shot_id", shot_file.stem)

                    video_path = self.get_path("05_dailies", f"{shot_id}.mp4")
                    if video_path.exists():
                        shots_by_status["Animated"] += 1
                        continue

                    keyframe_path = shots_dir / f"{shot_id}.png"
                    if keyframe_path.exists():
                        shots_by_status["Storyboarded"] += 1
                        continue

                    shots_by_status["Pending"] += 1
                except Exception:
                    continue

        output_file = self.get_path("05_dailies", "final_video.mp4")

        return {
            "total_scenes": total_scenes,
            "total_shots": total_shots,
            "shots_by_status": shots_by_status,
            "output_ready": output_file.exists(),
        }
