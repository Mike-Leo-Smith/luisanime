from pydantic import BaseModel, Field
from typing import List, Optional


class MediaPipeValidationReport(BaseModel):
    status: str = Field(description="Enum: PASS, FAIL_ANATOMY")
    anomaly_frame_index: Optional[int] = Field(
        None,
        description="The exact frame number where the topological collapse or failure occurred.",
    )
    bone_length_variance: Optional[float] = Field(
        None,
        description="The maximum detected percentage change in bone length (must remain < 5%).",
    )
    finger_count_max: Optional[int] = Field(
        None,
        description="The maximum number of distinct distal phalanges detected (must be <= 5 per hand).",
    )
    rigid_prop_curvature: Optional[float] = Field(
        None, description="Degree of deviation from the Hough Line Transform vector."
    )


class FFMPEGTimelineTrack(BaseModel):
    source_path: str
    start_time_ms: int
    end_time_ms: int
    clip_id: str


class FFMPEGAudioTrack(BaseModel):
    source_path: str
    insert_time_ms: int
    volume_db: float


class FFMPEGTimelineJSON(BaseModel):
    timeline_id: str
    resolution: dict = Field(
        description="Specifies width and height based on the global project configuration."
    )
    video_tracks: List[FFMPEGTimelineTrack]
    audio_tracks: List[FFMPEGAudioTrack]
    transitions: List[dict] = Field(
        default_factory=list,
        description="Defines cross-fades or hard cuts between sequential clip_ids.",
    )
