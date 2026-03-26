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

    def create_project(
        self, name: str, novel_text: str, config: Dict[str, Any]
    ) -> Path:
        project_dir = self.projects_root / name
        if project_dir.exists():
            raise ValueError(f"Project '{name}' already exists")

        dirs = [
            "src",
            "assets/characters",
            "assets/locations",
            "assets/audio",
            "assets/lore",
            "scenes",
            "cache",
            "checkpoints",
            "output",
            "logs",
        ]

        for d in dirs:
            (project_dir / d).mkdir(parents=True, exist_ok=True)

        (project_dir / "src" / "novel.txt").write_text(novel_text, encoding="utf-8")

        default_config = self._load_template_config()
        default_config.update(config)
        (project_dir / "config.yaml").write_text(
            yaml.dump(default_config, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )

        (project_dir / "assets" / "lore" / "entities.json").write_text(
            json.dumps({}, indent=2), encoding="utf-8"
        )

        readme = f"""# {name}

AFP Video Project

## Structure

- `src/` - Source materials (novel.txt, scripts)
- `assets/` - Generated assets (characters, locations, lore, audio)
- `scenes/` - Scene-based shot organization
- `cache/` - Cache files
- `checkpoints/` - Pipeline checkpoints
- `output/` - Final deliverables
- `logs/` - Pipeline logs
- `config.yaml` - Project configuration

## Pipeline Stages

1. `lore` - Segment chapters and extract entities
2. `scenes` - Break into scenes
3. `shots` - Generate shot list
4. `storyboard` - Generate keyframes
5. `animate` - Generate video clips
6. `qa` - Quality assurance
7. `composite` - Final assembly

## Usage

```bash
python main.py lore {name}
python main.py scenes {name}
python main.py shots {name}
python main.py produce {name}
```
"""
        (project_dir / "README.md").write_text(readme, encoding="utf-8")

        self._save_checkpoint(
            project_dir,
            "init",
            {
                "status": "created",
                "timestamp": datetime.now().isoformat(),
                "stage": "init",
            },
        )

        return project_dir

    def load_project(self, name: str) -> Path:
        project_dir = self.projects_root / name
        if not project_dir.exists():
            raise ValueError(f"Project '{name}' not found")

        self.current_project = project_dir
        config_path = project_dir / "config.yaml"
        self.project_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self._shot_cache.clear()

        return project_dir

    def _load_template_config(self) -> Dict[str, Any]:
        script_dir = Path(__file__).parent
        root_dir = script_dir.parent.parent
        template_path = root_dir / "config.yaml.template"
        if not template_path.exists():
            raise FileNotFoundError(
                f"config.yaml.template not found at {template_path}. "
                "Please ensure the template file exists."
            )
        return yaml.safe_load(template_path.read_text(encoding="utf-8"))

    def _require_project(self):
        if self.current_project is None:
            raise RuntimeError("No project loaded. Call load_project() first.")

    def get_src_path(self, *subpaths) -> Path:
        self._require_project()
        return self.current_project / "src" / Path(*subpaths)

    def load_novel(self) -> str:
        self._require_project()
        novel_path = self.get_src_path("novel.txt")
        if novel_path.exists():
            return novel_path.read_text(encoding="utf-8")
        return ""

    def get_index_path(self, *subpaths) -> Path:
        self._require_project()
        return self.current_project / "index" / Path(*subpaths)

    def get_cache_path(self, *subpaths) -> Path:
        self._require_project()
        return self.current_project / "cache" / Path(*subpaths)

    def get_checkpoint_path(self, name: str) -> Path:
        self._require_project()
        return self.current_project / "checkpoints" / f"{name}.json"

    def _save_checkpoint(self, project_dir: Path, name: str, state: Dict):
        checkpoint_path = project_dir / "checkpoints" / f"{name}.json"
        checkpoint_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def save_checkpoint(self, name: str, state: Dict):
        self._require_project()
        self._save_checkpoint(self.current_project, name, state)

    def load_checkpoint(self, name: str) -> Optional[Dict]:
        self._require_project()
        checkpoint_path = self.get_checkpoint_path(name)
        if checkpoint_path.exists():
            return json.loads(checkpoint_path.read_text(encoding="utf-8"))
        return None

    def list_checkpoints(self) -> List[str]:
        self._require_project()
        checkpoints_dir = self.current_project / "checkpoints"
        return [f.stem for f in checkpoints_dir.glob("*.json")]

    def update_project_stats(self, **kwargs):
        self._require_project()
        project_file = self.current_project / "index" / "project.json"
        if project_file.exists():
            data = json.loads(project_file.read_text(encoding="utf-8"))
            data["updated_at"] = datetime.now().isoformat()
            data["stats"].update(kwargs)
            project_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_assets_path(self, *subpaths) -> Path:
        self._require_project()
        return self.current_project / "assets" / Path(*subpaths)

    def save_character(self, character: CharacterProfile):
        self._require_project()
        char_path = self.get_assets_path("characters", f"{character.id}.json")
        char_path.write_text(
            json.dumps(character.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.log(f"Saved character profile: {character.id}")

    def load_character(self, char_id: str) -> Optional[CharacterProfile]:
        self._require_project()
        char_path = self.get_assets_path("characters", f"{char_id}.json")
        if char_path.exists():
            return CharacterProfile.from_dict(
                json.loads(char_path.read_text(encoding="utf-8"))
            )
        return None

    def list_characters(self) -> List[str]:
        self._require_project()
        chars_dir = self.get_assets_path("characters")
        return [f.stem for f in chars_dir.glob("*.json")]

    def save_location(self, location: LocationProfile):
        self._require_project()
        loc_path = self.get_assets_path("locations", f"{location.id}.json")
        loc_path.write_text(
            json.dumps(location.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.log(f"Saved location profile: {location.id}")

    def load_location(self, loc_id: str) -> Optional[LocationProfile]:
        self._require_project()
        loc_path = self.get_assets_path("locations", f"{loc_id}.json")
        if loc_path.exists():
            return LocationProfile.from_dict(
                json.loads(loc_path.read_text(encoding="utf-8"))
            )
        return None

    def save_entity_graph(self, entity_graph: Dict):
        self._require_project()
        entities_path = self.get_assets_path("lore", "entities.json")
        entities_path.write_text(
            json.dumps(entity_graph, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def load_entity_graph(self) -> Dict:
        self._require_project()
        entities_path = self.get_assets_path("lore", "entities.json")
        if entities_path.exists():
            return json.loads(entities_path.read_text(encoding="utf-8"))
        return {}

    def get_scene_path(self, scene_id: str, *subpaths) -> Path:
        self._require_project()
        return self.current_project / "scenes" / scene_id / Path(*subpaths)

    def ensure_scene_dir(self, scene_id: str) -> Path:
        self._require_project()
        scene_dir = self.current_project / "scenes" / scene_id
        scene_dir.mkdir(parents=True, exist_ok=True)
        (scene_dir / "shots").mkdir(exist_ok=True)
        return scene_dir

    def save_scene_metadata(self, scene_id: str, metadata: Dict):
        self._require_project()
        scene_dir = self.ensure_scene_dir(scene_id)
        meta_path = scene_dir / "metadata.json"
        meta_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def load_scene_metadata(self, scene_id: str) -> Optional[Dict]:
        self._require_project()
        meta_path = self.get_scene_path(scene_id, "metadata.json")
        if meta_path.exists():
            return json.loads(meta_path.read_text(encoding="utf-8"))
        return None

    def list_scenes(self) -> List[str]:
        self._require_project()
        scenes_dir = self.current_project / "scenes"
        if not scenes_dir.exists():
            return []
        return sorted([d.name for d in scenes_dir.iterdir() if d.is_dir()])

    def get_shot_path(self, scene_id: str, shot_id: str, *subpaths) -> Path:
        self._require_project()
        return (
            self.current_project
            / "scenes"
            / scene_id
            / "shots"
            / shot_id
            / Path(*subpaths)
        )

    def ensure_shot_dir(self, scene_id: str, shot_id: str) -> Path:
        self._require_project()
        shot_dir = self.current_project / "scenes" / scene_id / "shots" / shot_id
        shot_dir.mkdir(parents=True, exist_ok=True)
        return shot_dir

    def save_shot(self, scene_id: str, shot: ShotAsset):
        self._require_project()
        self.ensure_shot_dir(scene_id, shot.shot_id)
        shot_path = self.get_shot_path(scene_id, shot.shot_id, "metadata.json")
        shot_path.write_text(json.dumps(shot.to_dict(), indent=2), encoding="utf-8")
        self._shot_cache[f"{scene_id}/{shot.shot_id}"] = shot
        self._update_database()

    def load_shot(self, scene_id: str, shot_id: str) -> Optional[ShotAsset]:
        self._require_project()
        cache_key = f"{scene_id}/{shot_id}"
        if cache_key in self._shot_cache:
            return self._shot_cache[cache_key]

        shot_path = self.get_shot_path(scene_id, shot_id, "metadata.json")
        if shot_path.exists():
            shot = ShotAsset.from_dict(
                json.loads(shot_path.read_text(encoding="utf-8"))
            )
            self._shot_cache[cache_key] = shot
            return shot
        return None

    def list_shots(self, scene_id: str) -> List[str]:
        self._require_project()
        shots_dir = self.current_project / "scenes" / scene_id / "shots"
        if not shots_dir.exists():
            return []
        return sorted([d.name for d in shots_dir.iterdir() if d.is_dir()])

    def save_shot_asset(
        self,
        scene_id: str,
        shot_id: str,
        filename: str,
        data: Any,
        binary: bool = False,
    ):
        self._require_project()
        self.ensure_shot_dir(scene_id, shot_id)
        asset_path = self.get_shot_path(scene_id, shot_id, filename)

        if binary:
            asset_path.write_bytes(data)
        elif isinstance(data, (dict, list)):
            asset_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        else:
            asset_path.write_text(str(data), encoding="utf-8")

        return asset_path

    def load_shot_asset(self, scene_id: str, shot_id: str, filename: str) -> Any:
        self._require_project()
        asset_path = self.get_shot_path(scene_id, shot_id, filename)
        if not asset_path.exists():
            return None

        if asset_path.suffix == ".json":
            return json.loads(asset_path.read_text(encoding="utf-8"))
        return (
            asset_path.read_bytes()
            if asset_path.suffix in [".png", ".mp4", ".wav"]
            else asset_path.read_text(encoding="utf-8")
        )

    def _update_database(self):
        self._require_project()
        project_file = self.current_project / "index" / "project.json"
        if not project_file.exists():
            return

        data = json.loads(project_file.read_text(encoding="utf-8"))
        scenes = self.list_scenes()
        total_shots = sum(len(self.list_shots(s)) for s in scenes)

        data["updated_at"] = datetime.now().isoformat()
        data["stats"]["scenes"] = len(scenes)
        data["stats"]["shots"] = total_shots

        project_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

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
        shutil.make_archive(
            str(archive_path.with_suffix("")), "zip", self.current_project
        )
        return archive_path

    def get_stage_summary(self) -> Dict[str, Any]:
        self._require_project()
        scenes = self.list_scenes()
        total_shots = 0
        shots_by_status = {
            "pending": 0,
            "storyboarded": 0,
            "animated": 0,
            "qa_failed": 0,
            "approved": 0,
            "synced": 0,
        }

        for scene_id in scenes:
            for shot_id in self.list_shots(scene_id):
                shot = self.load_shot(scene_id, shot_id)
                if shot:
                    total_shots += 1
                    shots_by_status[shot.status] = (
                        shots_by_status.get(shot.status, 0) + 1
                    )

        return {
            "total_scenes": len(scenes),
            "total_shots": total_shots,
            "pre_production_complete": total_shots > 0,
            "shots_by_status": shots_by_status,
            "output_ready": self.get_output_path("final_video.mp4").exists(),
        }
