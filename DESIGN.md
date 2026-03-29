# System Architecture Design Document: Agentic Filming Pipeline (AFP)

## 1. Executive Summary & Engineering Philosophy

The Agentic Filming Pipeline (AFP) is an end-to-end, automated system designed to transcode long-form textual novels into broadcast-quality animated video sequences using an **Autonomous Film Crew (AFC)** architecture.

To mitigate the inherent flaws of current Video Diffusion Models (e.g., topological collapse, temporal inconsistency, physical hallucinations), the AFP is explicitly modeled after modern compiler infrastructures and physically-based rendering pipelines. It abstracts the unpredictable nature of generative AI behind strict state machines, Intermediate Representations (IR), and automated visual linters.

The system adheres to six engineering principles:
1. **Autonomous Film Crew**: Specialized AI agents collaborate via LangGraph, each with a specific production role
2. **Frontend/Backend Decoupling**: LLMs act as the "Compiler Frontend" to parse text and generate structured ASTs (Shot Lists). Video APIs act as the "Rasterization Backend."
3. **Defensive Generation via QA Linters**: No video clip is accepted blindly. Every generated sequence passes through Vision-Language Model (VLM) inspection with retry loops and circuit breakers.
4. **Budget Management**: Built-in cost tracking with automatic production halt when budget is exceeded.
5. **Per-Agent Configuration**: Each agent has independent configuration for provider, model, API key, and parameters.
6. **Scene-Based Continuity**: Cinematic continuity is maintained through explicit shot-to-shot linkage in the Director's shot plans.

---

## 2. System Architecture: The Three Planes

The system is partitioned into three distinct operational planes orchestrated by a LangGraph runtime environment.

### 2.1 Control Plane (LangGraph Orchestration)
* **Engine**: LangGraph with cyclic workflow graphs. Handles state transitions, conditional routing, and fault tolerance.
* **State Management**: TypedDict with annotation-based merging (`AFCState`).
* **Configuration**: Per-project `config.yaml` with agent-specific settings.
* **Role**: The central bus. Routes data between agents via conditional edges and manages the macro/micro production loops.

### 2.2 Generation Plane (Cloud API Backend)
* **LLM Inference**: Top-tier reasoning models for high-fidelity logic, spatial decomposition, and JSON compliance.
* **Image/Video APIs**: Commercial endpoints for pixel rasterization.
* **Provider Abstraction**: Unified interface for Gemini (LLM + Image) and MiniMax (Video).
* **Role**: Heavy compute execution. Subject to strict budget control and circuit breakers.

### 2.3 Post-Processing Plane (Local CPU/GPU)
* **Asset Assembly**: Local Python scripts for scene assembly and final output generation.
* **Compositing**: FFmpeg for timeline assembly and audio multiplexing.

---

## 3. Provider Abstraction Layer

The system uses a provider abstraction layer to support multiple AI service backends without coupling to specific APIs.

### 3.1 Base Classes

```python
# Base provider interfaces
BaseLLMProvider      - Text generation and JSON structured output
BaseImageProvider    - Image generation
BaseVideoProvider    - Video generation with polling
```

### 3.2 Provider Implementations

| Provider | LLM | Image | Video | Configuration |
|----------|-----|-------|-------|---------------|
| **Gemini** | ✅ | ✅ | ❌ | `model`, `image_model`, `api_key` |
| **MiniMax** | ❌ | ❌ | ✅ | `video_model`, `api_key` |

### 3.3 Provider Factory

Providers are instantiated via `ProviderFactory` which reads configuration and creates the appropriate provider:

```python
from src.providers.factory import ProviderFactory
from src.config import load_config, ConfigLoader

config = load_config()
agent_cfg = ConfigLoader.get_agent_config(config, "cinematographer")

llm_provider = ProviderFactory.create_llm(agent_cfg)
image_provider = ProviderFactory.create_image(agent_cfg)
video_provider = ProviderFactory.create_video(agent_cfg)
```

---

## 4. State Management & The AFCState

The pipeline uses a centralized state object (`AFCState`) that all agents read from and write to:

```python
class AFCState(TypedDict):
    workspace_root: str
    project_config: Dict[str, Any]
    ledger: FinancialLedger           # Budget tracking
    novel_text: str
    
    # Macro Queue (Scenes)
    unprocessed_scenes: List[str]     # Scene file paths
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
    shot_id: str
    target_duration_ms: int
    camera_movement: str
    detailed_camera_plan: str
    action_description: str
    active_entities: List[str]
    staging_description: str
    character_poses: Dict[str, str]
    setting_details: str
    era_context: str
    ending_composition_description: str  # For continuity
```

### 4.2 Budget Management

Each agent call tracks costs in the `FinancialLedger`:

```python
class FinancialLedger(BaseModel):
    project_budget_usd: float = 100.0
    accumulated_cost_usd: float = 0.0
```

The Showrunner audits costs and halts production if the budget is exceeded.

---

## 5. Project Structure & Asset Organization

### 5.1 Project Layout

