import os
import json
import pytest
from unittest.mock import MagicMock, patch

from src.core.state import PipelineState, SceneIR, Shot, EntityState

_HERE = os.path.dirname(__file__)
_TEST_NOVEL_PATH = os.path.join(_HERE, "test_project", "novel.txt")

_ENTITIES_JSON = json.dumps(
    {
        "Kaelen": {"type": "character", "description": "A lone cyborg protagonist"},
        "Zara": {"type": "character", "description": "A hacker and ally"},
        "Neo-Tokyo": {
            "type": "location",
            "description": "Neon-drenched futuristic city",
        },
        "Sapphire Tower": {"type": "location", "description": "The Syndicate HQ"},
    }
)

_SCENES_JSON = json.dumps(
    [
        {
            "id": "scene_1",
            "location": "Neo-Tokyo Streets",
            "time_of_day": "Night",
            "characters": ["Kaelen"],
            "description": "Kaelen evades a Mark-7 Hunter drone in the rain-soaked streets.",
        },
        {
            "id": "scene_2",
            "location": "Safehouse above Ramen Stall",
            "time_of_day": "Night",
            "characters": ["Zara"],
            "description": "Zara monitors Kaelen's biosigns and guides him through the city grid.",
        },
    ]
)

_SHOTS_JSON = json.dumps(
    [
        {
            "id": "shot_1_1",
            "scene_id": "scene_1",
            "prompt": "Wide aerial shot of Neo-Tokyo rain-soaked streets at night.",
            "camera_movement": "Drone descend",
            "duration": 4.0,
        },
    ]
)

_QA_APPROVED_JSON = json.dumps(
    {"status": "approved", "reason": "No visual defects detected."}
)
_QA_REJECTED_JSON = json.dumps(
    {"status": "rejected", "reason": "Limb melting detected on left arm."}
)


def _make_llm_response(content: str) -> MagicMock:
    mock_response = MagicMock()
    mock_response.content = content
    return mock_response


def _llm_class_mock(content: str) -> MagicMock:
    instance = MagicMock()
    instance.invoke.return_value = _make_llm_response(content)
    cls = MagicMock(return_value=instance)
    return cls


@pytest.fixture()
def mock_pre_production_llms_full_pipeline():
    lore_inst = MagicMock()
    lore_inst.invoke.return_value = _make_llm_response(_ENTITIES_JSON)

    scene_inst = MagicMock()
    scene_inst.invoke.return_value = _make_llm_response(_SCENES_JSON)

    shot_inst = MagicMock()
    shot_inst.invoke.return_value = _make_llm_response(_SHOTS_JSON)

    mock_cls = MagicMock(side_effect=[lore_inst, scene_inst, shot_inst])
    with patch("src.agents.pre_production.ChatGoogleGenerativeAI", mock_cls):
        yield mock_cls


@pytest.fixture()
def mock_pre_production_llms_director_only():
    shot_inst = MagicMock()
    shot_inst.invoke.return_value = _make_llm_response(_SHOTS_JSON)
    mock_cls = MagicMock(return_value=shot_inst)
    with patch("src.agents.pre_production.ChatGoogleGenerativeAI", mock_cls):
        yield mock_cls


@pytest.fixture()
def mock_qa_linter_llm_approved():
    inst = MagicMock()
    inst.invoke.return_value = _make_llm_response(_QA_APPROVED_JSON)
    mock_cls = MagicMock(return_value=inst)
    with patch("src.agents.production.ChatGoogleGenerativeAI", mock_cls):
        yield mock_cls


@pytest.fixture()
def mock_qa_linter_llm_rejected():
    inst = MagicMock()
    inst.invoke.return_value = _make_llm_response(_QA_REJECTED_JSON)
    mock_cls = MagicMock(return_value=inst)
    with patch("src.agents.production.ChatGoogleGenerativeAI", mock_cls):
        yield mock_cls


@pytest.fixture()
def mock_qa_linter_llm_reject_then_approve():
    rejected_inst = MagicMock()
    rejected_inst.invoke.return_value = _make_llm_response(_QA_REJECTED_JSON)
    approved_inst = MagicMock()
    approved_inst.invoke.return_value = _make_llm_response(_QA_APPROVED_JSON)
    mock_cls = MagicMock(side_effect=[rejected_inst, approved_inst])
    with patch("src.agents.production.ChatGoogleGenerativeAI", mock_cls):
        yield mock_cls


