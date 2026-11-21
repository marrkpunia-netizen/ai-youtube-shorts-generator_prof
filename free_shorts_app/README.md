# Free Shorts Studio

A free, open-source Streamlit app for turning long videos into vertical short clips. It uses local Whisper transcription, transparent rule-based highlight ranking, and FFmpeg rendering. **No API keys, paid services, usage credits, or external LLM calls.**

## Features
- Upload MP4, MOV, MKV or WebM videos
- Optional public YouTube URL input through `yt-dlp`
- Local speech transcription with `faster-whisper`
- Rule-based highlight scoring (no LLM/API)
- 9:16, 1:1 and 16:9 output
- Preview and download each generated clip

## Run locally (recommended)

Python 3.10–3.12 and FFmpeg are recommended.

```bash
git clone https://github.com/YOUR-USERNAME/free-shorts-studio.git
cd free-shorts-studio
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The first run downloads the selected Whisper model. This is a one-time model download, not an API call or credit charge. `tiny` is fastest, `base` is a reasonable default, and `small` may be more accurate but uses more resources.

## Deploy free with GitHub + Streamlit Community Cloud

1. Create a new public GitHub repository.
2. Upload all files from this project to the repository root.
3. Open [share.streamlit.io](https://share.streamlit.io/) and sign in with GitHub.
4. Choose **Create app**, select your repository and branch, and set the main file to `app.py`.
5. Deploy. No secrets or API keys are needed.

`packages.txt` asks the build environment to install FFmpeg. Free cloud resources are limited: Whisper model downloads, long videos, and rendering may exceed available RAM or execution time. For longer videos, run the same app locally on your computer. The cloud deployment itself is free under Streamlit Community Cloud's current free offering, subject to its terms and limits.

## How the highlight detector works

The app transcribes speech locally and ranks candidate time windows using word density, questions, emphasis words, and a small multilingual hook-word list. This is deliberately deterministic and does not use a generative AI model. It is not as context-aware as a large language model, and its score is not a guarantee of virality. Review clips before publishing.

## Notes
- Use videos you own or have permission to download and edit. Follow YouTube's terms and applicable copyright law.
- No guarantee is made that every YouTube URL can be downloaded; uploading a video file is the most reliable option.
- No API keys, paid credits, or subscription-based AI services are used by the app.

## License
MIT (see `LICENSE`).
