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

    def create_project(self, name: str, novel_text: str, config_override: Optional[Dict] = None) -> Path:
        project_path = self.root / name
        if project_path.exists():
            raise ValueError(f"Project '{name}' already exists")
        
        project_path.mkdir(parents=True)
        
        # Create systematic structure
        (project_path / "index" / "chapters").mkdir(parents=True)
        (project_path / "runtime" / "lore").mkdir(parents=True)
        (project_path / "runtime" / "screenplay").mkdir(parents=True)
        (project_path / "runtime" / "style").mkdir(parents=True)
        (project_path / "production").mkdir(parents=True)
        (project_path / "logs").mkdir(parents=True)
        (project_path / "output").mkdir(parents=True)
        
        # Save novel
        (project_path / "novel.txt").write_text(novel_text, encoding="utf-8")
        
        # Load and save config
        template_path = Path("config.yaml.template")
        if template_path.exists():
            config = yaml.safe_load(template_path.read_text(encoding="utf-8"))
        else:
            config = {}
            
        if config_override:
            config = self._deep_merge(config, config_override)
            
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
            self.project_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    def get_path(self, *args) -> Path:
        if not self.current_project:
            raise ValueError("No project loaded")
        return self.current_project.joinpath(*args)

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get_stage_summary(self) -> Dict[str, Any]:
        """Returns a summary of the project progress."""
        if not self.current_project:
            return {}
            
        # Check scenes
        scenes_file = self.get_path("runtime", "screenplay", "scenes.json")
        total_scenes = 0
        if scenes_file.exists():
            try:
                scenes = json.loads(scenes_file.read_text())
                total_scenes = len(scenes)
            except: pass
            
        # Check shots
        shot_list_file = self.get_path("runtime", "shot_list.json")
        total_shots = 0
        shots_by_status = {"Pending": 0, "Storyboarded": 0, "Animated": 0}
        
        if shot_list_file.exists():
            try:
                data = json.loads(shot_list_file.read_text())
                shots = data.get("shots", [])
                total_shots = len(shots)
                
                for shot in shots:
                    sid = shot["scene_id"]
                    shid = shot["shot_id"]
                    
                    # Check for video
                    video_path = self.get_path("production", f"scene_{sid}", f"shot_{shid}", "video.mp4")
                    # Fallback for old path naming
                    if not video_path.exists():
                        video_path = self.get_path("production", sid, shid, "video.mp4")
                        
                    if video_path.exists():
                        shots_by_status["Animated"] += 1
                        continue
                        
                    # Check for keyframe
                    kb_path = self.get_path("production", f"scene_{sid}", f"shot_{shid}", "keyframe_begin.png")
                    if not kb_path.exists():
                        kb_path = self.get_path("production", sid, shid, "keyframe_begin.png")
                        
                    if kb_path.exists():
                        shots_by_status["Storyboarded"] += 1
                        continue
                        
                    shots_by_status["Pending"] += 1
            except: pass
            
        return {
            "total_scenes": total_scenes,
            "total_shots": total_shots,
            "shots_by_status": shots_by_status,
            "output_ready": self.get_path("output", "final_video.mp4").exists()
        }
