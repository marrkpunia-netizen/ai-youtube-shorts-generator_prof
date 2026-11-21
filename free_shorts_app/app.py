from __future__ import annotations
import os, re, subprocess, tempfile
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="Free Shorts Studio", page_icon="🎬", layout="wide")

st.markdown("""
<style>
.block-container{padding-top:2rem;max-width:1180px}
.hero{padding:1.5rem;border-radius:18px;background:linear-gradient(120deg,#171923,#29233d);border:1px solid #45405d;margin-bottom:1.3rem}
.hero h1{margin:0;color:white;font-size:2.25rem}.hero p{color:#d0cce0;margin:.5rem 0 0}
div[data-testid="stMetric"]{background:rgba(120,110,150,.10);padding:12px;border-radius:12px}
</style>
<div class="hero"><h1>🎬 Free Shorts Studio</h1><p>Turn long videos into vertical clips — locally processed, with no API keys or credits.</p></div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Clip settings")
    model_size = st.selectbox("Whisper model", ["tiny", "base", "small"], index=1, help="Tiny is fastest; small may be more accurate but needs more memory.")
    clip_count = st.slider("Number of clips", 1, 8, 3)
    clip_length = st.slider("Target clip length (seconds)", 20, 90, 45, step=5)
    aspect = st.selectbox("Output format", ["9:16 (YouTube Shorts / Reels)", "1:1 (Square)", "16:9 (Landscape)"])
    language_choice = st.selectbox("Spoken language", ["Auto detect", "English", "Hindi", "Spanish", "French", "German", "Portuguese", "Arabic", "Japanese", "Other"])
    st.caption("All settings are processed by open-source tools. No paid AI service is called.")

st.subheader("1. Choose your video")
source_mode = st.radio("Video source", ["Upload a video", "YouTube URL"], horizontal=True)
uploaded = None
video_url = ""
if source_mode == "Upload a video":
    uploaded = st.file_uploader("Upload MP4, MOV, MKV or WebM", type=["mp4", "mov", "mkv", "webm"])
else:
    video_url = st.text_input("Paste a public YouTube video URL", placeholder="https://www.youtube.com/watch?v=...")
    st.caption("YouTube downloads depend on availability and the platform's terms. Use videos you have permission to process.")

st.info("**How highlight selection works:** speech is transcribed with Whisper, then a transparent, rule-based scoring system ranks moments using hooks, questions, emphasis words and information density. It does not call a paid LLM/API.")


def get_video_path():
    work = Path(tempfile.mkdtemp(prefix="free_shorts_"))
    if uploaded is not None:
        suffix = Path(uploaded.name).suffix or ".mp4"
        path = work / ("source" + suffix)
        path.write_bytes(uploaded.getbuffer())
        return path, work
    if video_url.strip():
        try:
            import yt_dlp
        except ImportError as e:
            raise RuntimeError("yt-dlp is missing. Install requirements.txt and restart.") from e
        opts = {"format": "best[ext=mp4]/best", "outtmpl": str(work / "source.%(ext)s"), "merge_output_format": "mp4", "quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([video_url.strip()])
        files = list(work.glob("source.*"))
        if not files:
            raise RuntimeError("The video could not be downloaded. Try uploading the video file instead.")
        return files[0], work
    raise RuntimeError("Upload a video or enter a YouTube URL first.")


def rank_highlights(segments, duration, count, target_len):
    """Deterministic highlight scoring; no model/API call."""
    if not segments:
        return []
    # Candidate windows begin at speech segments and span approximately target_len.
    candidates = []
    step = max(10, target_len // 3)
    starts = []
    t = 0
    while t < max(duration, 1):
        starts.append(float(t)); t += step
    starts.extend(float(s["start"]) for s in segments[::max(1, len(segments)//80)])
    starts = sorted(set(starts))
    hook_words = {"secret", "mistake", "never", "always", "truth", "why", "how", "important", "amazing", "surprising", "actually", "remember", "problem", "solution", "best", "worst", "imagine", "because", "लेकिन", "क्यों", "कैसे", "सच", "गलती"}
    emphasis = {"must", "should", "impossible", "incredible", "exactly", "first", "finally", "danger", "easy", "simple", "सबसे", "जरूरी"}
    for start in starts:
        end = min(duration, start + target_len)
        if end - start < min(12, target_len * .55):
            continue
        chosen = [s for s in segments if s["start"] < end and s["end"] > start]
        text = " ".join(s["text"].strip() for s in chosen).strip()
        words = re.findall(r"\b[\w']+\b", text.lower())
        if len(words) < 12:
            continue
        hook_hits = sum(w in hook_words for w in words)
        emphasis_hits = sum(w in emphasis for w in words)
        questions = text.count("?")
        exclamations = text.count("!")
        # Reward meaningful speech density without simply rewarding long transcripts.
        density = min(1.0, len(words) / max(1, (end-start) * 2.2))
        score = min(99, 38 + hook_hits*7 + emphasis_hits*5 + questions*4 + exclamations*2 + density*18)
        first_sentence = re.split(r"(?<=[.!?])\s+", text)[0][:100]
        title = first_sentence or "Interesting moment"
        candidates.append({"title": title, "start_time": start, "end_time": end, "score": int(score), "hook_sentence": first_sentence, "virality_reason": "Ranked using speech density, question cues, emphasis and hook vocabulary."})
    candidates.sort(key=lambda x: x["score"], reverse=True)
    selected=[]
    for c in candidates:
        if all(min(c["end_time"], x["end_time"])-max(c["start_time"],x["start_time"]) < .35*(c["end_time"]-c["start_time"]) for x in selected):
            selected.append(c)
        if len(selected)>=count: break
    return sorted(selected, key=lambda x:x["start_time"])


def render_clip(source, item, out_path, ratio):
    filters = {
        "9:16": "crop=ih*9/16:ih:(iw-ow)/2:0,scale=720:1280",
        "1:1": "crop=min(iw\\,ih):min(iw\\,ih):(iw-ow)/2:(ih-oh)/2,scale=720:720",
        "16:9": "crop=iw:iw*9/16:0:(ih-oh)/2,scale=1280:720",
    }
    cmd=["ffmpeg","-y","-ss",f"{item['start_time']:.2f}","-i",str(source),"-t",f"{item['end_time']-item['start_time']:.2f}","-vf",filters[ratio],"-c:v","libx264","-preset","veryfast","-crf","23","-c:a","aac","-b:a","128k","-movflags","+faststart",str(out_path)]
    result=subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1800:] or "FFmpeg could not render this clip.")


if st.button("✨ Generate my Shorts", type="primary", use_container_width=True, disabled=(uploaded is None and not video_url.strip())):
    try:
        with st.status("Preparing your video...", expanded=True) as status:
            source, workdir = get_video_path()
            st.write("Loading local Whisper transcription model...")
            from faster_whisper import WhisperModel
            model = WhisperModel(model_size, device="cpu", compute_type="int8", download_root=str(workdir / "models"))
            lang_map={"English":"en","Hindi":"hi","Spanish":"es","French":"fr","German":"de","Portuguese":"pt","Arabic":"ar","Japanese":"ja"}
            lang = lang_map.get(language_choice)
            st.write("Transcribing speech. First run may download the model files.")
            seg_iter, info = model.transcribe(str(source), language=lang, beam_size=3, vad_filter=True)
            segments=[{"start":float(s.start),"end":float(s.end),"text":s.text.strip()} for s in seg_iter]
            duration=float(getattr(info,"duration",0) or (segments[-1]["end"] if segments else 0))
            if not segments:
                raise RuntimeError("No speech was detected. Try another video or check its audio.")
            st.write(f"Transcribed {len(segments)} speech segments ({duration/60:.1f} minutes).")
            highlights=rank_highlights(segments,duration,clip_count,clip_length)
            if not highlights:
                raise RuntimeError("Could not find enough speech for clips. Try a longer video or a shorter target clip length.")
            ratio="9:16" if aspect.startswith("9:16") else ("1:1" if aspect.startswith("1:1") else "16:9")
            results=[]
            st.write("Rendering vertical clips with FFmpeg...")
            progress=st.progress(0)
            for i,h in enumerate(highlights,1):
                out=workdir/f"short_{i:02d}.mp4"
                render_clip(source,h,out,ratio)
                results.append((h,out))
                progress.progress(i/len(highlights))
            status.update(label="Your Shorts are ready!", state="complete", expanded=False)
        st.session_state["shorts_results"]=[(h,str(p)) for h,p in results]
        st.session_state["shorts_workdir"]=str(workdir)
    except Exception as e:
        st.error(f"Something went wrong: {e}")
        st.caption("Tip: For the most reliable free processing, run the app on your own computer. Free cloud hosting has limited memory and processing time.")

if st.session_state.get("shorts_results"):
    results=st.session_state["shorts_results"]
    st.divider(); st.subheader("2. Your generated Shorts")
    a,b=st.columns(2)
    a.metric("Clips created",len(results)); b.metric("Processing", "On-device / open source")
    for i,(h,path) in enumerate(results,1):
        st.markdown(f"#### Clip {i} · Score {h['score']}/99")
        st.write(h["title"])
        st.caption(f"{h['start_time']:.1f}s – {h['end_time']:.1f}s · {h['virality_reason']}")
        st.video(path)
        with open(path,"rb") as f:
            st.download_button(f"⬇️ Download Short {i}",data=f.read(),file_name=f"youtube_short_{i:02d}.mp4",mime="video/mp4",key=f"download_{i}")
        st.divider()
    st.caption("Highlight scores are heuristic estimates, not predictions of actual views or virality. Review each clip before publishing.")

st.markdown("<div style='text-align:center;color:gray;padding:1rem'>Free Shorts Studio · Open source · No API keys · No credits</div>",unsafe_allow_html=True)
