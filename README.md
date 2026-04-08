# Agentic Filming Pipeline (AFP) - Autonomous Film Crew (AFC)

The **Agentic Filming Pipeline (AFP)** is an end-to-end automated system that transcodes long-form textual novels into broadcast-quality video sequences using an **Autonomous Film Crew (AFC)** architecture.

By modeling the process after modern compiler infrastructures and physically-based rendering pipelines, AFP abstracts the unpredictable nature of generative AI behind strict state machines, Intermediate Representations (IR), and automated visual linters. The system uses a **LangGraph-based workflow** where specialized AI agents collaborate as a film production crew.

## Key Features
- **Autonomous Film Crew Architecture**: 11 specialized agents collaborate via LangGraph state machine
- **Shot Continuation Detection**: Director pre-marks continuation shots; pipeline reuses the last video frame as the starting keyframe for seamless transitions
- **Per-Agent Configuration**: Each AI agent has independent provider, model, and API key settings
- **Multi-Provider Support**: Unified interface for Gemini (LLM + Image), Kling (Video), and MiniMax (Video)
- **Scene-Based Production**: Novels are broken into scenes, then shots, with full continuity management
- **Quality Assurance Loops**: VLM-based QA at three stages — design validation, storyboard inspection, and keyframe review — with retry logic, best-of-N fallback, and circuit breakers
- **No-Text Enforcement**: Style presets enforce zero on-screen text, subtitles, or dialogue bubbles in all generated media
- **Storyboard-First Workflow**: Storyboard panels are generated before keyframes; keyframe converts Panel 1 into a full-resolution image
- **Location & Character Design**: Production Designer generates reference images for locations and characters to maintain visual consistency
- **Budget Management**: Built-in cost tracking with automatic production halt on budget exceedance

## Tech Stack
- **Orchestration**: LangGraph (Python) with cyclic workflow graphs
- **Logic/Reasoning**: Gemini 2.5 Flash (bulk agents), Gemini 3.1 Pro (vision QA)
- **Vision QA**: Gemini 3.1 Pro (keyframe inspection)
- **Image Generation**: Gemini 3.1 Flash Image Preview
- **Video Generation**: Kling v3-omni (via JWT-authenticated API)
- **State Management**: Pydantic TypedDict with annotation-based merging

## Documentation
- [DESIGN.md](./DESIGN.md) - Comprehensive architectural deep-dive with LangGraph topology
- [PROGRESS.md](./PROGRESS.md) - Current implementation status and roadmap
- [AGENTS.md](./AGENTS.md) - Agent development guide

## Getting Started

### 1. Installation

```bash
git clone git@github.com:Mike-Leo-Smith/luisanime.git
cd luisanime
pip install -r requirements.txt
```

### 2. Configuration

#### Set up API Keys

Create a `.env` file in the project root:

```
GEMINI_FLASH_API_KEY=your_gemini_api_key
GEMINI_PRO_API_KEY=your_gemini_api_key
KLING_ACCESS_KEY=your_kling_access_key
KLING_SECRET_KEY=your_kling_secret_key
```

#### Customize Configuration (Optional)

Edit `config.yaml.template` to customize:
- Video style, resolution, FPS
- Agent models and parameters
- Project budget and retry settings
- Style presets (anime, cinematic) with no-text enforcement

### 3. Create a Project

```bash
python main.py create my_project novel.txt --style cinematic --max-shots 20
```

This creates a project directory with:
```
projects/my_project/
├── 00_project_config/
│   └── config.yaml
├── 01_source_material/
│   └── novel.txt
├── 02_screenplays/           # Scene scripts (JSON)
├── 03_lore_bible/            # Character sheets, style guides, location designs
│   └── designs/
│       └── locations/
├── 04_production_slate/      # Shot execution plans
│   └── shots/
├── 05_dailies/               # Generated keyframes and video clips
├── 06_logs/                  # Production logs and QA reports
└── config.yaml
```

### 4. Run the Pipeline

```bash
# Run the full autonomous pipeline
python main.py run my_project

# Check project status
python main.py status my_project
```

The pipeline automatically executes the full workflow:
1. **Screenwriter** → Parses novel into scenes
2. **Showrunner** → Orchestrates scene-by-scene production, audits budget
3. **Director** → Breaks scenes into shots with continuity and continuation marking
4. **Script Coordinator** → Manages shot queue, tracks character state
5. **Production Designer** → Generates master style, character designs, and location designs
6. **Design QA** → VLM-based validation of character/location/object designs (up to 3 retries)
7. **Cinematographer** → Generates storyboard panels, then converts Panel 1 into a keyframe
8. **Storyboard QA** → VLM-based storyboard inspection against design references (up to 3 retries)
9. **Continuity Supervisor** → VLM-based QA on keyframes (auto-passes continuation keyframes)
10. **Lead Animator** → Generates video via Kling API (continuation mode merges action descriptions)
11. **Editor** → Assembles per-scene preview videos and final output

