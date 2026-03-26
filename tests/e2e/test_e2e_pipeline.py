import json
import pytest
from unittest.mock import MagicMock, patch

from src.core.graph import app
from src.core.state import PipelineState
from main import run_pipeline

_ENTITIES_JSON = json.dumps(
    {
        "Kaelen": {"type": "character", "description": "A lone cyborg protagonist"},
        "Zara": {"type": "character", "description": "A hacker and ally"},
    }
)
_SCENES_JSON = json.dumps(
    [
        {
            "id": "scene_1",
            "location": "Neo-Tokyo Streets",
            "time_of_day": "Night",
            "characters": ["Kaelen"],
            "description": "Kaelen evades a drone.",
        }
    ]
)
_SINGLE_SHOT_JSON = json.dumps(
    [
        {
            "id": "shot_fallback_1",
            "scene_id": "scene_1",
            "prompt": "Fallback shot after director retry.",
            "camera_movement": "Static",
            "duration": 3.0,
        }
    ]
)
_QA_APPROVED_JSON = json.dumps({"status": "approved", "reason": "No visual defects."})
_QA_REJECTED_JSON = json.dumps(
    {"status": "rejected", "reason": "Limb melting detected."}
)


def _inst(content: str) -> MagicMock:
    response = MagicMock()
    response.content = content
    inst = MagicMock()
    inst.invoke.return_value = response
    return inst


class TestFullPipelineRunsEndToEnd:
    def test_full_pipeline_runs_end_to_end(
        self,
        initial_state,
        mock_pre_production_llms_full_pipeline,
        mock_qa_linter_llm_approved,
        all_mocks,
    ):
        final_state = app.invoke(initial_state)

        assert len(final_state["entity_graph"]) > 0
        assert "Kaelen" in final_state["entity_graph"]

        assert len(final_state["scenes"]) == 2
        assert final_state["scenes"][0].id == "scene_1"
        assert final_state["scenes"][1].id == "scene_2"

        assert len(final_state["shot_list"]) == 1
        assert final_state["shot_list"][0].id == "shot_1_1"
        assert final_state["shot_list"][0].status == "approved"

        assert len(final_state["approved_clips"]) == 1
        assert "shot_1_1.mp4" in final_state["approved_clips"][0]

        assert final_state["final_video_path"] is not None
        assert final_state["final_video_path"].endswith("final_output.mp4")

        assert final_state["retry_count"] == 0
        assert final_state["last_error"] is None


class TestPipelineQaRetryLoop:
    def test_pipeline_qa_retry_loop(
        self,
        initial_state,
        mock_pre_production_llms_full_pipeline,
        mock_qa_linter_llm_reject_then_approve,
        all_mocks,
    ):
        mock_generate_video_clip = all_mocks["generate_video_clip"]
        mock_generate_video_clip.side_effect = [
            "https://mock-cdn.test/clip_rejected.mp4",
            "https://mock-cdn.test/clip_approved.mp4",
        ]

        final_state = app.invoke(initial_state)

        assert len(final_state["shot_list"]) == 1
        assert final_state["shot_list"][0].status == "approved"
        assert len(final_state["approved_clips"]) == 1
        assert "shot_1_1.mp4" in final_state["approved_clips"][0]
        assert final_state["final_video_path"] is not None

    def test_pipeline_qa_retry_resets_counter_on_approval(
        self,
        initial_state,
        mock_pre_production_llms_full_pipeline,
        mock_qa_linter_llm_reject_then_approve,
        all_mocks,
    ):
        mock_generate_video_clip = all_mocks["generate_video_clip"]
        mock_generate_video_clip.side_effect = [
            "https://mock-cdn.test/clip_rejected.mp4",
            "https://mock-cdn.test/clip_approved.mp4",
        ]

        final_state = app.invoke(initial_state)

        assert final_state["retry_count"] == 0


class TestPipelineMaxRetryFallback:
    def test_pipeline_max_retry_fallback(
        self,
        initial_state,
        all_mocks,
    ):
        pre_prod_cls = MagicMock(
            side_effect=[
                _inst(_ENTITIES_JSON),
                _inst(_SCENES_JSON),
                _inst(_SINGLE_SHOT_JSON),
                _inst(_SINGLE_SHOT_JSON),
            ]
        )

        qa_cls = MagicMock(
            side_effect=[
                _inst(_QA_REJECTED_JSON),
                _inst(_QA_REJECTED_JSON),
                _inst(_QA_REJECTED_JSON),
                _inst(_QA_APPROVED_JSON),
            ]
        )

        with patch("src.agents.pre_production.ChatGoogleGenerativeAI", pre_prod_cls):
            with patch("src.agents.production.ChatGoogleGenerativeAI", qa_cls):
                final_state = app.invoke(initial_state)

        assert qa_cls.call_count == 4
        assert pre_prod_cls.call_count == 4

        assert len(final_state["approved_clips"]) >= 1
        assert final_state["final_video_path"] is not None


class TestPipelineViaMainRunPipeline:
    def test_pipeline_via_main_run_pipeline(
        self,
        mock_pre_production_llms_full_pipeline,
        mock_qa_linter_llm_approved,
        all_mocks,
        tmp_path,
    ):
        novel = (
            "In the rain-drenched streets of Neo-Tokyo, Kaelen gripped his pulse-blade. "
            "A hover-drone descended, its red sensors locking on his position."
        )

        with patch("main.app.invoke") as mock_invoke:
            mock_invoke.return_value = {
                "entity_graph": {"Kaelen": MagicMock(), "Neo-Tokyo": MagicMock()},
                "scenes": [MagicMock(), MagicMock()],
                "shot_list": [MagicMock(), MagicMock()],
                "approved_clips": [
                    "https://mock-cdn.test/clip_001.mp4",
                    "https://mock-cdn.test/clip_002.mp4",
                ],
                "final_video_path": str(tmp_path / "final_output.mp4"),
                "retry_count": 0,
                "last_error": None,
                "project_dir": str(tmp_path),
                "style": "anime",
            }

            final_state = run_pipeline(novel)

        assert mock_invoke.called
        invoked_state = mock_invoke.call_args[0][0]
        assert invoked_state["novel_text"] == novel
        assert invoked_state["style"] == "anime"
        assert invoked_state["project_dir"] == "./workspace"

        assert len(final_state["scenes"]) == 2
        assert len(final_state["shot_list"]) == 2
        assert len(final_state["approved_clips"]) == 2
        assert final_state["final_video_path"] is not None
