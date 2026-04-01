# AFP Agent Development Guide

This document outlines the critical requirements, workflow patterns, skills, and lessons learned for developing agents in the Agentic Filming Pipeline (AFP).

## Critical Requirements

### 1. JSON Schema Enforcement

All agents that interact with LLMs must use structured output via JSON schemas:

```python
from src.agents.utils import get_llm_provider

def my_agent(state: PipelineState) -> PipelineState:
    provider = get_llm_provider(state, "agent_name")

    result = provider.generate_structured(
        prompt=prompt,
        response_schema=ENTITY_SCHEMA
    )
```

### 2. Provider Factory Pattern

Never instantiate providers directly. Always use the factory via base agent classes:

```python
from src.agents.base import BaseCreative

class MyAgent(BaseCreative):
    # self.llm, self.image_gen are initialized from config
    pass

agent = MyAgent.from_config(workspace, project_config)
```

Or via the factory directly:

```python
from src.providers.factory import ProviderFactory

llm = ProviderFactory.create_llm(agent_cfg)
image_gen = ProviderFactory.create_image(agent_cfg)
video_gen = ProviderFactory.create_video(agent_cfg)
```

### 3. Project Directory Structure

```
project/
├── 00_project_config/    # Configuration (read)
├── 01_source_material/   # Source novel (read)
├── 02_screenplays/       # Scene scripts (write)
├── 03_lore_bible/        # Character sheets, location designs (write)
│   └── designs/
│       └── locations/
├── 04_production_slate/  # Shot execution plans (write)
│   └── shots/
├── 05_dailies/           # Keyframes and video clips (write)
├── 06_logs/              # Logs and QA reports (write)
└── config.yaml
```

### 4. Progress Reporting

All long-running operations must report progress:

```python
def process_chapters(chapters):
    total = len(chapters)
    for i, chapter in enumerate(chapters, 1):
        progress = (i / total) * 100
        print(f"    [{i}/{total} {progress:.1f}%] Processing {chapter.id}...")
```

### 5. Error Handling

Agents must catch exceptions and set `state["last_error"]`:

```python
def my_agent(state: PipelineState) -> PipelineState:
    try:
        # ... agent logic
    except Exception as e:
        print(f"Error: {e}")
        state["last_error"] = str(e)
    return state
```

## Workflow Patterns

### Node Function Template

Each agent has a class (methods) and a node function (LangGraph entry point):

```python
from typing import Dict
from src.agents.base import BaseCreative
from src.pipeline.state import AFCState, ShotExecutionPlan


class MyAgent(BaseCreative):
    def do_work(self, plan: ShotExecutionPlan) -> str:
        # Agent logic here
        pass


def my_agent_node(state: AFCState) -> Dict:
    print(f"\n{'=' * 60}")
    print(f"🎯 [My Agent] === NODE ENTRY ===")
    plan = state.get("active_shot_plan")
    print(f"   active_shot_plan: {plan.shot_id if plan else None}")
    print(f"{'=' * 60}")

    from src.pipeline.workspace import AgenticWorkspace

    ws = AgenticWorkspace(state["workspace_root"])
    agent = MyAgent.from_config(ws, state["project_config"])

    if not plan:
        print(f"🎯 [My Agent] === NODE EXIT === No plan (no-op)")
        return {}

    try:
        result = agent.do_work(plan)
        print(f"🎯 [My Agent] === NODE EXIT === result={result}")
        return {"some_state_key": result}
    except Exception as e:
        print(f"🎯 [My Agent] Error: {e}")
        return {}
```

### Shot Continuation Handling

Agents that process shots must respect the `is_continuation` flag:

```python
plan = state.get("active_shot_plan")

if getattr(plan, "is_continuation", False):
    # This shot continues from the previous shot's motion
    # - Cinematographer: extract last frame instead of generating keyframe
    # - Continuity Supervisor: auto-pass (no QA needed)
    # - Lead Animator: use generate_video_continuation() with merged action
    pass
```

