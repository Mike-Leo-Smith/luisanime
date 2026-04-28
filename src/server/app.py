from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.pipeline.graph import AGENT_NODES
from src.server.runner import RunManager
from src.server.artifacts import discover, kind_for, safe_resolve, EDITABLE_EXTS
from src.server import admin as admin_mod


WEB_DIR = Path(__file__).parent / "web"
ROOT_DIR = Path(__file__).resolve().parents[2]


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


class EnvWriteReq(BaseModel):
    items: List[Dict[str, Any]]


class ConfigWriteReq(BaseModel):
    data: Optional[Dict[str, Any]] = None
    raw: Optional[str] = None


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

    @api.get("/api/graph")
    async def graph_topology():
        from src.pipeline.graph import workflow

        compiled = workflow.compile()
        g = compiled.get_graph()

        roles = {
            "screenwriter": ("Screenwriter", "creative"),
            "showrunner": ("Showrunner", "orchestrator"),
            "director": ("Director", "creative"),
            "script_coordinator": ("Script Coordinator", "support"),
            "production_designer": ("Production Designer", "creative"),
            "design_qa": ("Design QA", "qa"),
            "cinematographer": ("Cinematographer", "creative"),
            "storyboard_qa": ("Storyboard QA", "qa"),
            "continuity_supervisor": ("Continuity Supervisor", "qa"),
            "lead_animator": ("Lead Animator", "creative"),
            "editor": ("Editor", "support"),
        }

        edge_labels = {
            ("showrunner", "director"): "scenes remain",
            ("showrunner", "__end__"): "done / escalation",
            ("script_coordinator", "production_designer"): "more shots",
            ("script_coordinator", "editor"): "scene complete",
            ("design_qa", "cinematographer"): "approved",
            ("design_qa", "production_designer"): "rejected (retry)",
            ("storyboard_qa", "continuity_supervisor"): "approved + keyframe",
            ("storyboard_qa", "cinematographer"): "rejected / need keyframe",
            ("continuity_supervisor", "lead_animator"): "keyframe ok / re-render",
            ("continuity_supervisor", "script_coordinator"): "render approved",
            ("continuity_supervisor", "cinematographer"): "keyframe rejected",
            ("continuity_supervisor", "director"): "circuit breaker",
        }

        nodes = []
        for nid in g.nodes.keys():
            label, role = roles.get(nid, (nid, "system"))
            if nid == "__start__":
                label, role = "START", "terminal"
            elif nid == "__end__":
                label, role = "END", "terminal"
            nodes.append({"id": nid, "label": label, "role": role})

        edges = []
        for e in g.edges:
            edges.append({
                "source": e.source,
                "target": e.target,
                "conditional": bool(e.conditional),
                "label": edge_labels.get((e.source, e.target), ""),
            })

        return {"nodes": nodes, "edges": edges}

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

    @api.get("/api/admin/env")
    async def admin_env_get():
        env_path = ROOT_DIR / ".env"
        return {"path": str(env_path), "items": admin_mod.parse_env_file(env_path)}

    @api.put("/api/admin/env")
    async def admin_env_put(req: EnvWriteReq):
        env_path = ROOT_DIR / ".env"
        existing = admin_mod.parse_env_file(env_path, reveal=True)
        admin_mod.write_env_file(env_path, req.items, existing)
        return {"ok": True, "count": len(req.items)}

    @api.get("/api/admin/config")
    async def admin_config_get(project: Optional[str] = None):
        if project:
            cfg_path = Path(projects_dir) / project / "config.yaml"
            if not cfg_path.exists():
                raise HTTPException(404, f"No config.yaml for project '{project}'")
        else:
            cfg_path = ROOT_DIR / "config.yaml"
            if not cfg_path.exists():
                tmpl = ROOT_DIR / "config.yaml.template"
                if tmpl.exists():
                    cfg_path = tmpl
        data, raw = admin_mod.load_config_file(cfg_path)
        return {
            "path": str(cfg_path),
            "exists": cfg_path.exists(),
            "raw": raw,
            "data": admin_mod.mask_config_secrets(data),
            "agent_nodes": AGENT_NODES,
        }

    @api.put("/api/admin/config")
    async def admin_config_put(req: ConfigWriteReq, project: Optional[str] = None):
        if project:
            cfg_path = Path(projects_dir) / project / "config.yaml"
        else:
            cfg_path = ROOT_DIR / "config.yaml"
        if req.raw is not None:
            try:
                admin_mod.save_config_raw(cfg_path, req.raw)
            except yaml.YAMLError as e:
                raise HTTPException(400, f"Invalid YAML: {e}")
            return {"ok": True, "mode": "raw", "path": str(cfg_path)}
        if req.data is None:
            raise HTTPException(400, "Provide either 'raw' or 'data'")
        old, _ = admin_mod.load_config_file(cfg_path)
        merged = admin_mod.unmask_config(req.data, old)
        admin_mod.save_config_file(cfg_path, merged)
        return {"ok": True, "mode": "data", "path": str(cfg_path)}

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
