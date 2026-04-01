# System Architecture Design Document: Agentic Filming Pipeline (AFP)

## 1. Executive Summary & Engineering Philosophy

The Agentic Filming Pipeline (AFP) is an end-to-end automated system designed to transcode long-form textual novels into broadcast-quality video sequences using an **Autonomous Film Crew (AFC)** architecture.

To mitigate the inherent flaws of current Video Diffusion Models (e.g., topological collapse, temporal inconsistency, physical hallucinations), the AFP is explicitly modeled after modern compiler infrastructures and physically-based rendering pipelines. It abstracts the unpredictable nature of generative AI behind strict state machines, Intermediate Representations (IR), and automated visual linters.

The system adheres to these engineering principles:
1. **Autonomous Film Crew**: Specialized AI agents collaborate via LangGraph, each with a specific production role
2. **Frontend/Backend Decoupling**: LLMs act as the "Compiler Frontend" to parse text and generate structured ASTs (Shot Lists). Video APIs act as the "Rasterization Backend."
3. **Defensive Generation via QA Linters**: Every generated keyframe passes through VLM inspection with retry loops, best-of-N fallback, and circuit breakers.
4. **Shot Continuation**: The Director pre-marks continuation shots at planning time. The pipeline reuses the last video frame as the starting keyframe, bypasses QA, and merges action descriptions for seamless transitions.
5. **Budget Management**: Built-in cost tracking with automatic production halt when budget is exceeded.
6. **Per-Agent Configuration**: Each agent has independent configuration for provider, model, API key, and parameters.
7. **No-Text Enforcement**: All generation prompts enforce zero on-screen text, subtitles, dialogue bubbles, or watermarks.

---

## 2. System Architecture: The Three Planes

### 2.1 Control Plane (LangGraph Orchestration)
* **Engine**: LangGraph with cyclic workflow graphs. Handles state transitions, conditional routing, and fault tolerance.
* **State Management**: TypedDict with annotation-based merging (`AFCState`).
* **Configuration**: Per-project `config.yaml` with agent-specific settings.

### 2.2 Generation Plane (Cloud API Backend)
* **LLM Inference**: Gemini 3.1 Pro for reasoning, JSON structured output, and vision analysis.
* **Image Generation**: Gemini 3.1 Flash Image Preview for keyframes, character designs, and location designs.
* **Video Generation**: Kling v3-omni via JWT-authenticated REST API with async task polling.
* **Provider Abstraction**: Unified interface for Gemini, Kling, and MiniMax.

### 2.3 Post-Processing Plane (Local CPU)
* **Scene Assembly**: Editor concatenates all shots per scene into preview videos.
* **Compositing**: FFmpeg for timeline assembly with scale/pad normalization for resolution mismatches.

---

## 3. Provider Abstraction Layer

### 3.1 Base Classes

```python
BaseLLMProvider      # Text generation, JSON structured output, vision (image/video) analysis
BaseImageProvider    # Image generation
BaseVideoProvider    # Video generation with async polling
```

### 3.2 Provider Implementations

| Provider | LLM | Image | Video | Authentication |
|----------|-----|-------|-------|----------------|
| **Gemini** | ✅ | ✅ | ❌ | API key |
| **Kling** | ❌ | ❌ | ✅ | JWT (access_key + secret_key) |
| **MiniMax** | ❌ | ❌ | ✅ | API key |

### 3.3 Provider Factory

```python
from src.providers.factory import ProviderFactory

llm_provider = ProviderFactory.create_llm(agent_cfg)
image_provider = ProviderFactory.create_image(agent_cfg)
video_provider = ProviderFactory.create_video(agent_cfg)
```

### 3.4 Kling Video Provider

The Kling provider uses JWT authentication:
- Generates JWT tokens from `access_key` and `secret_key`
- Creates video generation tasks via REST API
- Polls task status until completion
- Downloads and returns video bytes
- Supports `first_frame` image reference via `image_list` parameter with `<<<image_1>>>` prompt token

---

## 4. State Management & The AFCState

