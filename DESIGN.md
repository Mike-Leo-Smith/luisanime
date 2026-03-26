# System Architecture Design Document: Agentic Filming Pipeline (AFP)

## 1. Executive Summary & Engineering Philosophy
The Agentic Filming Pipeline (AFP) is an end-to-end, automated system designed to transcode long-form textual novels into broadcast-quality animated video sequences. 

To mitigate the inherent flaws of current Video Diffusion Models (e.g., topological collapse, temporal inconsistency, physical hallucinations), the AFP is explicitly modeled after modern compiler infrastructures and physically-based rendering pipelines. It abstracts the unpredictable nature of generative AI behind strict state machines, Intermediate Representations (IR), and automated visual linters.

The system adheres to three engineering principles:
1.  **Frontend/Backend Decoupling:** Large Language Models (LLMs) act strictly as the "Compiler Frontend" to parse text and generate structured ASTs (Shot Lists). Video APIs act purely as the "Rasterization Backend."
2.  **Defensive Generation via QA Linters:** No video clip is accepted blindly. Every generated sequence must pass a strict, automated Vision-Language Model (VLM) inspection.
3.  **Hybrid Compute Plane:** LLM reasoning and heavy pixel generation are outsourced to Cloud APIs to bypass VRAM bottlenecks, while deterministic post-processing (lip-sync, frame interpolation) remains local for precise control.

---

## 2. System Architecture: The Three Planes

The system is partitioned into three distinct operational planes orchestrated by a local runtime environment.

### 2.1 Control Plane (Local Orchestration)
* **Engine:** LangGraph. Handles state transitions, loop routing, and fault tolerance.
* **Memory/State DB:** Redis or MongoDB. Manages the hierarchical context and entity state machines.
* **Role:** The central bus. It never generates pixels; it only routes data and triggers API calls via strict Tool Calling.

### 2.2 Generation Plane (Cloud API Backend)
* **LLM Inference:** Top-tier reasoning models for high-fidelity logic, spatial decomposition, and JSON compliance.
* **Image/Video APIs:** Commercial endpoints for pixel rasterization.
* **Role:** Heavy compute execution. Subject to strict budget control and circuit breakers.

### 2.3 Post-Processing Plane (Local CPU/GPU)
* **Audio/Sync:** Local Python scripts invoking lightweight models (e.g., MuseTalk, Wav2Lip) for deterministic lip-syncing without altering full-frame topologies.
* **Compositing:** FFmpeg for timeline assembly, transitions, and audio multiplexing.

---

## 3. Hierarchical Memory & State Management
To prevent context degradation over a 100k+ word text, memory is managed akin to a multi-level cache.

* **L3 Global Symbol Table (Persistent DB):** Extracted by the *Lore Master Agent*. Stores immutable world-building rules and mutable character state machines (e.g., `hero_A: { left_arm: "missing", inventory: ["broken_sword"] }`). Timestamped by chapter ID.
* **L2 Scene Graph (Sliding Window):** Maintains the narrative continuity of the Past (last 5 scenes), Present (current scene), and Future (next 2 scenes).
* **L1 Working Register (RAG Injection):** The exact, assembled Prompt for the current shot, hard-coded with L3 visual attributes to force the generation model's compliance.

---

## 4. Agent Topology & Workflow (StateGraph)

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

## 5. Technology Stack & SOTA Model Selection (2026 Landscape)

Based on the latest 2026 benchmarks for reasoning, vision, and video generation, the following models are selected for their respective roles in the pipeline:

| Component | Role | Recommended SOTA Models (2026) | Rationale |
| :--- | :--- | :--- | :--- |
| **Frontend LLM** | Director & Screenwriter (Logic & AST Generation) | **Gemini 3.1 Pro**, **GPT-5.2**, **Claude 4.6 Sonnet** | These models lead the LM-Arena for spatial reasoning, JSON formatting compliance, and possessing 1M+ context windows necessary for L3 state injection. |
| **Vision Linter** | QA Agent (Physical & Topological Checks) | **Gemini 3.1 Pro**, **GPT-5.2** | Gemini 3.1 Pro currently tops the Vision Arena leaderboard. Crucial for detecting microscopic pixel blending, rigid-body failures, and executing the strict `qa_checklist`. |
| **Image API** | Storyboarder (Keyframe & Asset Locking) | **Nano Banana 2** (Gemini 3 Flash Image), **Flux.1 Pro** | State-of-the-art for multi-image-to-image composition, style transfer, and generating highly accurate character reference sheets. |
| **Video API** | Animator (Rasterization Backend) | **Veo 3.1**, **Sora 2**, **Kling 3.0**, **Runway Gen-4.5** | **Veo 3.1** leads in physical realism and native audio integration. **Sora 2** is unmatched for cinematic storytelling. **Kling 3.0** is the pioneer for multi-shot subject consistency. |

---

## 6. Global Configuration (`config.yaml`)

The system separates runtime configurations from the Python logic to allow dynamic adjustments of API keys, model endpoints, and circuit breaker thresholds.

```yaml
# ==========================================
# Agentic Filming Pipeline - Global Config
# ==========================================

project:
  name: "project_novel_to_anime"
  workspace_dir: "./workspace"
  log_level: "INFO"

control_plane:
  memory_db:
    type: "redis"
    url: "redis://127.0.0.1:6379/0"

  agents:
    director_node:
      provider: "google"
      model: "gemini-3.1-pro"
      api_key: "ENV:GEMINI_API_KEY"
      temperature: 0.2
      
    qa_linter:
      provider: "google"
      model: "gemini-3.1-pro"
      api_key: "ENV:GEMINI_API_KEY"
      temperature: 0.0  # Zero temperature for deterministic assertions

render_plane:
  storyboarder:
    provider: "google"
    model: "nano-banana-2"
    api_key: "ENV:GEMINI_API_KEY"
    
  animator:
    provider: "hailuo" # Modular: Switch to 'veo', 'sora', or 'kling' as needed
    model: "hailuo-video-v1"
    api_key: "ENV:VIDEO_API_KEY"
    pipeline_settings:
      max_retries_per_shot: 3
      candidates_per_take: 3

post_processing:
  lip_sync:
    engine: "local_musetalk"
    device: "cuda:0"
```

---

## 7. Crucial Engineering Caveats & Constraints

1.  **The API Censorship Trap (NSFW Filters):**
    Commercial video APIs possess highly sensitive safety filters. Combat scenes will frequently return HTTP 400/403 errors.
    * *Mitigation:* The LangGraph runtime must catch API-level safety rejections and trigger a specific `Fallback_Rewrite` state, forcing the Director Agent to rewrite the prompt using metaphorical or implied violence (e.g., montage techniques) to bypass censorship.
2.  **Lip-Sync Resolution Degradation:**
    Current local lip-sync models often output at lower resolutions for the masked face area, which looks blurry when pasted back onto a 1080p/4K video.
    * *Mitigation:* Only trigger lip-sync on Medium Shots or tighter. If Super Resolution (VSR) is integrated, lip-sync *must* be performed prior to the SR pass to blend the seams natively.
3.  **Circuit Breaker Implementation:**
    Video APIs are expensive. The LangGraph state *must* strictly enforce the `max_retries_per_shot` counter. If the threshold is reached, the system must automatically route back to the Director to heavily degrade the physical action prompt.
