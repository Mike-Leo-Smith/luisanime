from typing import Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
import requests
import time

from src.core.state import PipelineState
from src.config import load_config
from src.utils.json_utils import extract_json


def generate_video_clip(prompt: str, keyframe_url: str, config: Any) -> str | None:
    """
    Calls MiniMax-Hailuo-02 for Video Generation.
    Reference: https://platform.minimaxi.com/docs/api-reference/video-generation-fl2v
    """
    print(f"--- VIDEO GEN: {prompt} ---")

    model_cfg = config.render_plane.animator
    api_key = model_cfg.api_key

    base_url = "https://api.minimaxi.com/v1"
    gen_url = f"{base_url}/video_generation"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {
        "model": "MiniMax-Hailuo-02",
        "prompt": prompt,
        "duration": 6,
        "resolution": "1080P",
    }

    response = requests.post(gen_url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"MiniMax API Error: {response.text}")
        response.raise_for_status()

    task_id = response.json().get("task_id")
    print(f"Started video task {task_id}. Polling...")

    status_url = f"{base_url}/query/video_generation"
    status = "preparing"
    video_url = None

    while status.lower() in ["preparing", "queueing", "processing"]:
        time.sleep(15)
        res = requests.get(f"{status_url}?task_id={task_id}", headers=headers)
        data = res.json()
        status = data.get("status")

        if status.lower() == "success":
            file_id = data.get("file_id")
            if file_id:
                # Retrieve the file to get the download URL
                retrieve_url = f"{base_url}/files/retrieve?file_id={file_id}"
                retrieve_res = requests.get(retrieve_url, headers=headers)
                retrieve_data = retrieve_res.json()
                video_url = retrieve_data.get("file", {}).get("download_url")
                print(f"Video generation successful: {video_url}")
                break
            else:
                raise Exception("Video succeeded but no file_id returned")
        elif status.lower() == "fail":
            error_msg = data.get("error_msg", "Unknown error")
            raise Exception(f"MiniMax video task failed: {error_msg}")

        print(f"Task {task_id} still {status}...")

    return video_url


def animator(state: PipelineState) -> PipelineState:
    """Generates video from Keyframe and Prompt."""
    idx = state["current_shot_index"]
    shot = state["shot_list"][idx]

    print(f"--- ANIMATOR: Generating Video for Shot {shot.id} ---")

    config = load_config()

    try:
        if not shot.keyframe_url:
            raise ValueError(f"Shot {shot.id} is missing a keyframe.")

        video_url = generate_video_clip(shot.prompt, shot.keyframe_url, config)
        state["shot_list"][idx].video_url = video_url
        state["shot_list"][idx].status = "animated"
    except Exception as e:
        print(f"Error in animator: {e}")
        state["last_error"] = str(e)

    return state


def qa_linter(state: PipelineState) -> PipelineState:
    """Inspects the generated video using Gemini VLM."""
    idx = state["current_shot_index"]
    shot = state["shot_list"][idx]

    print(f"--- QA LINTER: Inspecting Shot {idx} ---")

    config = load_config()
    model_cfg = config.control_plane.agents["qa_linter"]

    llm = ChatGoogleGenerativeAI(
        model=model_cfg.model,
        google_api_key=model_cfg.api_key,
        temperature=model_cfg.temperature,
    )

    prompt = f"""
    Inspect the following generated video clip against the intended prompt.
    Intended Prompt: {shot.prompt}
    Video URL: {shot.video_url}
    
    Perform the following checks:
    1. Topological Check: Are there limb melting or multi-finger mutations?
    2. Consistency Check: Does the character match the established visual reference?
    3. Physical Hallucination: Are there impossible physics or fluid-like rigid bodies?
    
    Return a JSON object:
    {{
        "status": "approved" or "rejected",
        "reason": "..."
    }}
    """

    response = llm.invoke([HumanMessage(content=prompt)])

    try:
        qa_result = extract_json(response.content)
        if qa_result["status"] == "approved":
            state["shot_list"][idx].status = "approved"
            state["retry_count"] = 0
            if shot.video_url:
                if shot.video_url.startswith("http"):
                    import os
                    import requests

                    project_dir = state.get("project_dir", "./workspace")
                    os.makedirs(project_dir, exist_ok=True)
                    local_path = os.path.join(project_dir, f"shot_{shot.id}.mp4")
                    try:
                        r = requests.get(shot.video_url, stream=True, timeout=10)
                        r.raise_for_status()
                        with open(local_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                        state["approved_clips"].append(local_path)
                    except Exception as e:
                        print(f"Failed to download {shot.video_url}: {e}")
                        state["approved_clips"].append(shot.video_url)
                else:
                    state["approved_clips"].append(shot.video_url)
        else:
            state["shot_list"][idx].status = "qa_failed"
            state["retry_count"] += 1
            print(f"QA REJECTED: {qa_result['reason']}")
    except Exception as e:
        print(f"Error in QA Linter: {e}")
        state["last_error"] = str(e)

    return state
