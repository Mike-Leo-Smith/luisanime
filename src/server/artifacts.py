from pathlib import Path
from typing import Any, Dict, List, Optional

EDITABLE_EXTS = {".json", ".md", ".txt", ".yaml", ".yml", ".log"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".webm"}
TEXT_EXTS = {".txt", ".log", ".yaml", ".yml"}


def kind_for(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext == ".json":
        return "json"
    if ext == ".md":
        return "markdown"
    if ext in TEXT_EXTS:
        return "text"
    return "binary"


def _entry(project_root: Path, p: Path) -> Dict[str, Any]:
    rel = p.relative_to(project_root).as_posix()
    return {
        "path": rel,
        "name": p.name,
        "kind": kind_for(p),
        "editable": p.suffix.lower() in EDITABLE_EXTS,
        "size": p.stat().st_size if p.exists() else 0,
    }


def _glob_sorted(root: Path, pattern: str) -> List[Path]:
    if not root.exists():
        return []
    return sorted(root.glob(pattern), key=lambda p: p.name)


def discover(project_root: Path, node: Optional[str] = None) -> Dict[str, List[Dict]]:
    """Return artifacts grouped by category, optionally filtered to a node's outputs."""
    project_root = project_root.resolve()
    groups: Dict[str, List[Dict]] = {}

    if node in (None, "screenwriter"):
        groups["screenplays"] = [
            _entry(project_root, p)
            for p in _glob_sorted(project_root / "02_screenplays", "*.json")
        ]

    if node in (None, "production_designer", "design_qa"):
        lore = project_root / "03_lore_bible"
        groups["lore_bible"] = [
            _entry(project_root, p) for p in _glob_sorted(lore, "*.md")
        ]
        groups["designs"] = [
            _entry(project_root, p)
            for p in _glob_sorted(lore / "designs", "*")
            if p.is_file()
        ]
        groups["locations"] = [
            _entry(project_root, p)
            for p in _glob_sorted(lore / "designs" / "locations", "*")
            if p.is_file()
        ]

    if node in (None, "director", "script_coordinator"):
        groups["shot_plans"] = [
            _entry(project_root, p)
            for p in _glob_sorted(
                project_root / "04_production_slate" / "shots", "*.json"
            )
        ]

    if node in (None, "cinematographer", "storyboard_qa", "continuity_supervisor", "lead_animator"):
        dailies = project_root / "05_dailies"
        shot_dirs: List[Dict] = []
        if dailies.exists():
            for shot_dir in sorted(dailies.iterdir()):
                if not shot_dir.is_dir():
                    continue
                shot_dirs.append(
                    {
                        "shot_id": shot_dir.name,
                        "files": [
                            _entry(project_root, p)
                            for p in sorted(shot_dir.iterdir())
                            if p.is_file()
                        ],
                    }
                )
        groups["dailies"] = shot_dirs

    if node in (None, "editor"):
        finals = [
            _entry(project_root, p)
            for p in _glob_sorted(project_root / "05_dailies", "*.mp4")
            if p.is_file()
        ]
        groups["final_renders"] = finals

    if node is None:
        groups["logs"] = [
            _entry(project_root, p)
            for p in _glob_sorted(project_root / "06_logs", "*")
            if p.is_file()
        ]

    return groups


def safe_resolve(project_root: Path, rel_path: str) -> Path:
    project_root = project_root.resolve()
    target = (project_root / rel_path).resolve()
    if target != project_root and not str(target).startswith(str(project_root) + "/"):
        raise PermissionError("Path traversal denied")
    return target
