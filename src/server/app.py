from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.pipeline.graph import AGENT_NODES
from src.server.runner import RunManager
from src.server.artifacts import discover, kind_for, safe_resolve, EDITABLE_EXTS


WEB_DIR = Path(__file__).parent / "web"


class CreateRunReq(BaseModel):
    project_name: str


class ResumeReq(BaseModel):
    state_patch: Optional[Dict[str, Any]] = None


class WriteFileReq(BaseModel):
    path: str
    content: str


class RegenerateReq(BaseModel):
    node: str
    state_patch: Optional[Dict[str, Any]] = None


def create_app(projects_dir: str = "./projects") -> FastAPI:
    api = FastAPI(title="AFP HITL Inspector")
    manager = RunManager(projects_dir)

    api.state.manager = manager

    @api.on_event("shutdown")
    async def _shutdown():
        await manager.shutdown()

    @api.get("/", response_class=HTMLResponse)
    async def index():
        return (WEB_DIR / "index.html").read_text(encoding="utf-8")

    api.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @api.get("/api/meta")
    async def meta():
        return {"agent_nodes": AGENT_NODES}

    @api.get("/api/projects")
    async def list_projects():
        root = Path(projects_dir)
        if not root.exists():
            return []
        return sorted(p.name for p in root.iterdir() if p.is_dir())

    @api.get("/api/runs")
    async def list_runs():
        return manager.list_runs()

    @api.post("/api/runs")
    async def create_run(req: CreateRunReq):
        run = await manager.create(req.project_name)
        await run.start()
        return {"run_id": run.run_id}

    @api.get("/api/runs/{run_id}")
    async def get_run(run_id: str):
        run = manager.get(run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        return await run.get_state_snapshot()

    @api.post("/api/runs/{run_id}/resume")
    async def resume_run(run_id: str, req: ResumeReq):
        run = manager.get(run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        await run.resume(req.state_patch)
        return {"ok": True}

    @api.post("/api/runs/{run_id}/regenerate")
    async def regenerate(run_id: str, req: RegenerateReq):
        run = manager.get(run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        if req.node not in AGENT_NODES:
            raise HTTPException(400, f"Unknown node: {req.node}")
        patch = dict(req.state_patch or {})
        if req.node == "production_designer":
            patch.setdefault("design_feedback", None)
            patch.setdefault("design_retry_count", 0)
        elif req.node == "cinematographer":
            patch.setdefault("storyboard_feedback", None)
            patch.setdefault("storyboard_retry_count", 0)
            patch.setdefault("current_keyframe_path", None)
            patch.setdefault("keyframe_retry_count", 0)
        elif req.node == "lead_animator":
            patch.setdefault("current_render_path", None)
            patch.setdefault("render_retry_count", 0)
            patch.setdefault("continuity_feedback", None)
        await run.resume(patch)
        return {"ok": True, "applied_patch_keys": list(patch.keys())}

    @api.get("/api/runs/{run_id}/artifacts")
    async def list_artifacts(run_id: str, node: Optional[str] = None):
        run = manager.get(run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        project_root = Path(projects_dir) / run.project_name
        return discover(project_root, node)

    @api.get("/api/runs/{run_id}/artifact")
    async def get_artifact(run_id: str, path: str):
        run = manager.get(run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        project_root = Path(projects_dir) / run.project_name
        try:
            target = safe_resolve(project_root, path)
        except PermissionError:
            raise HTTPException(403, "Path traversal denied")
        if not target.exists() or not target.is_file():
            raise HTTPException(404, "Artifact not found")
        return FileResponse(str(target))

    @api.get("/api/runs/{run_id}/artifact/text")
    async def get_artifact_text(run_id: str, path: str):
        run = manager.get(run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        project_root = Path(projects_dir) / run.project_name
        try:
            target = safe_resolve(project_root, path)
        except PermissionError:
            raise HTTPException(403, "Path traversal denied")
        if not target.exists() or not target.is_file():
            raise HTTPException(404, "Artifact not found")
        if target.suffix.lower() not in EDITABLE_EXTS:
            raise HTTPException(415, "Not a text artifact")
        return {
            "path": path,
            "kind": kind_for(target),
            "content": target.read_text(encoding="utf-8"),
        }

    @api.put("/api/runs/{run_id}/artifact/text")
    async def write_artifact_text(run_id: str, req: WriteFileReq):
        run = manager.get(run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        project_root = Path(projects_dir) / run.project_name
        try:
            target = safe_resolve(project_root, req.path)
        except PermissionError:
            raise HTTPException(403, "Path traversal denied")
        if target.suffix.lower() not in EDITABLE_EXTS:
            raise HTTPException(415, "Not editable")
        if target.exists() and target.is_dir():
            raise HTTPException(400, "Target is a directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(req.content, encoding="utf-8")
        return {"ok": True, "bytes": len(req.content)}

    @api.websocket("/api/ws/{run_id}")
    async def ws(websocket: WebSocket, run_id: str):
        run = manager.get(run_id)
        if not run:
            await websocket.close(code=4404)
            return
        await websocket.accept()
        q = run.subscribe()
        try:
            snap = await run.get_state_snapshot()
            await websocket.send_json({"type": "snapshot", "data": snap})
            while True:
                event = await q.get()
                await websocket.send_json(event)
        except WebSocketDisconnect:
            pass
        finally:
            run.unsubscribe(q)

    return api