```python
class AFCState(TypedDict):
    workspace_root: str
    project_config: Dict[str, Any]
    ledger: FinancialLedger
    novel_text: str

    # Macro Queue (Scenes)
    unprocessed_scenes: List[str]
    current_scene_path: Optional[str]

    # Micro Queue (Shots)
    unprocessed_shots: List[ShotExecutionPlan]
    active_shot_plan: Optional[ShotExecutionPlan]

    # Media State (Active Shot)
    current_proxy_path: Optional[str]
    current_keyframe_path: Optional[str]
    current_render_path: Optional[str]

    # Asset Assembly
    scene_dailies_paths: List[str]
    completed_scenes_paths: List[str]

    # Feedback & Escalation
    previs_retry_count: int
    render_retry_count: int
    continuity_feedback: Optional[str]
    escalation_required: bool
```

### 4.1 ShotExecutionPlan

The core IR for shot generation:

```python
class ShotExecutionPlan(BaseModel):
    shot_id: str                          # e.g., "scene_01_SHOT_001"
    target_duration_ms: int
    camera_movement: str                  # High-level tag
    detailed_camera_plan: str             # Detailed movement instructions
    action_description: str
    active_entities: List[str]
    staging_description: str              # Character positions, environmental layout
    character_poses: Dict[str, str]       # entity_id → specific pose/expression
    setting_details: str                  # Period-accurate details, lighting cues
    era_context: str
    ending_composition_description: str   # For continuity linkage to next shot
    is_continuation: bool = False         # True if this shot continues from previous shot's motion
```

### 4.2 Shot ID Format

Shot IDs follow the pattern `{scene_id}_SHOT_{index:03d}`:
- `scene_01_SHOT_001`, `scene_01_SHOT_002`, etc.
- Deterministically assigned by the Director (overrides LLM output)
- Scene IDs are normalized to `scene_{n:02d}` by the Screenwriter

---

## 5. Project Structure

```
projects/{project_name}/
├── 00_project_config/
│   └── config.yaml
├── 01_source_material/
│   └── novel.txt
├── 02_screenplays/
│   ├── scene_01.json
│   ├── scene_02.json
│   └── scene_03.json
├── 03_lore_bible/
│   ├── master_style.md
│   ├── {entity_id}.md
│   └── designs/
│       ├── {entity_id}.png
│       ├── {entity_id}.png.prompt.txt
│       └── locations/
│           ├── {location_name}.png
│           └── {location_name}.png.prompt.txt
├── 04_production_slate/
│   └── shots/
│       ├── scene_01_SHOT_001.json
│       ├── scene_01_SHOT_002.json
│       └── ...
├── 05_dailies/
│   ├── scene_01_SHOT_001/
│   │   ├── keyframe_v1.png
│   │   ├── keyframe_v1.png.prompt.txt
│   │   ├── render.mp4
│   │   └── render.mp4.prompt.txt
│   ├── scene_01_SHOT_002/
│   │   ├── keyframe_v1.png           # For continuation shots: extracted last frame
│   │   ├── continuity/               # Reference frames from previous video
│   │   │   ├── ref_0.png
│   │   │   ├── ref_1.png
│   │   │   └── ref_2.png
│   │   └── render.mp4
│   └── scene_01_master.mp4           # Per-scene assembled preview
├── 06_logs/
│   ├── generation_prompts.log
│   └── qa_reports.log
└── config.yaml
```

---

## 6. Agent Topology & Workflow (LangGraph)

### 6.1 Agent Registry

| Node | Agent Class | Type | Providers |
|------|-------------|------|-----------|
| `screenwriter` | ScreenwriterAgent | Creative | Gemini LLM |
| `showrunner` | ShowrunnerAgent | Orchestrator | Gemini LLM |
| `director` | DirectorAgent | Creative | Gemini LLM |
| `script_coordinator` | ScriptCoordinatorAgent | Support | Gemini LLM |
| `production_designer` | ProductionDesignerAgent | Creative | Gemini LLM + Image |
| `cinematographer` | CinematographerAgent | Creative | Gemini LLM + Image |
| `continuity_supervisor` | ContinuitySupervisorAgent | QA | Gemini LLM (Vision) |
| `lead_animator` | LeadAnimatorAgent | Creative | Gemini LLM + Kling Video |
| `editor` | EditorAgent | Support | FFmpeg |

