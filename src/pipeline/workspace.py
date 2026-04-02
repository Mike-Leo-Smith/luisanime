import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional


class AgenticWorkspace:
    """Virtual Filesystem Middleware for the Agentic Filming Company."""

    def __init__(self, workspace_root: str):
        self.root = Path(workspace_root)
        self.vfs_map = {
            "00_project_config": "00_project_config",
            "01_source_material": "01_source_material",
            "02_screenplays": "02_screenplays",
            "03_lore_bible": "03_lore_bible",
            "04_production_slate": "04_production_slate",
            "05_dailies": "05_dailies",
            "06_logs": "06_logs",
        }

    def _resolve(self, virtual_path: str) -> Path:
        parts = virtual_path.strip("/").split("/", 1)
        vdir = parts[0]
        if vdir not in self.vfs_map:
            raise ValueError(f"Invalid virtual directory: {vdir}")

        rel_path = parts[1] if len(parts) > 1 else ""
        return self.root / self.vfs_map[vdir] / rel_path

    def read_file(self, virtual_path: str) -> str:
        target = self._resolve(virtual_path)
        return target.read_text(encoding="utf-8")

    def write_file(self, virtual_path: str, content: str):
        target = self._resolve(virtual_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def append_file(self, virtual_path: str, content: str):
        target = self._resolve(virtual_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(content + "\n")

    def list_dir(self, virtual_path: str) -> List[str]:
        target = self._resolve(virtual_path)
        return [f.name for f in target.iterdir()]

    def read_json(self, virtual_path: str) -> Dict:
        return json.loads(self.read_file(virtual_path))

    def exists(self, virtual_path: str) -> bool:
        """Checks if a virtual path exists on the physical filesystem."""
        try:
            return self._resolve(virtual_path).exists()
        except (ValueError, OSError):
            return False

    def write_json(self, virtual_path: str, data: Any):
        self.write_file(virtual_path, json.dumps(data, indent=4, ensure_ascii=False))

    def save_media(self, virtual_path: str, media_bytes: bytes):
        target = self._resolve(virtual_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(media_bytes)

    def get_physical_path(self, virtual_path: str) -> str:
        """Returns the real filesystem path for external tool usage (FFMPEG, MediaPipe)."""
        return str(self._resolve(virtual_path))
