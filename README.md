# Agentic Filming Pipeline (AFP)

The **Agentic Filming Pipeline (AFP)** is a state-of-the-art, automated system designed to transcode long-form textual novels into broadcast-quality animated video sequences. 

By modeling the process after modern compiler infrastructures and physically-based rendering pipelines, AFP abstracts the unpredictable nature of generative AI behind strict state machines, Intermediate Representations (IR), and automated visual linters.

## Key Features
- **Per-Agent Configuration:** Each AI agent has independent provider, model, and API key settings
- **Multi-Provider Support:** Unified interface for Gemini, MiniMax, and OpenAI-compatible APIs
- **Shot-Based Asset Organization:** Clean project structure with per-shot assets and shared resources
- **Resumable Pipeline:** Checkpoint system allows resuming from any stage
- **Frontend/Backend Decoupling:** LLMs act as the "Compiler Frontend" (parsing text to AST/Shot Lists), while Video APIs serve as the "Rasterization Backend"
- **Defensive Generation:** Every generated sequence is validated by an automated Vision-Language Model (VLM) inspection (QA Linter)
- **Hierarchical Memory:** Manages context over 100k+ words using a multi-level cache (Global Symbol Table, Scene Graph, and Working Register)
- **Local Post-Processing:** Deterministic lip-syncing and compositing are handled locally for precision and cost-efficiency

## Tech Stack
- **Orchestration:** LangGraph (Python)
- **Logic/Reasoning:** Gemini 1.5 Pro / GPT-4 / Claude
- **Vision QA:** Gemini 1.5 Pro
- **Image Generation:** MiniMax Image-01 / Gemini Flash
- **Video Generation:** MiniMax Hailuo-02 / Veo / Sora / Kling
- **Local Processing:** MuseTalk, FFmpeg, Pydantic

## Documentation
- [DESIGN.md](./DESIGN.md) - Comprehensive architectural deep-dive with provider abstraction and configuration system
- [PROGRESS.md](./PROGRESS.md) - Current implementation status and roadmap

## Getting Started

### 1. Installation

```bash
git clone <repository-url>
cd agentic-filming-pipeline
pip install -r requirements.txt
```

### 2. Configuration

#### Set up API Keys

Each agent uses its own API key. Set them as environment variables:

```bash
# Gemini agents (indexer, lore_master, screenwriter, director, image_qa, video_qa)
export GEMINI_FLASH_API_KEY="your_gemini_api_key"
export GEMINI_PRO_API_KEY="your_gemini_api_key"

# MiniMax agents (storyboarder, animator)
export MINIMAX_IMAGE_API_KEY="your_minimax_api_key"
export MINIMAX_VIDEO_API_KEY="your_minimax_api_key"
```

Or create a `.env` file:
```
GEMINI_FLASH_API_KEY=your_gemini_api_key
GEMINI_PRO_API_KEY=your_gemini_api_key
MINIMAX_IMAGE_API_KEY=your_minimax_api_key
MINIMAX_VIDEO_API_KEY=your_minimax_api_key
```

#### Customize Configuration (Optional)

Edit `config.yaml` to customize:
- Video style, resolution, FPS
- Agent models and parameters
- Generation settings (retries, thresholds)
- Style presets for prompts

### 3. Create a Project

```bash
python main.py create my_video_project novel.txt
```

This creates a project directory with:
```
my_video_project/
├── config.yaml          # Project-specific config
├── src/
│   └── novel.txt        # Source novel
├── assets/              # Generated assets
│   ├── characters/      # Character profiles
│   ├── locations/       # Location profiles
│   ├── audio/           # Audio assets
│   └── lore/            # Entity database
├── index/               # Chapter index and metadata
│   └── chapters/        # Individual chapter files
├── scenes/              # Scene-based shot organization
│   └── {scene_id}/
│       ├── metadata.json
│       └── shots/
│           └── {shot_id}/
│               ├── metadata.json
│               ├── keyframe.png
│               └── video.mp4
├── cache/               # Cache files
├── checkpoints/         # Pipeline checkpoints
├── output/              # Final deliverables
├── logs/                # Pipeline logs
└── README.md            # Project documentation
```

### 4. Run Pipeline Stages

```bash
# Run individual stages
python main.py index my_video_project      # Segment novel into chapters
python main.py lore my_video_project       # Extract entities
python main.py scenes my_video_project     # Break into scenes
python main.py shots my_video_project      # Generate shot list
python main.py storyboard my_video_project # Generate keyframes
python main.py animate my_video_project    # Generate video clips
python main.py qa my_video_project         # Quality assurance
python main.py post-prod my_video_project  # Final assembly

# Check status
python main.py status my_video_project
```

## Architecture Overview

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
- **MiniMax** - Image and video generation
- **OpenAI** - LLM (OpenAI-compatible APIs)

### Agent Configuration

Each agent is independently configured in `config.yaml`:

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
  image_qa:
    model: gemini-pro
    temperature: 0.0
  video_qa:
    model: gemini-pro
    temperature: 0.0
  storyboarder:
    model: minimax-image
  animator:
    model: minimax-video
```

### Project Structure

```
project/
├── src/                   # Source materials
│   └── novel.txt
├── assets/                # Generated assets
│   ├── characters/        # Character profiles
│   ├── locations/         # Location profiles
│   ├── audio/             # Audio assets
│   └── lore/              # Entity database (entities.json)
├── index/                 # Chapter index
│   ├── project.json       # Project metadata
│   ├── toc.json           # Table of contents
│   └── chapters/          # Individual chapters
├── scenes/                # Scene organization
│   └── {scene_id}/
│       ├── metadata.json
│       └── shots/
├── cache/                 # Cache files
├── checkpoints/           # Pipeline checkpoints
├── output/                # Final deliverables
├── logs/                  # Pipeline logs
└── config.yaml
```

## Configuration Reference

### Video Settings

```yaml
video:
  style: "anime"              # anime, cinematic, realistic, cyberpunk
  resolution: "1080p"         # 720p, 1080p, 4k
  fps: 24
```

### Generation Settings

```yaml
generation:
  max_retries_per_shot: 3     # Auto-retry on failure
  candidates_per_take: 1      # Videos per shot
  qa_threshold: 0.8           # Quality threshold
  skip_lip_sync: false
  enable_vlm_qa: true
```

### Style Presets

```yaml
style_presets:
  anime:
    prompt_prefix: "High-quality 3D anime style."
    prompt_suffix: "Studio Ghibli inspired..."
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

### Checkpoint Issues
To resume from a specific point, use the checkpoint files in `checkpoints/`.

## License

[Your License Here]

---
*Built for the next generation of automated storytelling.*