### 6.2 Graph Topology

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
                    ▼                                         │
START → Screenwriter → Showrunner ────────► Director ─────────┘
                         │                    │
                         │ (no scenes)        ▼
                         ▼              Script Coordinator
                        END                   │
                              ┌───────────────┴───────────────┐
                              │ (shots remaining)             │ (scene done)
                              ▼                               ▼
                    Production Designer                    Editor
                              │                               │
                              ▼                               │
                     Cinematographer ◄────────────────────┐   │
                              │                           │   │
                              ▼                           │   │
                  Continuity Supervisor                   │   │
                              │                           │   │
                    ┌─────────┴─────────┐                 │   │
                    │ (fail, retry < 3) │ (pass or 3×)    │   │
                    ▼                   ▼                  │   │
              Cinematographer     Lead Animator            │   │
                (retry)                 │                  │   │
                                        ▼                  │   │
                              Continuity Supervisor        │   │
                                        │                  │   │
                                        ▼ (shot done)     │   │
                              Script Coordinator ──────────┘   │
                                        │ (scene done)         │
                                        ▼                      │
                                     Showrunner ◄──────────────┘
```

### 6.3 Shot Continuation Flow

When `plan.is_continuation == True`:

```
Cinematographer:
  → Extract last frame from dailies[-1] at 95% duration → keyframe_v1.png
  → Skip normal keyframe generation

Continuity Supervisor:
  → Auto-PASS (log "AUTO-PASS (continuation shot)")
  → No VLM call needed

Lead Animator:
  → Load previous shot plan
  → Merge action: prev.ending_composition_description + current.action_description
  → Extract last frame from previous video
  → Call generate_video_continuation() with first_frame reference
```

### 6.4 Keyframe QA & Best-of-N Fallback

1. Cinematographer generates `keyframe_v1.png`
2. Continuity Supervisor runs VLM check
3. If FAIL and retries < 3: regenerate with feedback → `keyframe_v2.png`, `keyframe_v3.png`
4. If all 3 attempts fail: Continuity Supervisor compares all versions via LLM and selects the least severe
5. Pipeline proceeds with the best candidate

---

## 7. Configuration System

### 7.1 Model Definitions

```yaml
models:
  gemini-flash:
    provider: "gemini"
    model: "gemini-3.1-pro-preview"
    api_key: "ENV:GEMINI_FLASH_API_KEY"
    temperature: 0.2

  gemini-pro:
    provider: "gemini"
    model: "gemini-3.1-pro-preview"
    api_key: "ENV:GEMINI_PRO_API_KEY"
    temperature: 0.2

  gemini-image:
    provider: "gemini"
    model: "gemini-3.1-flash-image-preview"
    api_key: "ENV:GEMINI_FLASH_API_KEY"

  kling-video:
    provider: "kling"
    model: "kling-v3-omni"
    api_key: "ENV:KLING_ACCESS_KEY"
    secret_key: "ENV:KLING_SECRET_KEY"
```

### 7.2 Per-Agent Configuration

```yaml
agents:
  showrunner:
    llm: gemini-flash
  screenwriter:
    llm: gemini-flash
  production_designer:
    llm: gemini-flash
    image: gemini-image
  director:
    llm: gemini-flash
  script_coordinator:
    llm: gemini-flash
  cinematographer:
    llm: gemini-flash
    image: gemini-image
  lead_animator:
    llm: gemini-flash
    video: kling-video
  continuity_supervisor:
    llm: gemini-pro
  editor:
    llm: gemini-flash
