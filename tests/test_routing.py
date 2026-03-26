import pytest
from src.core.state import PipelineState, Shot
from src.core.graph import route_qa


def test_route_qa_to_next_shot():
    # Shot 1 of 2 is approved
    state: PipelineState = {
        "shot_list": [
            Shot(
                id="s1",
                scene_id="sc1",
                prompt="...",
                camera_movement="...",
                duration=3.0,
                status="approved",
            ),
            Shot(
                id="s2",
                scene_id="sc1",
                prompt="...",
                camera_movement="...",
                duration=3.0,
                status="pending",
            ),
        ],
        "current_shot_index": 0,
        "retry_count": 0,
    }

    # We expect it to go to storyboarder for the next shot
    # Note: The actual increment of current_shot_index might happen in a node or the router.
    # In LangGraph, it's often cleaner to do it in a node before the router or in the router itself.
    # Let's see how we want to handle it.
    next_node = route_qa(state)
    assert next_node == "advance_shot"


def test_route_qa_to_lip_sync():
    # Last shot is approved
    state: PipelineState = {
        "shot_list": [
            Shot(
                id="s1",
                scene_id="sc1",
                prompt="...",
                camera_movement="...",
                duration=3.0,
                status="approved",
            )
        ],
        "current_shot_index": 0,
        "retry_count": 0,
    }

    next_node = route_qa(state)
    assert next_node == "lip_sync"


def test_route_qa_to_retry_animator():
    # Shot failed but we have retries left
    state: PipelineState = {
        "shot_list": [
            Shot(
                id="s1",
                scene_id="sc1",
                prompt="...",
                camera_movement="...",
                duration=3.0,
                status="qa_failed",
            )
        ],
        "current_shot_index": 0,
        "retry_count": 1,  # Assume max_retries is 3
    }

    next_node = route_qa(state)
    assert next_node == "animator"


def test_route_qa_to_fallback_director():
    # Shot failed and we exhausted retries
    # From config.yaml, max_retries_per_shot is 3
    state: PipelineState = {
        "shot_list": [
            Shot(
                id="s1",
                scene_id="sc1",
                prompt="...",
                camera_movement="...",
                duration=3.0,
                status="qa_failed",
            )
        ],
        "current_shot_index": 0,
        "retry_count": 3,
    }

    next_node = route_qa(state)
    assert next_node == "director"