@pytest.fixture()
def mock_generate_image_keyframe():
    with patch(
        "src.agents.asset_locking.generate_image_keyframe",
        return_value="https://mock-cdn.test/keyframe_001.jpg",
    ) as mock:
        yield mock


@pytest.fixture()
def mock_generate_video_clip():
    with patch(
        "src.agents.production.generate_video_clip",
        return_value="https://mock-cdn.test/clip_001.mp4",
    ) as mock:
        yield mock


@pytest.fixture()
def mock_subprocess_run():
    with patch("src.agents.post_production.subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0)
        yield mock


@pytest.fixture()
def mock_ffmpeg(tmp_path):
    sentinel = str(tmp_path / "final_output.mp4")
    sentinel_file = tmp_path / "final_output.mp4"
    sentinel_file.write_bytes(b"MOCK_VIDEO")

    with patch("src.agents.post_production.ffmpeg") as mock_ffmpeg_mod:
        mock_input = MagicMock()
        mock_concat = MagicMock()
        mock_output_node = MagicMock()
        mock_overwrite = MagicMock()

        mock_ffmpeg_mod.input.return_value = mock_input
        mock_ffmpeg_mod.concat.return_value = mock_concat
        mock_ffmpeg_mod.output.return_value = mock_output_node
        mock_output_node.overwrite_output.return_value = mock_overwrite
        mock_overwrite.run.return_value = None
        mock_ffmpeg_mod.Error = Exception

        yield mock_ffmpeg_mod, sentinel


@pytest.fixture()
def mock_requests_get():
    with patch("src.agents.production.requests.get") as mock:
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"fake_video_data"]
        mock.return_value = mock_response
        yield mock


@pytest.fixture()
def all_mocks(
    mock_generate_image_keyframe,
    mock_generate_video_clip,
    mock_subprocess_run,
    mock_ffmpeg,
    mock_requests_get,
):
    ffmpeg_mock, sentinel = mock_ffmpeg
    return {
        "generate_image_keyframe": mock_generate_image_keyframe,
        "generate_video_clip": mock_generate_video_clip,
        "subprocess_run": mock_subprocess_run,
        "ffmpeg": ffmpeg_mock,
        "final_video_sentinel": sentinel,
    }


@pytest.fixture()
def novel_text():
    with open(_TEST_NOVEL_PATH, "r") as f:
        return f.read()


@pytest.fixture()
def initial_state(novel_text, tmp_path) -> PipelineState:
    return {  # type: ignore[return-value]
        "project_dir": str(tmp_path),
        "style": "anime",
        "novel_text": novel_text,
        "current_chapter_id": "ch_e2e_test",
        "entity_graph": {},
        "scenes": [],
        "current_scene_index": 0,
        "shot_list": [],
        "current_shot_index": 0,
        "retry_count": 0,
        "last_error": None,
        "approved_clips": [],
    }


@pytest.fixture()
def state_with_scenes(initial_state) -> PipelineState:
    state = dict(initial_state)
    state["entity_graph"] = {
        "Kaelen": EntityState(
            id="Kaelen",
            attributes={"type": "character", "description": "A lone cyborg"},
        ),
        "Zara": EntityState(
            id="Zara",
            attributes={"type": "character", "description": "A hacker ally"},
        ),
    }
    state["scenes"] = [
        SceneIR(
            id="scene_1",
            location="Neo-Tokyo Streets",
            time_of_day="Night",
            characters=["Kaelen"],
            description="Kaelen evades a Mark-7 Hunter drone.",
        ),
        SceneIR(
            id="scene_2",
            location="Safehouse",
            time_of_day="Night",
            characters=["Zara"],
            description="Zara monitors Kaelen remotely.",
        ),
    ]
    return state  # type: ignore[return-value]


@pytest.fixture()
def state_with_shot_list(state_with_scenes) -> PipelineState:
    state = dict(state_with_scenes)
    state["shot_list"] = [
        Shot(
            id="shot_1_1",
            scene_id="scene_1",
            prompt="Wide aerial shot of Neo-Tokyo rain-soaked streets at night.",
            camera_movement="Drone descend",
            duration=4.0,
        ),
    ]
    state["current_shot_index"] = 0
    return state  # type: ignore[return-value]
