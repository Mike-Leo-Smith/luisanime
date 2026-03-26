# Agentic Filming Pipeline (AFP)

The **Agentic Filming Pipeline (AFP)** is a state-of-the-art, automated system designed to transcode long-form textual novels into broadcast-quality animated video sequences. 

By modeling the process after modern compiler infrastructures and physically-based rendering pipelines, AFP abstracts the unpredictable nature of generative AI behind strict state machines, Intermediate Representations (IR), and automated visual linters.

## 🚀 Key Features
- **Frontend/Backend Decoupling:** LLMs act as the "Compiler Frontend" (parsing text to AST/Shot Lists), while Video APIs serve as the "Rasterization Backend."
- **Defensive Generation:** Every generated sequence is validated by an automated Vision-Language Model (VLM) inspection (QA Linter).
- **Hierarchical Memory:** Manages context over 100k+ words using a multi-level cache (Global Symbol Table, Scene Graph, and Working Register).
- **Local Post-Processing:** Deterministic lip-syncing and compositing are handled locally for precision and cost-efficiency.

## 🛠 Tech Stack (2026 SOTA)
- **Orchestration:** LangGraph (Python)
- **Logic/Reasoning:** Gemini 3.1 Pro / GPT-5.2 / Claude 4.6
- **Vision QA:** Gemini 3.1 Pro
- **Image Generation:** Nano Banana 2 / Flux.1 Pro
- **Video Generation:** Veo 3.1 / Sora 2 / Kling 3.0
- **Local Processing:** MuseTalk, FFmpeg, Pydantic, Redis

## 📖 Documentation
- [DESIGN.md](./DESIGN.md) - Comprehensive architectural deep-dive.
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Guidelines for extending agent nodes.

## 🚦 Getting Started
*(In Development)*
1. Clone the repository.
2. Configure `config.yaml` with your API keys.
3. Run `pip install -r requirements.txt`.
4. Execute the pipeline: `python main.py --novel path/to/novel.txt`.

---
*Built for the next generation of automated storytelling.*