```
projects/{project_name}/
├── 00_project_config/         # Configuration
│   └── config.yaml
├── 01_source_material/        # Source novel
│   └── novel.txt
├── 02_screenplays/            # Scene scripts (JSON)
│   └── scene_001.json
│   └── scene_002.json
├── 03_lore_bible/             # Character sheets, style guides
│   └── master_style.md
├── 04_production_slate/       # Shot plans and keyframes
│   └── shots/
│       ├── S1_SHOT_001.json
│       ├── S1_SHOT_002.json
│       └── keyframes/
├── 05_dailies/                # Generated video clips
│   └── scene_001/
│       └── S1_SHOT_001.mp4
├── 06_logs/                   # Production logs
└── config.yaml                # Legacy config
```

### 5.2 Project Manager

The `ProjectManager` handles asset paths and organization:

```python
from src.pipeline.project import ProjectManager

pm = ProjectManager("./projects")
pm.create_project("my_project", novel_text, config)
pm.load_project("my_project")

# Access paths
novel_path = pm.get_path("01_source_material", "novel.txt")
config_path = pm.get_path("00_project_config", "config.yaml")
```

---

## 6. Agent Topology & Workflow (LangGraph)

The pipeline uses a LangGraph state machine with 9 specialized agents:

### 6.1 Agent Registry

| Node | Agent Class | Type | Description |
|------|-------------|------|-------------|
| `screenwriter` | ScreenwriterAgent | Creative | Parses novel into structured scenes |
| `showrunner` | ShowrunnerAgent | Orchestrator | Routes workflow, audits budget |
| `director` | DirectorAgent | Creative | Generates shot plans with continuity |
| `script_coordinator` | ScriptCoordinatorAgent | Support | Manages shot queue |
| `production_designer` | ProductionDesignerAgent | Creative | Establishes visual style |
| `cinematographer` | CinematographerAgent | Creative | Generates keyframes |
| `continuity_supervisor` | ContinuitySupervisorAgent | QA | VLM-based quality assurance |
| `lead_animator` | LeadAnimatorAgent | Creative | Generates video from keyframes |
| `editor` | EditorAgent | Support | Assembles final video |

### 6.2 Graph Topology

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
                    ▼                                         │
START → Screenwriter → Showrunner ────────► Director ─────────┘
                         │                    │
                         │ (no scenes)        │ (escalation)
                         ▼                    ▼
                        END              Script Coordinator
                                                  │
                              ┌───────────────────┴───────────────────┐
                              │ (shots remaining)                     │ (no shots)
                              ▼                                       ▼
                    Production Designer ────────► Cinematographer ───► Editor
                                                           │           │
                                                           ▼           │
                                              Continuity Supervisor    │
                                                           │           │
                              ┌────────────────────────────┴────┐      │
                              │ (fail)                          │ (pass)
                              ▼                                 ▼      │
                    Cinematographer (retry)          Lead Animator    │
                                                           │           │
                                                           ▼           │
                                              Continuity Supervisor    │
                                                           │           │
                    ┌───────────────────────────────────────┼───┐      │
                    │ (fail, retries < 3)                   │   │ (pass)
                    ▼                                       │   ▼      │
          Lead Animator (retry)                    Script Coordinator◄──┘
                    │                                       │
                    │ (fail, retries >= 3)                  │ (scene done)
                    ▼                                       ▼
          Director (escalation)                    Showrunner (next scene)
```

### 6.3 Routing Functions

The graph uses conditional edges for routing:

```python
def route_macro_loop(state: AFCState) -> Literal["director", "__end__"]:
    """Showrunner routes the macro loop."""
    if state.get("unprocessed_scenes") and not state.get("escalation_required"):
        return "director"
    return "__end__"

def route_after_animator_qa(state: AFCState) -> Literal["script_coordinator", "lead_animator", "director"]:
    """QA evaluates Final Render fidelity."""
    if state.get("continuity_feedback"):
        if state.get("render_retry_count", 0) >= 3:
            return "director"  # Circuit breaker
        return "lead_animator"  # Retry
    return "script_coordinator"  # Pass
```

---

## 7. Configuration System

### 7.1 Per-Agent Configuration

Each agent has its own configuration section with provider-specific settings:

```yaml
agents:
  showrunner:
    llm: gemini-flash
  director:
    llm: gemini-flash
  production_designer:
    llm: gemini-flash
    image: gemini-image
  cinematographer:
    llm: gemini-flash
    image: gemini-image
  lead_animator:
    llm: gemini-flash
    video: minimax-video
  continuity_supervisor:
    llm: gemini-pro
```

### 7.2 Model Definitions

Models are defined in the `models` section and referenced by agents:

```yaml
models:
  gemini-flash:
    provider: "gemini"
    model: "gemini-3.1-flash-lite-preview"
    api_key: "ENV:GEMINI_FLASH_API_KEY"
    temperature: 0.2

  gemini-pro:
    provider: "gemini"
    model: "gemini-3.1-pro-preview"
    api_key: "ENV:GEMINI_PRO_API_KEY"
    temperature: 0.2

  gemini-image:
    provider: "gemini"
    model: "nano-banana-pro-preview"
    api_key: "ENV:GEMINI_FLASH_API_KEY"

  minimax-video:
    provider: "minimax"
    model: "MiniMax-Hailuo-2.3"
    api_key: "ENV:MINIMAX_VIDEO_API_KEY"