## Architecture Overview

### The Film Crew (Agents)

| Agent | Role | Providers | Responsibility |
|-------|------|-----------|----------------|
| **Screenwriter** | Creative | Gemini 2.5 Flash | Parses novel text into structured scene documents |
| **Showrunner** | Orchestrator | Gemini 2.5 Flash | Routes workflow, manages budget, audits costs |
| **Director** | Creative | Gemini 2.5 Flash | Generates shot plans with continuity and `is_continuation` marking |
| **Script Coordinator** | Support | Gemini 2.5 Flash | Manages shot queue, tracks per-character state mutations |
| **Production Designer** | Creative | Gemini 2.5 Flash + Gemini Image | Generates master style, character design sheets, location reference images |
| **Design QA** | QA | Gemini 3.1 Pro | VLM-based validation of character/location/object designs against specs |
| **Cinematographer** | Creative | Gemini 2.5 Flash + Gemini Image | Generates storyboard panels, then converts Panel 1 into a full-resolution keyframe |
| **Storyboard QA** | QA | Gemini 3.1 Pro | VLM-based storyboard inspection — character identity, panel count, staging |
| **Continuity Supervisor** | QA | Gemini 3.1 Pro | VLM-based keyframe QA with best-of-N fallback |
| **Lead Animator** | Creative | Gemini 2.5 Flash + Kling | Generates video from approved keyframes via Kling v3-omni |
| **Editor** | Support | FFmpeg | Assembles per-scene master videos with scale/pad normalization |

### Storyboard-First Pipeline

The Cinematographer generates a multi-panel storyboard first using design references and shot descriptions, then converts Panel 1 into a full-resolution keyframe. This ensures character identity fidelity — design refs inform the storyboard, and the storyboard alone informs the keyframe.

### Shot Continuation

The Director pre-marks shots with `is_continuation=True` when consecutive shots form a continuous motion. For continuation shots:
- **Cinematographer**: Extracts the last frame from the previous video as `keyframe_v1.png`
- **Continuity Supervisor**: Auto-passes (no QA needed since the frame comes from an approved video)
- **Lead Animator**: Uses `generate_video_continuation()` with the last frame as `first_frame` and a merged action description

### Provider Abstraction

Supported providers:
- **Gemini** — LLM (text generation, structured JSON output, vision analysis) and image generation
- **Kling** — Video generation via JWT-authenticated REST API with task polling
- **MiniMax** — Alternative video generation backend

### LangGraph Workflow

```
START → Screenwriter → Showrunner → Director → Script Coordinator
                                                       ↓
                                              Production Designer
                                                       ↓
                                                  Design QA ──→ (fail) → Production Designer
                                                       ↓ (pass)
                                                 Cinematographer
                                                       ↓
                                                Storyboard QA ──→ (fail) → Cinematographer
                                                       ↓ (pass)
                                            Continuity Supervisor
                                           ↓ (pass)        ↓ (fail)
                                      Lead Animator    Cinematographer (retry keyframe, up to 3×)
                                           ↓
                                         Editor → Showrunner → ... → END
```

## Configuration Reference

### Models

```yaml
models:
  gemini-flash:
    provider: "gemini"
    model: "gemini-2.5-flash"
    api_key: "ENV:GEMINI_FLASH_API_KEY"
  gemini-pro:
    provider: "gemini"
    model: "gemini-3.1-pro-preview"
    api_key: "ENV:GEMINI_PRO_API_KEY"
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

### Style Presets

```yaml
style_presets:
  anime:
    prompt_prefix: "Studio Ghibli 2D manga style, hand-drawn aesthetic, high-quality traditional animation."
    prompt_suffix: "Vibrant but natural colors... No text, no subtitles, no dialogue bubbles, no captions, no watermarks."
  cinematic:
    prompt_prefix: "Cinematic 35mm film style, photorealistic, highly detailed."
    prompt_suffix: "Dramatic lighting, deep shadows... No text, no subtitles, no dialogue bubbles, no captions, no watermarks."
```

## Troubleshooting

### Missing API Keys
If you see `MISSING_ENV_XXX`, set the corresponding environment variable in `.env`.

### Keyframe QA Failures
If a shot fails keyframe QA 3 times, the Continuity Supervisor selects the best candidate via best-of-N comparison rather than blocking the pipeline.

### Mirror Reflection False Positives
The QA agent is instructed to not flag laterally inverted details in mirror reflections as inconsistencies.

### Budget Exceeded
The Showrunner halts production when the budget is exceeded. Check `06_logs/` for cost details.

---
*Built for the next generation of automated storytelling.*
