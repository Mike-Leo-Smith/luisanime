import os
import json
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import yaml
from dataclasses import dataclass, asdict


@dataclass
class CharacterProfile:
    id: str
    name: str
    description: str
    visual_attributes: Dict[str, Any]
    reference_images: List[str]
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class LocationProfile:
    id: str
    name: str
    description: str
    visual_style: str
    reference_images: List[str]
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class ShotAsset:
    shot_id: str
    scene_id: str
    prompt: str
    camera_movement: str
    duration: float
    status: str = "pending"
    keyframe_path: Optional[str] = None
    video_raw_path: Optional[str] = None
    video_approved_path: Optional[str] = None
    video_synced_path: Optional[str] = None
    audio_path: Optional[str] = None
    qa_score: Optional[float] = None
    qa_feedback: Optional[str] = None
    retry_count: int = 0
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)


class ProjectManager:
    def __init__(self, projects_root: str = "./projects"):
        self.projects_root = Path(projects_root)
        self.projects_root.mkdir(parents=True, exist_ok=True)
        self.current_project: Optional[Path] = None
        self.project_config: Optional[Dict[str, Any]] = None
        self._shot_cache: Dict[str, ShotAsset] = {}
    
    def create_project(self, name: str, novel_text: str, config: Dict[str, Any]) -> Path:
        project_dir = self.projects_root / name
        if project_dir.exists():
            raise ValueError(f"Project '{name}' already exists")
        
        dirs = [
            "input",
            "output",
            "shared/characters",
            "shared/locations",
            "shared/audio",
            "shots",
            "checkpoints",
            "logs"
        ]
        
        for d in dirs:
            (project_dir / d).mkdir(parents=True, exist_ok=True)
        
        (project_dir / "input" / "novel.txt").write_text(novel_text, encoding="utf-8")
        
        default_config = self._get_default_config()
        default_config.update(config)
        (project_dir / "project.yaml").write_text(
            yaml.dump(default_config, default_flow_style=False, allow_unicode=True),
            encoding="utf-8"
        )
        
        (project_dir / "shared" / "entities.json").write_text(
            json.dumps({"characters": {}, "locations": {}, "items": {}}, indent=2),
            encoding="utf-8"
        )
        
        (project_dir / "shared" / "database.json").write_text(
            json.dumps({
                "project_id": name,
                "created_at": datetime.now().isoformat(),
                "shots_count": 0,
                "approved_shots": 0,
                "last_checkpoint": None
            }, indent=2),
            encoding="utf-8"
        )
        
        self._save_checkpoint(project_dir, "init", {
            "status": "created",
            "timestamp": datetime.now().isoformat(),
            "stage": "init"
        })
        
        return project_dir
    
    def load_project(self, name: str) -> Path:
        project_dir = self.projects_root / name
        if not project_dir.exists():
            raise ValueError(f"Project '{name}' not found")
        
        self.current_project = project_dir
        config_path = project_dir / "project.yaml"
        self.project_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self._shot_cache.clear()
        
        return project_dir
    
    def _get_default_config(self) -> Dict[str, Any]:
        return {
            "project": {
                "name": "untitled",
                "version": "1.0.0",
                "created_at": datetime.now().isoformat()
            },
            "video": {
                "style": "anime",
                "resolution": "1080p",
                "fps": 24,
                "duration_per_shot": 4.0,
                "max_shots": 10,
                "aspect_ratio": "16:9"
            },
            "generation": {
                "max_retries_per_shot": 3,
                "candidates_per_take": 1,
                "qa_threshold": 0.8,
                "skip_lip_sync": False,
                "enable_vlm_qa": True
            },
            "models": {
                "director": "gemini-3.1-pro",
                "qa_linter": "gemini-3.1-pro",
                "storyboarder": "imagen-4.0-generate-001",
                "animator": "minimax-hailuo-02"
            },
            "style_presets": {
                "anime": {
                    "prompt_prefix": "High-quality 3D anime style.",
                    "prompt_suffix": "Studio Ghibli inspired, vibrant colors, clean lines."
                },
                "cinematic": {
                    "prompt_prefix": "Cinematic live-action style.",
                    "prompt_suffix": "Dramatic lighting, film grain, 35mm aesthetic."
                },
                "realistic": {
                    "prompt_prefix": "Photorealistic style.",
                    "prompt_suffix": "Hyper-detailed, 8K resolution, realistic textures."
                }
            }
        }
    
    def _require_project(self):
        if self.current_project is None:
            raise RuntimeError("No project loaded. Call load_project() first.")
    
    def get_shared_path(self, *subpaths) -> Path:
        self._require_project()
        return self.current_project / "shared" / Path(*subpaths)
    
    def get_shot_path(self, shot_id: str, *subpaths) -> Path:
        self._require_project()
        return self.current_project / "shots" / shot_id / Path(*subpaths)
    
    def ensure_shot_dir(self, shot_id: str) -> Path:
        self._require_project()
        shot_dir = self.current_project / "shots" / shot_id
        shot_dir.mkdir(parents=True, exist_ok=True)
        return shot_dir
    
    def save_character(self, character: CharacterProfile):
        self._require_project()
        char_path = self.get_shared_path("characters", f"{character.id}.json")
        char_path.write_text(json.dumps(character.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        self.log(f"Saved character profile: {character.id}")
    
    def load_character(self, char_id: str) -> Optional[CharacterProfile]:
        self._require_project()
        char_path = self.get_shared_path("characters", f"{char_id}.json")
        if char_path.exists():
            return CharacterProfile.from_dict(json.loads(char_path.read_text(encoding="utf-8")))
        return None
    
    def list_characters(self) -> List[str]:
        self._require_project()
        chars_dir = self.get_shared_path("characters")
        return [f.stem for f in chars_dir.glob("*.json")]
    
    def save_location(self, location: LocationProfile):
        self._require_project()
        loc_path = self.get_shared_path("locations", f"{location.id}.json")
        loc_path.write_text(json.dumps(location.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        self.log(f"Saved location profile: {location.id}")
    
    def load_location(self, loc_id: str) -> Optional[LocationProfile]:
        self._require_project()
        loc_path = self.get_shared_path("locations", f"{loc_id}.json")
        if loc_path.exists():
            return LocationProfile.from_dict(json.loads(loc_path.read_text(encoding="utf-8")))
        return None
    
    def save_entity_graph(self, entity_graph: Dict):
        self._require_project()
        entities_path = self.get_shared_path("entities.json")
        entities_path.write_text(json.dumps(entity_graph, indent=2, ensure_ascii=False), encoding="utf-8")
    
    def load_entity_graph(self) -> Dict:
        self._require_project()
        entities_path = self.get_shared_path("entities.json")
        if entities_path.exists():
            return json.loads(entities_path.read_text(encoding="utf-8"))
        return {"characters": {}, "locations": {}, "items": {}}
    
    def save_shot(self, shot: ShotAsset):
        self._require_project()
        self.ensure_shot_dir(shot.shot_id)
        shot_path = self.get_shot_path(shot.shot_id, "shot.json")
        shot_path.write_text(json.dumps(shot.to_dict(), indent=2), encoding="utf-8")
        self._shot_cache[shot.shot_id] = shot
        self._update_database()
    
    def load_shot(self, shot_id: str) -> Optional[ShotAsset]:
        self._require_project()
        if shot_id in self._shot_cache:
            return self._shot_cache[shot_id]
        
        shot_path = self.get_shot_path(shot_id, "shot.json")
        if shot_path.exists():
            shot = ShotAsset.from_dict(json.loads(shot_path.read_text(encoding="utf-8")))
            self._shot_cache[shot_id] = shot
            return shot
        return None
    
    def list_shots(self) -> List[str]:
        self._require_project()
        shots_dir = self.current_project / "shots"
        if not shots_dir.exists():
            return []
        return sorted([d.name for d in shots_dir.iterdir() if d.is_dir()])
    
    def get_shots_by_status(self, status: str) -> List[ShotAsset]:
        return [self.load_shot(sid) for sid in self.list_shots() 
                if self.load_shot(sid) and self.load_shot(sid).status == status]
    
    def save_shot_asset(self, shot_id: str, filename: str, data: Any, binary: bool = False):
        self._require_project()
        self.ensure_shot_dir(shot_id)
        asset_path = self.get_shot_path(shot_id, filename)
        
        if binary:
            asset_path.write_bytes(data)
        elif isinstance(data, (dict, list)):
            asset_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            asset_path.write_text(str(data), encoding="utf-8")
        
        return asset_path
    
    def load_shot_asset(self, shot_id: str, filename: str) -> Any:
        self._require_project()
        asset_path = self.get_shot_path(shot_id, filename)
        if not asset_path.exists():
            return None
        
        if asset_path.suffix == ".json":
            return json.loads(asset_path.read_text(encoding="utf-8"))
        return asset_path.read_bytes() if asset_path.suffix in [".png", ".mp4", ".wav"] else asset_path.read_text(encoding="utf-8")
    
    def _update_database(self):
        self._require_project()
        db_path = self.get_shared_path("database.json")
        shots = self.list_shots()
        approved = len([s for s in shots if self.load_shot(s) and self.load_shot(s).status == "approved"])
        
        db = {
            "project_id": self.current_project.name,
            "updated_at": datetime.now().isoformat(),
            "shots_count": len(shots),
            "approved_shots": approved,
            "shots_by_status": {
                "pending": len(self.get_shots_by_status("pending")),
                "storyboarded": len(self.get_shots_by_status("storyboarded")),
                "animated": len(self.get_shots_by_status("animated")),
                "qa_failed": len(self.get_shots_by_status("qa_failed")),
                "approved": len(self.get_shots_by_status("approved")),
                "synced": len(self.get_shots_by_status("synced"))
            }
        }
        db_path.write_text(json.dumps(db, indent=2), encoding="utf-8")
    
    def get_database(self) -> Dict:
        self._require_project()
        db_path = self.get_shared_path("database.json")
        if db_path.exists():
            return json.loads(db_path.read_text(encoding="utf-8"))
        return {}
    
    def _save_checkpoint(self, project_dir: Path, name: str, state: Dict):
        checkpoint_path = project_dir / "checkpoints" / f"{name}.json"
        checkpoint_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    
    def save_checkpoint(self, name: str, state: Dict):
        self._require_project()
        self._save_checkpoint(self.current_project, name, state)
    
    def load_checkpoint(self, name: str) -> Optional[Dict]:
        self._require_project()
        checkpoint_path = self.current_project / "checkpoints" / f"{name}.json"
        if checkpoint_path.exists():
            return json.loads(checkpoint_path.read_text(encoding="utf-8"))
        return None
    
    def list_checkpoints(self) -> List[str]:
        self._require_project()
        checkpoints_dir = self.current_project / "checkpoints"
        return [f.stem for f in checkpoints_dir.glob("*.json")]
    
    def get_stage_summary(self) -> Dict[str, Any]:
        self._require_project()
        shots = [self.load_shot(sid) for sid in self.list_shots()]
        shots = [s for s in shots if s]
        
        return {
            "total_shots": len(shots),
            "pre_production_complete": len(shots) > 0,
            "assets_generated": len([s for s in shots if s.keyframe_path]),
            "production_complete": len([s for s in shots if s.video_approved_path]),
            "post_production_complete": self.get_output_path("final_video.mp4").exists(),
            "shots_by_status": {
                status: len([s for s in shots if s.status == status])
                for status in ["pending", "storyboarded", "animated", "qa_failed", "approved", "synced"]
            }
        }
    
    def get_output_path(self, filename: str) -> Path:
        self._require_project()
        return self.current_project / "output" / filename
    
    def log(self, message: str, level: str = "INFO"):
        self._require_project()
        log_path = self.current_project / "logs" / "pipeline.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_entry)
    
    def archive_project(self, name: str) -> Path:
        self._require_project()
        archive_path = self.projects_root / f"{name}_archive.zip"
        shutil.make_archive(str(archive_path.with_suffix("")), "zip", self.current_project)
        return archive_path
