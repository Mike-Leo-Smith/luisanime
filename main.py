from src.core.graph import app
from src.core.state import PipelineState
import uuid


def run_pipeline(text: str):
    # Initialize state
    initial_state: PipelineState = {
        "novel_text": text,
        "current_chapter_id": str(uuid.uuid4()),
        "entity_graph": {},
        "scenes": [],
        "current_scene_index": 0,
        "shot_list": [],
        "current_shot_index": 0,
        "retry_count": 0,
        "last_error": None,
        "approved_clips": [],
        "project_dir": "./workspace",
        "style": "anime",
    }

    # Run the graph
    print("🚀 Starting Agentic Filming Pipeline...")
    final_state = app.invoke(initial_state)

    print("\n✅ Pipeline Completed!")
    print(f"Total Scenes: {len(final_state['scenes'])}")
    print(f"Total Shots: {len(final_state['shot_list'])}")
    print(f"Entities Found: {list(final_state['entity_graph'].keys())}")

    return final_state


if __name__ == "__main__":
    sample_text = """
    In the neon-drenched streets of Neo-Tokyo, a lone cyborg named Kaelen 
    walked towards the abandoned Sapphire Tower. Rain streaked his metallic 
    cheeks as he gripped the hilt of his pulse-blade. Suddenly, a hover-drone 
    descended from the smog, its red sensors locking onto him.
    """
    run_pipeline(sample_text)
