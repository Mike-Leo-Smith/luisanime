# Agentic Filming Pipeline (AFP)

The **Agentic Filming Pipeline (AFP)** is a state-of-the-art, automated system designed to transcode long-form textual novels into broadcast-quality animated video sequences. 

By modeling the process after modern compiler infrastructures and physically-based rendering pipelines, AFP abstracts the unpredictable nature of generative AI behind strict state machines, Intermediate Representations (IR), and automated visual linters.

## 🚀 Key Features
- **Per-Agent Configuration:** Each AI agent has independent provider, model, and API key settings
- **Multi-Provider Support:** Unified interface for Gemini, MiniMax, and OpenAI-compatible APIs
- **Shot-Based Asset Organization:** Clean project structure with per-shot assets and shared resources
- **Resumable Pipeline:** Checkpoint system allows resuming from any stage
- **Frontend/Backend Decoupling:** LLMs act as the "Compiler Frontend" (parsing text to AST/Shot Lists), while Video APIs serve as the "Rasterization Backend"
- **Defensive Generation:** Every generated sequence is validated by an automated Vision-Language Model (VLM) inspection (QA Linter)
- **Hierarchical Memory:** Manages context over 100k+ words using a multi-level cache (Global Symbol Table, Scene Graph, and Working Register)
- **Local Post-Processing:** Deterministic lip-syncing and compositing are handled locally for precision and cost-efficiency

## 🛠 Tech Stack
- **Orchestration:** LangGraph (Python)
- **Logic/Reasoning:** Gemini 1.5 Pro / GPT-4 / Claude
- **Vision QA:** Gemini 1.5 Pro
- **Image Generation:** MiniMax Image-01 / Gemini Flash
- **Video Generation:** MiniMax Hailuo-02 / Veo / Sora / Kling
- **Local Processing:** MuseTalk, FFmpeg, Pydantic

## 📖 Documentation
- [DESIGN.md](./DESIGN.md) - Comprehensive architectural deep-dive with provider abstraction and configuration system
- [PROGRESS.md](./PROGRESS.md) - Current implementation status and roadmap

## 🚦 Getting Started

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
# Gemini agents (lore_master, screenwriter, director, qa_linter)
export LORE_MASTER_API_KEY="your_gemini_api_key"
export SCREENWRITER_API_KEY="your_gemini_api_key"
export DIRECTOR_API_KEY="your_gemini_api_key"
export QA_LINTER_API_KEY="your_gemini_api_key"

# MiniMax agents (storyboarder, animator)
export STORYBOARDER_API_KEY="your_minimax_api_key"
export ANIMATOR_API_KEY="your_minimax_api_key"
```

Or create a `.env` file:
```
LORE_MASTER_API_KEY=your_gemini_api_key
SCREENWRITER_API_KEY=your_gemini_api_key
DIRECTOR_API_KEY=your_gemini_api_key
QA_LINTER_API_KEY=your_gemini_api_key
STORYBOARDER_API_KEY=your_minimax_api_key
ANIMATOR_API_KEY=your_minimax_api_key
```

#### Customize Configuration (Optional)

Edit `config.yaml` to customize:
- Video style, resolution, FPS
- Agent models and parameters
- Generation settings (retries, thresholds)
- Style presets for prompts

### 3. Initialize a Project

```bash
python main.py init my_video_project
```

This creates a project directory with:
```
my_video_project/
├── config.yaml          # Project-specific config
├── novel.txt            # Place your source text here
├── shots/               # Generated shot assets
└── shared/              # Characters, locations, audio
    ├── characters/
    ├── locations/
    └── audio/
```

### 4. Run the Pipeline

```bash
# Run with a project
python main.py run --novel my_novel.txt --project my_video_project

# Run specific stage only
python main.py run --novel my_novel.txt --project my_video_project --stage pre_production

# Resume from checkpoint
python main.py run --resume-from my_video_project/checkpoints/checkpoint_005.json

# Use custom config file
CONFIG_PATH=/path/to/config.yaml python main.py run --novel my_novel.txt
```

### 5. Backwards Compatibility

The old API still works for quick tests:

```python
from main import run_pipeline

# Simple usage (uses default config)
run_pipeline("path/to/novel.txt")

# With project
run_pipeline("path/to/novel.txt", project_path="my_video_project")
```

## 🏗 Architecture Overview

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
  # High-token agents use Flash for cost efficiency
  lore_master:
    provider: "gemini"
    model: "gemini-3.1-flash-preview"
    api_key: "ENV:LORE_MASTER_API_KEY"
    temperature: 0.2

  screenwriter:
    provider: "gemini"
    model: "gemini-3.1-flash-preview"
    api_key: "ENV:SCREENWRITER_API_KEY"
    temperature: 0.3

  # Reasoning-heavy agents use Pro
  director:
    provider: "gemini"
    model: "gemini-3.1-pro-preview"
    api_key: "ENV:DIRECTOR_API_KEY"
    temperature: 0.2

  qa_linter:
    provider: "gemini"
    model: "gemini-3.1-pro-preview"
    api_key: "ENV:QA_LINTER_API_KEY"
    temperature: 0.0

  animator:
    provider: "minimax"
    model: "MiniMax-Hailuo-02"
    api_key: "ENV:ANIMATOR_API_KEY"
```

### Project Structure

Projects use a shot-based organization:

```
project/
├── config.yaml
├── novel.txt
├── checkpoints/           # Pipeline state snapshots
├── shared/               # Common assets
│   ├── characters/      # Character reference images
│   ├── locations/       # Background images
│   └── audio/           # Music, sound effects
└── shots/
    ├── shot_001/
    │   ├── metadata.json    # Shot IR
    │   ├── keyframe.png     # Generated keyframe
    │   ├── video.mp4        # Generated video
    │   └── qa_report.json   # QA results
    └── ...
```

## 🎨 Configuration Reference

### Video Settings

```yaml
video:
  style: "anime"              # anime, cinematic, realistic, cyberpunk
  resolution: "1080p"         # 720p, 1080p, 4k
  fps: 24
  duration_per_shot: 4.0
  aspect_ratio: "16:9"
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

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_director.py

# Run with coverage
pytest --cov=src tests/
```

## 🐛 Troubleshooting

### Missing API Keys
If you see `MISSING_ENV_XXX`, ensure the corresponding environment variable is set.

### Provider Errors
Check that the model names in `config.yaml` match the provider's available models.

### Checkpoint Issues
To resume from a specific point:
```bash
python main.py run --resume-from path/to/checkpoint.json
```

## 📄 License

[Your License Here]

---
*Built for the next generation of automated storytelling.*
