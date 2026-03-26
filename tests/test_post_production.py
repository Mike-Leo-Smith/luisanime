import os
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.core.state import PipelineState, Shot
from src.agents.post_production import lip_sync_agent, compositor


def _base_state(**overrides) -> PipelineState:
    state: PipelineState = {
        "project_dir": "/tmp/test_project",
        "style": "anime",
        "novel_text": "...",
        "current_chapter_id": "ch1",
        "entity_graph": {},
        "scenes": [],
        "current_scene_index": 0,
        "shot_list": [],
        "current_shot_index": 0,
        "retry_count": 0,
        "last_error": None,
        "approved_clips": [],
    }
    for key, value in overrides.items():
        state[key] = value  # type: ignore[literal-required]
    return state


def _mock_config(device: str = "cpu") -> MagicMock:
    """Return a MagicMock that mimics GlobalConfig with lip_sync device."""
    cfg = MagicMock()
    cfg.post_processing.lip_sync = {"device": device}
    return cfg


# ---------------------------------------------------------------------------
# lip_sync_agent tests
# ---------------------------------------------------------------------------


class TestLipSyncAgent:
    @patch("src.agents.post_production.subprocess.run")
    @patch("src.agents.post_production.load_config")
    def test_lip_sync_agent_processes_clips(
        self, mock_load_config, mock_subprocess_run
    ):
        """Happy path: each approved clip gets a synced counterpart with sync_ prefix."""
        mock_load_config.return_value = _mock_config(device="cuda")
        mock_subprocess_run.return_value = MagicMock(returncode=0)

        state = _base_state(
            approved_clips=[
                "/workspace/shot_1.mp4",
                "/workspace/shot_2.mp4",
            ]
        )

        result = lip_sync_agent(state)

        assert result["synced_clips"] == [  # type: ignore[typeddict-item]
            "/workspace/sync_shot_1.mp4",
            "/workspace/sync_shot_2.mp4",
        ]
        # subprocess.run must have been called once per clip
        assert mock_subprocess_run.call_count == 2
        # Verify --device cuda was forwarded
        first_cmd = mock_subprocess_run.call_args_list[0][0][0]
        assert "--device" in first_cmd
        assert "cuda" in first_cmd

    @patch("src.agents.post_production.subprocess.run")
    @patch("src.agents.post_production.load_config")
    def test_lip_sync_agent_fallback_on_failure(
        self, mock_load_config, mock_subprocess_run
    ):
        """When MuseTalk raises CalledProcessError the original clip is kept."""
        mock_load_config.return_value = _mock_config()
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["python", "-m", "musetalk.inference"]
        )

        state = _base_state(
            approved_clips=["/workspace/shot_1.mp4", "/workspace/shot_2.mp4"]
        )

        result = lip_sync_agent(state)

        assert result["synced_clips"] == [  # type: ignore[typeddict-item]
            "/workspace/shot_1.mp4",
            "/workspace/shot_2.mp4",
        ]

    @patch("src.agents.post_production.subprocess.run")
    @patch("src.agents.post_production.load_config")
    def test_lip_sync_agent_no_clips(self, mock_load_config, mock_subprocess_run):
        """Empty approved_clips list yields an empty synced_clips list."""
        mock_load_config.return_value = _mock_config()

        state = _base_state(approved_clips=[])

        result = lip_sync_agent(state)

        assert result["synced_clips"] == []  # type: ignore[typeddict-item]
        mock_subprocess_run.assert_not_called()

    @patch("src.agents.post_production.subprocess.run")
    @patch("src.agents.post_production.load_config")
    def test_lip_sync_agent_fallback_on_file_not_found(
        self, mock_load_config, mock_subprocess_run
    ):
        """When MuseTalk binary is missing (FileNotFoundError) original clip is kept."""
        mock_load_config.return_value = _mock_config()
        mock_subprocess_run.side_effect = FileNotFoundError("python not found")

        state = _base_state(approved_clips=["/workspace/shot_1.mp4"])

        result = lip_sync_agent(state)

        assert result["synced_clips"] == ["/workspace/shot_1.mp4"]  # type: ignore[typeddict-item]

    @patch("src.agents.post_production.subprocess.run")
    @patch("src.agents.post_production.load_config")
    def test_lip_sync_agent_synced_count_matches_approved(
        self, mock_load_config, mock_subprocess_run
    ):
        """The count of synced_clips always equals approved_clips regardless of failures."""
        mock_load_config.return_value = _mock_config()
        # Alternate: first succeeds, second raises
        mock_subprocess_run.side_effect = [
            MagicMock(returncode=0),
            subprocess.CalledProcessError(1, ["python"]),
            MagicMock(returncode=0),
        ]

        clips = [f"/workspace/shot_{i}.mp4" for i in range(3)]
        state = _base_state(approved_clips=clips)

        result = lip_sync_agent(state)

        assert len(result["synced_clips"]) == len(clips)  # type: ignore[typeddict-item]

    @patch("src.agents.post_production.subprocess.run")
    @patch("src.agents.post_production.load_config")
    def test_lip_sync_agent_approved_clips_unchanged(
        self, mock_load_config, mock_subprocess_run
    ):
        """lip_sync_agent must not modify the original approved_clips list."""
        mock_load_config.return_value = _mock_config()
        mock_subprocess_run.return_value = MagicMock(returncode=0)

        original = ["/workspace/shot_1.mp4"]
        state = _base_state(approved_clips=original.copy())

        result = lip_sync_agent(state)

        assert result["approved_clips"] == original


