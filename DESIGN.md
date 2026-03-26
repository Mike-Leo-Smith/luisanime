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
| **MiniMax** | ❌ | ✅ | ✅ | `image_model`, `video_model`, `api_key` |
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
```yaml
checkpoints/
  checkpoint_001.json      # Full pipeline state
  checkpoint_002.json
  ...
```

Resume from any checkpoint:
```bash
python main.py --resume-from checkpoint_001.json
```

---

## 5. Project Structure & Asset Organization

### 5.1 Shot-Based Asset Layout

```
project/
├── config.yaml              # Project-specific configuration
├── novel.txt                # Source material
├── checkpoints/             # Pipeline state snapshots
├── shared/                  # Common assets across shots
│   ├── characters/
│   │   ├── hero_ref.png
│   │   └── villain_ref.png
│   ├── locations/
│   │   └── castle_bg.png
│   └── audio/
│       └── soundtrack.mp3
└── shots/
    ├── shot_001/
    │   ├── metadata.json    # Shot IR (prompt, duration, etc.)
    │   ├── keyframe.png     # Generated by storyboarder
    │   ├── video.mp4        # Generated by animator
    │   └── qa_report.json   # QA linter results
    ├── shot_002/
    └── ...
```

### 5.2 Project Manager

The `ProjectManager` handles asset paths and organization:

```python
from src.core.project_manager import ProjectManager

pm = ProjectManager("./my_project")
keyframe_path = pm.get_shot_asset_path("shot_001", "keyframe.png")
shared_char_path = pm.get_shared_asset_path("characters", "hero.png")
```

---

## 6. Agent Topology & Workflow (StateGraph)

The pipeline lifecycle consists of four phases executed by specialized Agents:

### Phase 1: Pre-production (Text to IR)
1.  **Lore Master:** Scans text, initializes L3 Entity Graph.
2.  **Screenwriter:** Chunks chapters into `Scene IR` metadata (location, time, characters).
3.  **Director (The Master Node):** Compiles `Scene IR` into a strictly formatted JSON `Shot List`. **Rule:** Must decompose complex rigid body dynamics and physical interactions (e.g., combat) into safe, renderable montages (e.g., close-ups of weapons, isolated reactions) to bypass physics hallucinations.

### Phase 2: Asset Locking
1.  **Storyboarder:** Calls Image APIs to generate the first frame (Keyframe) of a shot based on the Director's prompt and L3 state. Extracts facial embeddings ($v_{ref}$) for consistency checks.

### Phase 3: Production & Micro-QA Loop
1.  **Animator:** Submits the Keyframe + Text Prompt + Camera params to the Video API. Pulls 3 candidate takes.
2.  **QA Linter (The Safety Net):** Passes frames to a VLM. 
    * *Topological Check:* Analyzes for fluid-like limb melting or multi-finger mutations.
    * *Consistency Check:* Calculates cosine similarity $S = \frac{v_t \cdot v_{ref}}{||v_t|| ||v_{ref}||}$. Rejects if $S < \tau$.
    * *Routing:* If Pass $\rightarrow$ push to Post-production. If Fail $\rightarrow$ Re-roll Animator. If 3 consecutive Fails $\rightarrow$ Fallback to Director to simplify the physical action prompt.

### Phase 4: Post-Production
1.  **Sound Designer:** Generates TTS (`.wav`) and retrieves Foley/BGM.
2.  **Lip-Sync Agent:** Applies audio-driven mouth masking to the QA-approved video clip locally.
3.  **Compositor:** Stitches `.mp4` and `.wav` tracks via FFmpeg.

---

## 7. Configuration System

### 7.1 Per-Agent Configuration

Each agent has its own configuration section with provider-specific settings:

```yaml
agents:
  lore_master:
    provider: "gemini"
    model: "gemini-3.1-pro"
    api_key: "ENV:LORE_MASTER_API_KEY"
    temperature: 0.2

  screenwriter:
    provider: "gemini"
    model: "gemini-3.1-pro"
    api_key: "ENV:SCREENWRITER_API_KEY"
    temperature: 0.3

  director:
    provider: "gemini"
    model: "gemini-3.1-pro"
    api_key: "ENV:DIRECTOR_API_KEY"
    temperature: 0.2

  storyboarder:
    provider: "minimax"
    model: "image-01"
    api_key: "ENV:STORYBOARDER_API_KEY"

  animator:
    provider: "minimax"
    model: "MiniMax-Hailuo-02"
    api_key: "ENV:ANIMATOR_API_KEY"

  qa_linter:
    provider: "gemini"
    model: "gemini-3.1-pro"
    api_key: "ENV:QA_LINTER_API_KEY"
    temperature: 0.0
```

### 7.2 Configuration Loading Hierarchy

Configuration is loaded in the following priority order (later overrides earlier):

1. **Root `config.yaml`** - Default settings
2. **Environment variable `CONFIG_PATH`** - Alternative config file
3. **Project directory `config.yaml`** - Project-specific overrides

```python
from src.config import load_config, ConfigLoader

# Load with hierarchical merging
config = load_config(project_path="./my_project")

# Get merged agent config (includes provider defaults)
agent_cfg = ConfigLoader.get_agent_config(config, "director")
# Result: {provider: "gemini", model: "gemini-3.1-pro", api_key: "...", temperature: 0.2}
```

### 7.3 Environment Variables

API keys are specified via environment variables:

```bash
# Agent-specific keys
export LORE_MASTER_API_KEY="your_gemini_key"
export SCREENWRITER_API_KEY="your_gemini_key"
export DIRECTOR_API_KEY="your_gemini_key"
export STORYBOARDER_API_KEY="your_minimax_key"
export ANIMATOR_API_KEY="your_minimax_key"
export QA_LINTER_API_KEY="your_gemini_key"

# Or use provider-wide fallbacks
export GEMINI_API_KEY="your_gemini_key"
export MINIMAX_API_KEY="your_minimax_key"

# Custom config path
export CONFIG_PATH="/path/to/custom/config.yaml"
```

---

## 8. Technology Stack & SOTA Model Selection (2026 Landscape)

Based on the latest 2026 benchmarks for reasoning, vision, and video generation, the following models are selected for their respective roles in the pipeline:

| Component | Role | Recommended SOTA Models (2026) | Rationale |
| :--- | :--- | :--- | :--- |
| **Frontend LLM** | Director & Screenwriter (Logic & AST Generation) | **Gemini 3.1 Pro**, **GPT-5.2**, **Claude 4.6 Sonnet** | These models lead the LM-Arena for spatial reasoning, JSON formatting compliance, and possessing 1M+ context windows necessary for L3 state injection. |
| **Vision Linter** | QA Agent (Physical & Topological Checks) | **Gemini 3.1 Pro**, **GPT-5.2** | Gemini 3.1 Pro currently tops the Vision Arena leaderboard. Crucial for detecting microscopic pixel blending, rigid-body failures, and executing the strict `qa_checklist`. |
| **Image API** | Storyboarder (Keyframe & Asset Locking) | **MiniMax Image-01**, **Nano Banana 2** (Gemini 3 Flash Image), **Flux.1 Pro** | MiniMax offers cost-effective image generation. State-of-the-art alternatives for multi-image-to-image composition and style transfer. |
| **Video API** | Animator (Rasterization Backend) | **MiniMax Hailuo-02**, **Veo 3.1**, **Sora 2**, **Kling 3.0** | MiniMax Hailuo-02 provides good quality at lower cost. **Veo 3.1** leads in physical realism. **Sora 2** is unmatched for cinematic storytelling. |

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
# Initialize a new project
python main.py init my_video_project

# Run full pipeline
python main.py run --novel novel.txt --project my_video_project

# Run specific stage only
python main.py run --stage pre_production --novel novel.txt

# Resume from checkpoint
python main.py run --resume-from my_video_project/checkpoints/checkpoint_005.json

# Use custom config
CONFIG_PATH=/path/to/config.yaml python main.py run --novel novel.txt
```

### 10.2 Backwards Compatibility

The `run_pipeline()` function maintains backwards compatibility with the old API:

```python
from main import run_pipeline

# Old style (still works)
run_pipeline("path/to/novel.txt")

# New style with project
run_pipeline("path/to/novel.txt", project_path="my_project")
```
