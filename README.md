# Agentic Filming Pipeline (AFP) - Autonomous Film Crew (AFC)

The **Agentic Filming Pipeline (AFP)** is a state-of-the-art, automated system designed to transcode long-form textual novels into broadcast-quality animated video sequences using an **Autonomous Film Crew (AFC)** architecture.

By modeling the process after modern compiler infrastructures and physically-based rendering pipelines, AFP abstracts the unpredictable nature of generative AI behind strict state machines, Intermediate Representations (IR), and automated visual linters. The system uses a **LangGraph-based workflow** where specialized AI agents collaborate as a film production crew.

## Key Features
- **Autonomous Film Crew Architecture**: 9 specialized agents collaborate via LangGraph state machine
- **Per-Agent Configuration**: Each AI agent has independent provider, model, and API key settings
- **Multi-Provider Support**: Unified interface for Gemini and MiniMax APIs
- **Scene-Based Production**: Novels are broken into scenes, then shots, with full continuity management
- **Quality Assurance Loops**: Automated VLM inspection with retry logic and circuit breakers
- **Budget Management**: Built-in cost tracking with automatic production halt on budget exceedance
- **Resumable Pipeline**: State-based architecture supports checkpointing and recovery

## Tech Stack
- **Orchestration**: LangGraph (Python) with cyclic workflow graphs
- **Logic/Reasoning**: Gemini 1.5 Pro / Flash
- **Vision QA**: Gemini 1.5 Pro (Keyframe + Render QA)
- **Image Generation**: Gemini Image API
- **Video Generation**: MiniMax Hailuo-2.3
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

```bash
# Gemini agents (showrunner, screenwriter, production_designer, director, etc.)
export GEMINI_FLASH_API_KEY="your_gemini_api_key"
export GEMINI_PRO_API_KEY="your_gemini_api_key"

# MiniMax agents (lead_animator)
export MINIMAX_VIDEO_API_KEY="your_minimax_api_key"
```

Or create a `.env` file:
```
GEMINI_FLASH_API_KEY=your_gemini_api_key
GEMINI_PRO_API_KEY=your_gemini_api_key
MINIMAX_VIDEO_API_KEY=your_minimax_api_key
```

#### Customize Configuration (Optional)

Edit `config.yaml.template` to customize:
- Video style, resolution, FPS
- Agent models and parameters
- Project budget and retry settings
- Style presets for prompts

### 3. Create a Project

```bash
python main.py create my_video_project novel.txt --style anime --max-shots 10
```

This creates a project directory with:
```
projects/my_video_project/
├── 00_project_config/
│   └── config.yaml          # Project configuration
├── 01_source_material/
│   └── novel.txt            # Source novel
├── 02_screenplays/          # Scene scripts (JSON)
├── 03_lore_bible/           # Character/style documentation
├── 04_production_slate/     # Shot plans and keyframes
│   └── shots/
├── 05_dailies/              # Generated video clips
├── 06_logs/                 # Production logs
└── config.yaml              # Legacy config (symlink)
```

### 4. Run the Pipeline

```bash
# Run the full autonomous pipeline
python main.py run my_video_project

# Check project status
python main.py status my_video_project
```

The pipeline automatically executes the full workflow:
1. **Screenwriter** → Parses novel into scenes
2. **Showrunner** → Orchestrates scene-by-scene production
3. **Director** → Breaks scenes into shots with continuity
4. **Script Coordinator** → Manages shot queue
5. **Production Designer** → Establishes visual style
6. **Cinematographer** → Generates keyframes
7. **Continuity Supervisor** → QA on keyframes
8. **Lead Animator** → Generates video from keyframes
9. **Editor** → Assembles final video

## Architecture Overview

### The Film Crew (Agents)

The AFC consists of 9 specialized agents orchestrated by LangGraph:

| Agent | Role | Provider | Responsibility |
|-------|------|----------|----------------|
| **Screenwriter** | Creative | Gemini Flash | Parses novel text into structured scene documents |
| **Showrunner** | Orchestrator | Gemini Flash | Routes workflow, manages budget, audits costs |
| **Director** | Creative | Gemini Flash | Generates shot plans with cinematic continuity |
| **Script Coordinator** | Support | Gemini Flash | Manages shot queue, determines next actions |
| **Production Designer** | Creative | Gemini Flash + Image | Establishes visual style and references |
| **Cinematographer** | Creative | Gemini Flash + Image | Generates keyframes from shot plans |
| **Continuity Supervisor** | QA | Gemini Pro | VLM-based QA on keyframes and renders |
| **Lead Animator** | Creative | Gemini Flash + MiniMax | Generates video from approved keyframes |
| **Editor** | Support | Gemini Flash | Assembles scenes into final deliverable |

### Provider Abstraction

The system uses a provider abstraction layer to support multiple AI backends:

```python
from src.providers.factory import ProviderFactory
from src.config import load_config, ConfigLoader

config = load_config()
agent_cfg = ConfigLoader.get_agent_config(config, "director")

# Creates the appropriate provider automatically
llm = ProviderFactory.create_llm(agent_cfg)
```

Supported providers:
- **Gemini** - LLM and image generation
- **MiniMax** - Video generation

### Project Structure

```
project/
├── 00_project_config/       # Configuration
│   └── config.yaml
├── 01_source_material/      # Source novel
│   └── novel.txt
├── 02_screenplays/          # Scene scripts (JSON)
│   └── scene_001.json
├── 03_lore_bible/           # Style guides, character sheets
├── 04_production_slate/     # Shot plans, keyframes
│   └── shots/
│       ├── S1_SHOT_001.json
│       └── S1_SHOT_002.json
├── 05_dailies/              # Generated video clips
├── 06_logs/                 # Production logs
└── config.yaml              # Legacy config
```

### LangGraph Workflow

The pipeline uses a cyclic graph with conditional routing:

```
START → Screenwriter → Showrunner → Director → Script Coordinator
                                           ↓
Editor ← Continuity Supervisor ← Lead Animator ← Cinematographer ← Production Designer
  ↑                                              ↓
  └──────────────────────────────────────────────┘ (retry loops)
```

Key routing decisions:
- **Showrunner** → Routes to Director or END based on remaining scenes
- **Script Coordinator** → Enters micro-loop or finishes scene
- **Continuity Supervisor** → Approves, retries, or escalates (circuit breaker)

## Configuration Reference

### Video Settings

```yaml
video:
  style: "anime"              # anime, cinematic
  resolution: "1080p"         # 1080p, 720p, 360p
  fps: 24
  aspect_ratio: "16:9"
```

### Generation Settings

```yaml
generation:
  project_budget_usd: 100.0   # Max budget in USD
  max_retries_per_shot: 3     # Auto-retry on failure
  enable_vlm_qa: true         # Enable visual QA
```

### Agent Configuration

```yaml
agents:
  showrunner:
    llm: gemini-flash
  director:
    llm: gemini-flash
  cinematographer:
    llm: gemini-flash
    image: gemini-image
  lead_animator:
    llm: gemini-flash
    video: minimax-video
  continuity_supervisor:
    llm: gemini-pro
```

### Style Presets

```yaml
style_presets:
  anime:
    prompt_prefix: "Studio Ghibli 2D manga style..."
    prompt_suffix: "Vibrant but natural colors..."
  cinematic:
    prompt_prefix: "Cinematic 35mm film style..."
    prompt_suffix: "Dramatic lighting, deep shadows..."
```

## Testing

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_director.py

# Run with coverage
pytest --cov=src tests/
```

## Troubleshooting

### Missing API Keys
If you see `MISSING_ENV_XXX`, ensure the corresponding environment variable is set.

### Provider Errors
Check that the model names in `config.yaml` match the provider's available models.

### Budget Exceeded
The pipeline automatically halts when the budget is exceeded. Check `06_logs/` for cost tracking.

### Continuity Failures
If shots fail QA repeatedly, the circuit breaker triggers and escalates to the Director for prompt simplification.

## License

[Your License Here]

---
*Built for the next generation of automated storytelling.*
