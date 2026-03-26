# System Architecture Design Document: Agentic Filming Pipeline (AFP)

## 1. Executive Summary & Engineering Philosophy
The Agentic Filming Pipeline (AFP) is an end-to-end, automated system designed to transcode long-form textual novels into broadcast-quality animated video sequences. 

To mitigate the inherent flaws of current Video Diffusion Models (e.g., topological collapse, temporal inconsistency, physical hallucinations), the AFP is explicitly modeled after modern compiler infrastructures and physically-based rendering pipelines. It abstracts the unpredictable nature of generative AI behind strict state machines, Intermediate Representations (IR), and automated visual linters.

The system adheres to three engineering principles:
1.  **Frontend/Backend Decoupling:** Large Language Models (LLMs) act strictly as the "Compiler Frontend" to parse text and generate structured ASTs (Shot Lists). Video APIs act purely as the "Rasterization Backend."
2.  **Defensive Generation via QA Linters:** No video clip is accepted blindly. Every generated sequence must pass a strict, automated Vision-Language Model (VLM) inspection.
3.  **Hybrid Compute Plane:** LLM reasoning and heavy pixel generation are outsourced to Cloud APIs to bypass VRAM bottlenecks, while deterministic post-processing (lip-sync, frame interpolation) remains local for precise control.
4.  **Per-Agent Configuration:** Each agent has independent configuration for provider, model, API key, and parameters.
5.  **Shot-Based Asset Organization:** Assets are organized per-shot with shared resources in a hierarchical structure.
6.  **Resumable Pipeline:** Every stage is inspectable and resumable via checkpointing.

---

## 2. System Architecture: The Three Planes

The system is partitioned into three distinct operational planes orchestrated by a local runtime environment.

### 2.1 Control Plane (Local Orchestration)
* **Engine:** LangGraph. Handles state transitions, loop routing, and fault tolerance.
* **Memory/State DB:** Local file system with checkpointing, or Redis/MongoDB for distributed setups.
* **Configuration:** Per-project `config.yaml` with agent-specific settings.
* **Role:** The central bus. It never generates pixels; it only routes data and triggers API calls via strict Tool Calling.

### 2.2 Generation Plane (Cloud API Backend)
* **LLM Inference:** Top-tier reasoning models for high-fidelity logic, spatial decomposition, and JSON compliance.
* **Image/Video APIs:** Commercial endpoints for pixel rasterization with configurable providers.
* **Provider Abstraction:** Unified interface for Gemini, MiniMax, and OpenAI-compatible APIs.
* **Role:** Heavy compute execution. Subject to strict budget control and circuit breakers.

### 2.3 Post-Processing Plane (Local CPU/GPU)
* **Audio/Sync:** Local Python scripts invoking lightweight models (e.g., MuseTalk, Wav2Lip) for deterministic lip-syncing without altering full-frame topologies.
* **Compositing:** FFmpeg for timeline assembly, transitions, and audio multiplexing.

---

## 3. Provider Abstraction Layer

The system uses a provider abstraction layer to support multiple AI service backends without coupling to specific APIs.

### 3.1 Base Classes

```python
# Base provider interfaces
BaseLLMProvider      - Text generation and JSON output
BaseImageProvider    - Image generation and editing  
BaseVideoProvider    - Video generation with polling
```

### 3.2 Provider Implementations

| Provider | LLM | Image | Video | Configuration |
|----------|-----|-------|-------|---------------|
| **Gemini** | ✅ | ✅ | ❌ | `model`, `image_model`, `api_key` |
| **MiniMax** | ✅ | ✅ | ✅ | `model`, `image_model`, `video_model`, `api_key` |
| **OpenAI** | ✅ | ❌ | ❌ | `model`, `base_url`, `api_key` |

### 3.3 Provider Factory

Providers are instantiated via `ProviderFactory` which reads configuration and creates the appropriate provider:

```python
from src.providers.factory import ProviderFactory
from src.config import load_config, ConfigLoader

config = load_config()
agent_cfg = ConfigLoader.get_agent_config(config, "director")

llm_provider = ProviderFactory.create_llm(agent_cfg)
image_provider = ProviderFactory.create_image(agent_cfg)
video_provider = ProviderFactory.create_video(agent_cfg)
```

---

## 4. Hierarchical Memory & State Management

To prevent context degradation over a 100k+ word text, memory is managed akin to a multi-level cache.

* **L3 Global Symbol Table (Persistent DB):** Extracted by the *Lore Master Agent*. Stores immutable world-building rules and mutable character state machines (e.g., `hero_A: { left_arm: "missing", inventory: ["broken_sword"] }`). Timestamped by chapter ID.
* **L2 Scene Graph (Sliding Window):** Maintains the narrative continuity of the Past (last 5 scenes), Present (current scene), and Future (next 2 scenes).
* **L1 Working Register (RAG Injection):** The exact, assembled Prompt for the current shot, hard-coded with L3 visual attributes to force the generation model's compliance.

