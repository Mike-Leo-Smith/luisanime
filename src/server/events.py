from typing import Any, Dict, Literal
from pydantic import BaseModel
from datetime import datetime


EventType = Literal[
    "run_started",
    "node_started",
    "node_finished",
    "run_paused",
    "run_resumed",
    "run_completed",
    "run_error",
]


class Event(BaseModel):
    type: EventType
    run_id: str
    ts: str = ""
    node: str | None = None
    payload: Dict[str, Any] = {}

    def model_post_init(self, _ctx) -> None:
        if not self.ts:
            self.ts = datetime.utcnow().isoformat() + "Z"
