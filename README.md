# Private AI Readiness Advisor

An open-source Streamlit application for turning early enterprise AI requirements into a transparent pilot-readiness plan. The deterministic rules engine creates a score, approximate model-memory estimate, risk list, reference architecture, and next actions. An optional open model served from an OpenAI-compatible NVIDIA NIM endpoint can summarize the structured result.

> **Important:** This project is an educational planning aid, not an official NVIDIA, VMware, Broadcom, or hardware-vendor sizing tool. Validate all capacity decisions with measured benchmarks and official guidance.

## Why it matters
AI demos often skip infrastructure assumptions. This project exposes them, separates deterministic assessment from generative narrative, and gives reviewers a fully usable path without API credentials.

## Features
- Transparent, testable assessment logic
- Approximate 4-bit weight-memory planning calculation with visible overhead assumption
- Risk and governance prompts
- Optional NVIDIA NIM-compatible open-model narrative
- JSON report export
- No proprietary or confidential sample data

## Quick start
```bash
git clone YOUR_REPOSITORY_URL
cd private-ai-readiness-advisor
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Optional model integration
Copy `.env.example` to `.env`, set the endpoint and model, then export the variables before starting Streamlit. The endpoint must expose an OpenAI-compatible chat-completions API. Never commit credentials.

## How the estimate works
Version 0.1 uses an explicit planning approximation: `parameters in billions × 0.5 GB × 1.35 runtime overhead`. This approximates 4-bit model weights plus a fixed overhead. It deliberately does not claim throughput, concurrency capacity, or production suitability. Those require benchmarks.

## Test
```bash
pytest -q
```

## Architecture
See [architecture](docs/ARCHITECTURE.md).

## Roadmap and demo
- [30-day roadmap](docs/ROADMAP_30_DAYS.md)
- [90-second demo script](docs/DEMO_SCRIPT.md)

## License
MIT. Check the license of every model, dataset, container, and third-party component separately.