# ---------------------------------------------------------------------------
# compositor tests
# ---------------------------------------------------------------------------


def _setup_ffmpeg_mock(mock_ffmpeg):
    """Wire up the chain: ffmpeg.input -> concat -> output -> overwrite_output -> run."""
    mock_input = MagicMock()
    mock_ffmpeg.input.return_value = mock_input
    mock_concat = MagicMock()
    mock_ffmpeg.concat.return_value = mock_concat
    mock_output_node = MagicMock()
    mock_ffmpeg.output.return_value = mock_output_node
    mock_output_node.overwrite_output.return_value = mock_output_node
    mock_output_node.run.return_value = None
    return mock_output_node


class TestCompositor:
    @patch("src.agents.post_production.ffmpeg")
    def test_compositor_stitches_clips(self, mock_ffmpeg):
        """Happy path: compositor processes synced clips and sets final_video_path."""
        mock_output_node = _setup_ffmpeg_mock(mock_ffmpeg)

        clips = ["/workspace/sync_shot_1.mp4", "/workspace/sync_shot_2.mp4"]
        state = _base_state(approved_clips=clips)
        state["synced_clips"] = clips

        result = compositor(state)

        expected_path = os.path.join("/tmp/test_project", "final_output.mp4")
        assert result["final_video_path"] == expected_path  # type: ignore[typeddict-item]
        assert mock_ffmpeg.input.call_count == len(clips)
        mock_ffmpeg.concat.assert_called_once()
        mock_output_node.run.assert_called_once_with(quiet=True)

    @patch("src.agents.post_production.ffmpeg")
    def test_compositor_no_clips(self, mock_ffmpeg):
        """When both synced_clips and approved_clips are empty, final_video_path is None."""
        state = _base_state(approved_clips=[])
        state["synced_clips"] = []

        result = compositor(state)

        assert result["final_video_path"] is None  # type: ignore[typeddict-item]
        mock_ffmpeg.input.assert_not_called()

    @patch("src.agents.post_production.ffmpeg")
    def test_compositor_ffmpeg_error(self, mock_ffmpeg):
        """When ffmpeg.Error is raised, final_video_path is set to None (graceful degradation)."""
        mock_ffmpeg.input.return_value = MagicMock()
        mock_ffmpeg.concat.return_value = MagicMock()
        mock_output_node = MagicMock()
        mock_ffmpeg.output.return_value = mock_output_node
        mock_output_node.overwrite_output.return_value = mock_output_node

        # Build the ffmpeg.Error with a proper stderr bytes payload
        err = mock_ffmpeg.Error.return_value
        err.stderr = b"ffmpeg: No such file or directory"
        mock_output_node.run.side_effect = mock_ffmpeg.Error(
            "ffmpeg", "stdout", "stderr"
        )

        # Make ffmpeg.Error act like a real exception class in the except clause
        mock_ffmpeg.Error = type("ffmpeg.Error", (Exception,), {"stderr": b"error"})
        mock_output_node.run.side_effect = mock_ffmpeg.Error("ffmpeg error")

        clips = ["/workspace/sync_shot_1.mp4"]
        state = _base_state(approved_clips=clips)
        state["synced_clips"] = clips

        result = compositor(state)

        assert result["final_video_path"] is None  # type: ignore[typeddict-item]

    @patch("src.agents.post_production.ffmpeg")
    def test_compositor_falls_back_to_approved_clips(self, mock_ffmpeg):
        """When synced_clips is absent, compositor uses approved_clips instead."""
        _setup_ffmpeg_mock(mock_ffmpeg)

        # No synced_clips key in state
        state = _base_state(approved_clips=["/workspace/shot_1.mp4"])

        result = compositor(state)

        assert result["final_video_path"] is not None  # type: ignore[typeddict-item]
        mock_ffmpeg.input.assert_called_once_with("/workspace/shot_1.mp4")

    @patch("src.agents.post_production.ffmpeg")
    def test_compositor_sets_correct_output_path(self, mock_ffmpeg):
        """Output path is always <project_dir>/final_output.mp4."""
        _setup_ffmpeg_mock(mock_ffmpeg)

        state = _base_state(
            project_dir="./custom/project",
            approved_clips=["/workspace/sync_shot_1.mp4"],
        )
        state["synced_clips"] = ["/workspace/sync_shot_1.mp4"]  # type: ignore[typeddict-unknown-key]

        result = compositor(state)

        assert result["final_video_path"] == "./custom/project/final_output.mp4"  # type: ignore[typeddict-item]

    @patch("src.agents.post_production.ffmpeg")
    def test_compositor_calls_overwrite_output(self, mock_ffmpeg):
        """overwrite_output() must be called so re-runs don't stall on prompts."""
        mock_output_node = _setup_ffmpeg_mock(mock_ffmpeg)

        state = _base_state(approved_clips=["/workspace/sync_shot_1.mp4"])
        state["synced_clips"] = ["/workspace/sync_shot_1.mp4"]

        compositor(state)

        mock_output_node.overwrite_output.assert_called_once()