```

### 7.3 Style Presets

Both presets enforce no-text generation:

```yaml
style_presets:
  anime:
    prompt_prefix: "Studio Ghibli 2D manga style, hand-drawn aesthetic..."
    prompt_suffix: "...No text, no subtitles, no dialogue bubbles, no captions, no watermarks."
  cinematic:
    prompt_prefix: "Cinematic 35mm film style, photorealistic, highly detailed."
    prompt_suffix: "...No text, no subtitles, no dialogue bubbles, no captions, no watermarks."
```

---

## 8. Technology Stack

| Component | Role | Technology | Rationale |
|-----------|------|------------|-----------|
| **Orchestration** | Workflow | **LangGraph** | Cyclic graphs, conditional routing, state management |
| **Frontend LLM** | All agents | **Gemini 3.1 Pro** | Fast structured output, vision analysis |
| **Vision QA** | Continuity Supervisor | **Gemini 3.1 Pro** | Image analysis for keyframe quality |
| **Image API** | Cinematographer, Production Designer | **Gemini 3.1 Flash Image Preview** | Integrated with LLM for consistent outputs |
| **Video API** | Lead Animator | **Kling v3-omni** | High-quality video generation with first-frame control |
| **Compositing** | Editor | **FFmpeg** | Local video assembly with scale/pad normalization |

---

## 9. Engineering Caveats & Constraints

### 9.1 Circuit Breaker

If keyframe QA fails 3 times, the Continuity Supervisor selects the best-of-N candidate rather than escalating. Video QA is currently auto-passed to save API costs.

### 9.2 Budget Enforcement

The Showrunner audits costs before each scene. Production halts when `accumulated_cost_usd >= project_budget_usd`.

### 9.3 Cinematic Continuity

The Director maintains continuity through:
- `ending_composition_description`: describes the expected final frame of each shot
- `is_continuation`: marks shots where the previous shot's motion should seamlessly flow into the current shot
- Shot N+1's staging references Shot N's ending composition

### 9.4 Mirror Reflection Handling

The Continuity Supervisor is instructed to not flag laterally inverted details in mirror reflections as inconsistencies, since lateral inversion is physically correct.

### 9.5 Character Clothing Consistency

Both keyframe and video generation prompts include character appearance descriptions (extracted from lore bible) to maintain clothing and appearance consistency across shots.

---

## 10. CLI Interface

```bash
# Create a new project
python main.py create my_project novel.txt --style cinematic --max-shots 20

# Run the autonomous pipeline
python main.py run my_project

# Check status
python main.py status my_project
```

---

## 11. Key Files

**Configuration:**
- `config.yaml.template` — Template with model definitions and agent references
- `src/config.py` — ConfigLoader with hierarchical config merging

**Providers:**
- `src/providers/base.py` — Base provider interfaces
- `src/providers/gemini.py` — Gemini LLM + Image provider
- `src/providers/kling.py` — Kling Video provider (JWT auth, task polling)
- `src/providers/minimax.py` — MiniMax Video provider
- `src/providers/factory.py` — ProviderFactory

**Pipeline:**
- `src/pipeline/graph.py` — LangGraph workflow with routing functions
- `src/pipeline/state.py` — AFCState and ShotExecutionPlan definitions
- `src/pipeline/workspace.py` — AgenticWorkspace for file I/O
- `src/pipeline/project.py` — Project management

**Agents:**
- `src/agents/base.py` — BaseCreative, BaseOrchestrator, BaseQA, BaseExecutor
- `src/agents/screenwriter.py` — Novel → scene parsing with scene_id normalization
- `src/agents/director.py` — Scene → shot planning with is_continuation marking
- `src/agents/production_designer.py` — Master style, character designs, location designs
- `src/agents/cinematographer.py` — Keyframe generation with continuation frame extraction
- `src/agents/continuity_supervisor.py` — VLM QA with auto-pass for continuation shots
- `src/agents/lead_animator.py` — Video generation with continuation mode
- `src/agents/editor.py` — Per-scene video assembly
- `src/agents/prompts.py` — System prompts for agents

**Entry Point:**
- `main.py` — CLI (create, run, status)
