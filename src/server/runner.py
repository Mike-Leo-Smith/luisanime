import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from datetime import datetime

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.pipeline.graph import build_app, AGENT_NODES
from src.pipeline.state import AFCState, FinancialLedger
from src.pipeline.project import ProjectManager
from src.server.events import Event


RUNS_DIR = Path("runs")
RUNS_DIR.mkdir(exist_ok=True)
REGISTRY_PATH = RUNS_DIR / "registry.json"


def _load_registry() -> Dict[str, Dict[str, Any]]:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    return {}


def _save_registry(reg: Dict[str, Dict[str, Any]]) -> None:
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2))


class Run:
    def __init__(self, run_id: str, project_name: str, projects_dir: str):
        self.run_id = run_id
        self.project_name = project_name
        self.projects_dir = projects_dir
        self.subscribers: Set[asyncio.Queue] = set()
        self.task: Optional[asyncio.Task] = None
        self.status: str = "created"
        self.last_node: Optional[str] = None
        self.last_error: Optional[str] = None
        self._checkpointer_cm = None
        self._checkpointer = None
        self._app = None

    @property
    def db_path(self) -> Path:
        return RUNS_DIR / f"{self.run_id}.sqlite"

    @property
    def thread_id(self) -> str:
        return self.run_id

    async def _ensure_app(self):
        if self._app is not None:
            return
        self._checkpointer_cm = AsyncSqliteSaver.from_conn_string(str(self.db_path))
        self._checkpointer = await self._checkpointer_cm.__aenter__()
        self._app = build_app(
            checkpointer=self._checkpointer,
            interrupt_after=AGENT_NODES,
        )

    async def close(self):
        if self._checkpointer_cm is not None:
            await self._checkpointer_cm.__aexit__(None, None, None)
            self._checkpointer_cm = None
            self._checkpointer = None
            self._app = None

    async def broadcast(self, event: Event):
        dead = []
        for q in self.subscribers:
            try:
                q.put_nowait(event.model_dump())
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.subscribers.discard(q)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self.subscribers.discard(q)

    def _build_initial_state(self) -> AFCState:
        pm = ProjectManager(self.projects_dir)
        pm.load_project(self.project_name)
        novel_text = (
            pm.current_project / "01_source_material" / "novel.txt"
        ).read_text(encoding="utf-8")
        return AFCState(
            workspace_root=str(pm.current_project),
            project_config=pm.project_config,
            novel_text=novel_text,
            ledger=FinancialLedger(project_budget_usd=100.0, accumulated_cost_usd=0.0),
            unprocessed_scenes=[],
            current_scene_path=None,
            unprocessed_shots=[],
            active_shot_plan=None,
            current_proxy_path=None,
            current_keyframe_path=None,
            current_storyboard_path=None,
            current_render_path=None,
            scene_dailies_paths=[],
            completed_scenes_paths=[],
            keyframe_retry_count=0,
            render_retry_count=0,
            continuity_feedback=None,
            escalation_required=False,
            keyframe_is_reused_frame=False,
            design_feedback=None,
            design_retry_count=0,
            storyboard_feedback=None,
            storyboard_retry_count=0,
        )

    async def _drive(self, input_state: Optional[AFCState]):
        await self._ensure_app()
        config = {"configurable": {"thread_id": self.thread_id}}
        self.status = "running"
        await self.broadcast(Event(type="run_started", run_id=self.run_id))
        try:
            async for chunk in self._app.astream(
                input_state, config=config, stream_mode="updates"
            ):
                for node, _delta in chunk.items():
                    self.last_node = node
                    await self.broadcast(
                        Event(type="node_finished", run_id=self.run_id, node=node)
                    )
            snapshot = await self._app.aget_state(config)
            if snapshot.next:
                self.status = "paused"
                await self.broadcast(
                    Event(
                        type="run_paused",
                        run_id=self.run_id,
                        node=self.last_node,
                        payload={"next": list(snapshot.next)},
                    )
                )
            else:
                self.status = "completed"
                await self.broadcast(Event(type="run_completed", run_id=self.run_id))
        except Exception as e:
            self.status = "error"
            self.last_error = str(e)
            await self.broadcast(
                Event(
                    type="run_error",
                    run_id=self.run_id,
                    payload={"error": str(e)},
                )
            )

    async def start(self):
        if self.task and not self.task.done():
            raise RuntimeError("Run already in progress")
        initial = self._build_initial_state()
        self.task = asyncio.create_task(self._drive(initial))

    async def resume(self, state_patch: Optional[Dict[str, Any]] = None):
        if self.task and not self.task.done():
            raise RuntimeError("Run still in progress")
        await self._ensure_app()
        if state_patch:
            await self._app.aupdate_state(
                {"configurable": {"thread_id": self.thread_id}},
                state_patch,
            )
            await self.broadcast(
                Event(
                    type="run_resumed",
                    run_id=self.run_id,
                    payload={"patched": list(state_patch.keys())},
                )
            )
        self.task = asyncio.create_task(self._drive(None))

    async def get_state_snapshot(self) -> Dict[str, Any]:
        await self._ensure_app()
        snap = await self._app.aget_state(
            {"configurable": {"thread_id": self.thread_id}}
        )
        values = snap.values or {}
        return {
            "run_id": self.run_id,
            "project_name": self.project_name,
            "status": self.status,
            "last_node": self.last_node,
            "last_error": self.last_error,
            "next": list(snap.next) if snap.next else [],
            "values": _serialize_state(values),
        }


def _serialize_state(values: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in values.items():
        if hasattr(v, "model_dump"):
            out[k] = v.model_dump()
        elif isinstance(v, list):
            out[k] = [
                item.model_dump() if hasattr(item, "model_dump") else item for item in v
            ]
        else:
            try:
                json.dumps(v)
                out[k] = v
            except TypeError:
                out[k] = str(v)
    return out


class RunManager:
    def __init__(self, projects_dir: str = "./projects"):
        self.projects_dir = projects_dir
        self.runs: Dict[str, Run] = {}
        self.registry = _load_registry()

    def list_runs(self) -> List[Dict[str, Any]]:
        items = []
        for run_id, meta in self.registry.items():
            run = self.runs.get(run_id)
            items.append(
                {
                    **meta,
                    "status": run.status if run else meta.get("status", "idle"),
                    "last_node": run.last_node if run else None,
                }
            )
        return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)

    async def create(self, project_name: str) -> Run:
        run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        run = Run(run_id, project_name, self.projects_dir)
        self.runs[run_id] = run
        self.registry[run_id] = {
            "run_id": run_id,
            "project_name": project_name,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "status": "created",
        }
        _save_registry(self.registry)
        return run

    def get(self, run_id: str) -> Optional[Run]:
        run = self.runs.get(run_id)
        if run is not None:
            return run
        meta = self.registry.get(run_id)
        if not meta:
            return None
        run = Run(run_id, meta["project_name"], self.projects_dir)
        self.runs[run_id] = run
        return run

    async def shutdown(self):
        for run in list(self.runs.values()):
            if run.task and not run.task.done():
                run.task.cancel()
            await run.close()