### Shot ID Format

Shot IDs follow `{scene_id}_SHOT_{index:03d}`:
- `scene_01_SHOT_001`, `scene_01_SHOT_002`, etc.
- Scene IDs: `scene_01`, `scene_02`, etc.
- Deterministically assigned by Director (overrides LLM output)

## Agent Skills

### Required Skills

1. **LLM Prompt Engineering** — Clear task descriptions, JSON output formatting
2. **Provider Abstraction** — Factory pattern, per-agent config
3. **Schema Design** — Gemini-compatible JSON schemas (uppercase types, no union types)
4. **Error Resilience** — Exception handling, graceful degradation

### Gemini Schema Rules

```python
# Standard JSON Schema (NOT supported)
{"type": ["string", "null"]}
{"patternProperties": {...}}

# Gemini-compatible format
{"type": "STRING", "nullable": True}
{"type": "ARRAY", "items": {...}}
```

## Lessons Learned

### 1. Shot Naming Consistency
Shot IDs must be deterministically assigned by the Director (`scene_01_SHOT_001` format), not rely on LLM output which may vary between runs.

### 2. Continuation vs New Shot
The Director marks `is_continuation=True` at planning time. The first shot of every scene is always `is_continuation=False`. Downstream agents check this flag rather than making their own continuation decisions.

### 3. No-Text Enforcement
All style presets include explicit no-text instructions: "No text, no subtitles, no dialogue bubbles, no captions, no watermarks." This is enforced in both keyframe and video generation prompts.

### 4. Character Clothing in Prompts
Both keyframe and video generation prompts include character appearance descriptions from the lore bible (`03_lore_bible/{entity_id}.md`) to maintain clothing consistency.

### 5. Mirror Reflection QA
The Continuity Supervisor is instructed to not flag laterally inverted details in mirror reflections as errors, since lateral inversion is physically correct.

### 6. Keyframe Versioning
Keyframes are versioned (`keyframe_v1.png`, `keyframe_v2.png`, `keyframe_v3.png`). The `render_retry_count` in state tracks which version we're on. If all 3 fail, best-of-N selection picks the least severe.

### 7. Location Reference Images
The Production Designer generates location reference images (`03_lore_bible/designs/locations/{name}.png`) which the Cinematographer includes as reference when generating keyframes.

### 8. Kling API Integration
- Video generation uses JWT auth (access_key + secret_key)
- `image_list` with `type: "first_frame"` for starting frame reference
- Prompt uses `<<<image_1>>>` token to reference the uploaded image
- `duration` of 5 or 10 seconds
- Async task creation → polling → download

### 9. Editor Scale/Pad
Resolution mismatches between shots are handled by the Editor via FFmpeg scale+pad filters rather than failing the assembly.

## Checklist for New Agents

- [ ] Create `src/agents/{agent_name}.py`
- [ ] Define agent class extending `BaseCreative`, `BaseQA`, `BaseExecutor`, or `BaseOrchestrator`
- [ ] Create node function (`{agent_name}_node(state: AFCState) -> Dict`)
- [ ] Add detailed logging with emoji prefix and NODE ENTRY/EXIT markers
- [ ] Handle `is_continuation` flag if processing shots
- [ ] Use `generate_structured()` for LLM calls with Gemini-compatible schemas
- [ ] Add progress reporting for loops
- [ ] Handle exceptions gracefully
- [ ] Register node in `src/pipeline/graph.py`
- [ ] Add agent config in `config.yaml.template`
- [ ] Update DESIGN.md with agent description

## Resources

- **State Definition:** `src/pipeline/state.py`
- **JSON Schemas:** `src/schemas.py`
- **Agent Base Classes:** `src/agents/base.py`
- **Provider Base:** `src/providers/base.py`
- **Workspace:** `src/pipeline/workspace.py`
- **Graph:** `src/pipeline/graph.py`
- **Config Template:** `config.yaml.template`