### 4.1 Checkpointing & Resumability

The pipeline saves state at configurable intervals:
- After each shot completion
- Before/after each agent stage
- On error conditions

Checkpoint format:
```
checkpoints/
  checkpoint_001.json      # Full pipeline state
  checkpoint_002.json
  ...
```

Resume from any checkpoint:
```bash
# Checkpoints are loaded automatically based on pipeline state
```

---

## 5. Project Structure & Asset Organization

### 5.1 Project Layout

```
project/
├── src/                       # Source materials
│   └── novel.txt              # Source novel text
├── assets/                    # Generated assets
│   ├── characters/            # Character profiles (JSON)
│   ├── locations/             # Location profiles (JSON)
│   ├── audio/                 # Audio assets (music, SFX)
│   └── lore/                  # Entity database
│       └── entities.json      # Extracted entities
├── index/                     # Chapter index
│   ├── project.json           # Project metadata
│   ├── toc.json               # Table of contents
│   └── chapters/              # Individual chapter files
│       ├── chapter_001.json
│       ├── chapter_001.txt
│       └── ...
├── scenes/                    # Scene-based organization
│   └── {scene_id}/
│       ├── metadata.json      # Scene metadata
│       └── shots/             # Shot assets
│           └── {shot_id}/
│               ├── metadata.json    # Shot IR
│               ├── keyframe.png     # Generated keyframe
│               └── video.mp4        # Generated video
├── cache/                     # Cache files
├── checkpoints/               # Pipeline state snapshots
├── output/                    # Final deliverables
├── logs/                      # Pipeline logs
├── config.yaml                # Project configuration
└── README.md                  # Project documentation
```

### 5.2 Project Manager

The `ProjectManager` handles asset paths and organization:

```python
from src.core.project import ProjectManager

pm = ProjectManager("./projects")
pm.load_project("my_project")

# Access paths
novel_path = pm.get_src_path("novel.txt")
entities_path = pm.get_assets_path("lore", "entities.json")
scene_path = pm.get_scene_path("scene_001", "metadata.json")
shot_path = pm.get_shot_path("scene_001", "shot_001", "keyframe.png")
output_path = pm.get_output_path("final_video.mp4")
```

---

## 6. Agent Topology & Workflow (StateGraph)

The pipeline lifecycle consists of four phases executed by specialized Agents:

### Phase 1: Indexing
1.  **Indexer:** Segments novel by natural chapters, extracts metadata (title, characters, events, tone).

### Phase 2: Pre-production (Text to IR)
1.  **Lore Master:** Scans text, initializes L3 Entity Graph.
2.  **Screenwriter:** Chunks chapters into `Scene IR` metadata (location, time, characters).
3.  **Director (The Master Node):** Compiles `Scene IR` into a strictly formatted JSON `Shot List`. **Rule:** Must decompose complex rigid body dynamics and physical interactions (e.g., combat) into safe, renderable montages (e.g., close-ups of weapons, isolated reactions) to bypass physics hallucinations.

### Phase 3: Asset Locking
1.  **Storyboarder:** Calls Image APIs to generate the first frame (Keyframe) of a shot based on the Director's prompt and L3 state.

### Phase 4: Production & Micro-QA Loop
1.  **Animator:** Submits the Keyframe + Text Prompt + Camera params to the Video API.
2.  **QA Linter (The Safety Net):** Passes frames to a VLM. 
    * *Topological Check:* Analyzes for fluid-like limb melting or multi-finger mutations.
    * *Consistency Check:* Validates visual consistency.
    * *Routing:* If Pass → push to Post-production. If Fail → Re-roll Animator. If max retries reached → Fallback to Director to simplify the physical action prompt.

### Phase 5: Post-Production
1.  **Sound Designer:** Generates TTS (`.wav`) and retrieves Foley/BGM.
2.  **Lip-Sync Agent:** Applies audio-driven mouth masking to the QA-approved video clip locally.
3.  **Compositor:** Stitches `.mp4` and `.wav` tracks via FFmpeg.

---

## 7. Configuration System

### 7.1 Per-Agent Configuration

Each agent has its own configuration section with provider-specific settings:

```yaml
agents:
  indexer:
    model: gemini-flash
    temperature: 0.1
  lore_master:
    model: gemini-flash
  screenwriter:
    model: gemini-flash
    temperature: 0.3
  director:
    model: gemini-pro
  storyboarder:
    model: minimax-image
  animator:
    model: minimax-video
  qa_linter:
    model: gemini-pro
    temperature: 0.0
```

### 7.2 Model Definitions

Models are defined in the `models` section and referenced by agents:

```yaml
models:
  gemini-flash:
    provider: gemini
    model: gemini-3.1-flash-lite-preview
    api_key: ENV:GEMINI_FLASH_API_KEY
  gemini-pro:
    provider: gemini
    model: gemini-3.1-pro-preview
    api_key: ENV:GEMINI_PRO_API_KEY
  minimax-image:
    provider: minimax
    model: image-01
    api_key: ENV:MINIMAX_IMAGE_API_KEY
  minimax-video:
    provider: minimax
    model: MiniMax-Hailuo-02
    api_key: ENV:MINIMAX_VIDEO_API_KEY
```

### 7.3 Configuration Loading Hierarchy

Configuration is loaded in the following priority order (later overrides earlier):

1. **Template `config.yaml.template`** - Default settings
2. **Project directory `config.yaml`** - Project-specific overrides

```python
from src.config import load_config, ConfigLoader

# Load with hierarchical merging
config = load_config(project_path="./my_project")

# Get merged agent config (includes provider defaults)
agent_cfg = ConfigLoader.get_agent_config(config, "director")
```

### 7.4 Environment Variables

API keys are specified via environment variables:

```bash
# Model-specific keys
export GEMINI_FLASH_API_KEY="your_gemini_key"
export GEMINI_PRO_API_KEY="your_gemini_key"
export MINIMAX_IMAGE_API_KEY="your_minimax_key"
export MINIMAX_VIDEO_API_KEY="your_minimax_key"
```

---

## 8. Technology Stack & SOTA Model Selection

Based on the latest benchmarks for reasoning, vision, and video generation:

| Component | Role | Recommended Models | Rationale |
| :--- | :--- | :--- | :--- |
| **Frontend LLM** | Director & Screenwriter (Logic & AST Generation) | **Gemini 3.1 Pro**, **GPT-4**, **Claude** | Spatial reasoning, JSON formatting, 1M+ context windows for L3 state injection. |
| **Vision Linter** | QA Agent (Physical & Topological Checks) | **Gemini 3.1 Pro** | Top Vision Arena performance for detecting pixel blending, rigid-body failures. |
| **Image API** | Storyboarder (Keyframe & Asset Locking) | **MiniMax Image-01**, **Gemini Flash Image** | Cost-effective image generation, multi-image composition. |
| **Video API** | Animator (Rasterization Backend) | **MiniMax Hailuo-02**, **Veo**, **Sora**, **Kling** | MiniMax for cost-efficiency, Veo/Sora for cinematic quality. |

---

## 9. Crucial Engineering Caveats & Constraints

1.  **The API Censorship Trap (NSFW Filters):**
    Commercial video APIs possess highly sensitive safety filters. Combat scenes will frequently return HTTP 400/403 errors.
    * *Mitigation:* The LangGraph runtime must catch API-level safety rejections and trigger a specific `Fallback_Rewrite` state, forcing the Director Agent to rewrite the prompt using metaphorical or implied violence (e.g., montage techniques) to bypass censorship.
2.  **Lip-Sync Resolution Degradation:**
    Current local lip-sync models often output at lower resolutions for the masked face area, which looks blurry when pasted back onto a 1080p/4K video.
    * *Mitigation:* Only trigger lip-sync on Medium Shots or tighter. If Super Resolution (VSR) is integrated, lip-sync *must* be performed prior to the SR pass to blend the seams natively.
3.  **Circuit Breaker Implementation:**
    Video APIs are expensive. The LangGraph state *must* strictly enforce the `max_retries_per_shot` counter. If the threshold is reached, the system must automatically route back to the Director to heavily degrade the physical action prompt.
4.  **Model Version Compatibility:**
    Different providers update models frequently. Pin model versions in production configs to ensure consistent output quality.
5.  **Rate Limiting & Cost Management:**
    Implement exponential backoff for API calls. Use separate API keys for different agents to isolate quota limits and track costs per agent.

---

## 10. CLI Interface

### 10.1 Basic Usage

```bash
# Create a new project
python main.py create my_video_project novel.txt

# Run individual stages
python main.py index my_video_project
python main.py lore my_video_project
python main.py scenes my_video_project
python main.py shots my_video_project
python main.py storyboard my_video_project
python main.py animate my_video_project
python main.py qa my_video_project
python main.py post-prod my_video_project

# Check status
python main.py status my_video_project
```

### 10.2 Agent Files

Each agent is in its own file for modularity:

```
src/agents/
├── indexer.py          # Text segmentation
├── lore_master.py      # Entity extraction
├── screenwriter.py     # Scene chunking
├── director.py         # Shot list generation
├── storyboarder.py     # Keyframe generation
├── animator.py         # Video generation
├── qa_linter.py        # Quality assurance
└── compositor.py       # Final assembly
```
