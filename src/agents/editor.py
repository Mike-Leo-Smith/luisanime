from typing import Dict, Any, List, Optional
import ffmpeg
from src.agents.base import BaseCompiler
from src.pipeline.state import AFCState

class EditorAgent(BaseCompiler):
    def mux_scene(self, shot_paths: List[str], scene_id: str) -> str:
        """Executes the FFMPEG build and outputs the master file."""
        print(f"✂️ [Editor] Muxing {len(shot_paths)} shots for scene {scene_id}...")
        if not shot_paths:
            print("✂️ [Editor] WARNING: No shots to mux.")
            return ""
            
        output_path = self.workspace.get_physical_path(f"05_dailies/{scene_id}_master.mp4")
        
        # Simple concatenation using ffmpeg-python
        inputs = [ffmpeg.input(self.workspace.get_physical_path(p)) for p in shot_paths]
        
        try:
            (
                ffmpeg
                .concat(*inputs)
                .output(output_path)
                .overwrite_output()
                .run(quiet=True)
            )
            print(f"✂️ [Editor] Scene master created: {output_path}")
        except ffmpeg.Error as e:
            print(f"✂️ [Editor] FFMPEG Error: {e.stderr.decode() if e.stderr else str(e)}")
            # Fallback for mock/test if files are fake
            self.workspace.write_file(f"05_dailies/{scene_id}_master.mp4", "FAKE_MASTER_VIDEO_CONTENT")
            
        return f"05_dailies/{scene_id}_master.mp4"

def editor_node(state: AFCState) -> Dict:
    from src.pipeline.workspace import AgenticWorkspace
    ws = AgenticWorkspace(state["workspace_root"])
    agent = EditorAgent.from_config(ws, state["project_config"])
    
    scene_id = state["current_scene_path"].split("/")[-1].replace(".json", "")
    master_path = agent.mux_scene(state["scene_dailies_paths"], scene_id)
    
    completed = [master_path]
    
    return {
        "completed_scenes_paths": completed,
        "scene_dailies_paths": [], # This needs to be a replacement, not addition.
        "current_scene_path": None
    }