```

### 7.3 Configuration Loading

```python
from src.config import load_config, ConfigLoader

# Load with hierarchical merging
config = load_config(project_path="./projects/my_project")

# Get merged agent config
agent_cfg = ConfigLoader.get_agent_config(config, "director")
```

### 7.4 Environment Variables

API keys are specified via environment variables:

```bash
export GEMINI_FLASH_API_KEY="your_gemini_key"
export GEMINI_PRO_API_KEY="your_gemini_key"
export MINIMAX_VIDEO_API_KEY="your_minimax_key"
```

---

## 8. Technology Stack & Model Selection

| Component | Role | Models | Rationale |
| :--- | :--- | :--- | :--- |
| **Orchestration** | Workflow | **LangGraph** | Cyclic graphs, conditional routing, state management |
| **Frontend LLM** | Screenwriter, Director, Showrunner | **Gemini 3.1 Flash** | Fast, cost-effective for high-token operations |
| **Vision QA** | Continuity Supervisor | **Gemini 3.1 Pro** | Top Vision Arena performance for quality checks |
| **Image API** | Cinematographer | **Gemini Image** | Integrated with LLM for consistent outputs |
| **Video API** | Lead Animator | **MiniMax Hailuo-2.3** | Cost-effective video generation |

---

## 9. Crucial Engineering Caveats & Constraints

### 9.1 The Circuit Breaker Pattern

Video APIs are expensive. The LangGraph state strictly enforces the `max_retries_per_shot` counter. If the threshold is reached, the system automatically routes back to the Director to heavily degrade the physical action prompt.

```python
if state.get("render_retry_count", 0) >= 3:
    print("🚨 [CIRCUIT BREAKER] Escalate to Director")
    return "director"
```

### 9.2 Budget Enforcement

The Showrunner audits costs after each agent invocation:

```python
def audit_ledger(self, state: AFCState) -> bool:
    ledger = state.get("ledger")
    if ledger.accumulated_cost_usd >= ledger.project_budget_usd:
        return False
    return True
```

### 9.3 Cinematic Continuity

The Director maintains continuity through explicit `ending_composition_description` fields that link shots together:

```json
{
  "shot_id": "S1_SHOT_001",
  "ending_composition_description": "Character A stands at the temple gate, facing camera, right hand raised",
  "staging_description": "Character A at temple gate, camera at eye level"
}
```

Shot N+1's staging must match Shot N's ending composition.

### 9.4 Model Version Compatibility

Different providers update models frequently. Pin model versions in production configs to ensure consistent output quality.

### 9.5 Rate Limiting & Cost Management

Implement exponential backoff for API calls. Use separate API keys for different agents to isolate quota limits and track costs per agent.

---

## 10. CLI Interface

### 10.1 Basic Usage

```bash
# Create a new project
python main.py create my_video_project novel.txt --style anime --max-shots 10

# Run the autonomous pipeline
python main.py run my_video_project

# Check status
python main.py status my_video_project
```

### 10.2 CLI Arguments

**create**:
- `name` - Project name
- `input` - Path to novel text file
- `--style` - Visual style (anime, cinematic)
- `--resolution` - Output resolution (1080p, 720p, 360p)
- `--fps` - Frame rate (default: 24)
- `--max-shots` - Maximum shots to generate (default: 10)
- `--chapters` - Comma-separated chapter numbers to process

**run**:
- `name` - Project name
- `--stage` - Start from specific stage (not yet implemented)
- `--shot-index` - Start from specific shot index (not yet implemented)

**status**:
- `name` - Project name

### 10.3 Agent Files

Each agent is in its own file for modularity:

```
src/agents/
├── base.py                    # Base agent classes
├── showrunner.py              # Workflow orchestration
├── screenwriter.py            # Novel parsing
├── director.py                # Shot planning
├── production_designer.py     # Visual style
├── cinematographer.py         # Keyframe generation
├── lead_animator.py           # Video generation
├── continuity_supervisor.py   # QA
├── script_coordinator.py      # Shot queue management
├── editor.py                  # Final assembly
├── previs_artist.py           # Pre-visualization (legacy)
├── prompts.py                 # System prompts
└── utils.py                   # Shared utilities
```

---

## 11. Key Files

**Configuration:**
- `config.yaml.template` - Template with defaults
- `src/config.py` - ConfigLoader implementation

**Providers:**
- `src/providers/base.py` - Base provider classes
- `src/providers/gemini.py` - Gemini provider
- `src/providers/minimax.py` - MiniMax provider
- `src/providers/openai_compat.py` - OpenAI-compatible provider
- `src/providers/factory.py` - ProviderFactory

**Pipeline:**
- `src/pipeline/project.py` - Project management
- `src/pipeline/graph.py` - LangGraph workflow
- `src/pipeline/state.py` - AFCState definitions
- `src/pipeline/workspace.py` - AgenticWorkspace for file I/O
- `src/pipeline/chapters.py` - Chapter database

**Entry Point:**
- `main.py` - CLI and pipeline runner
