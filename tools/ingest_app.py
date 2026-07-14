"""EduVidQA — Local Admin Ingest UI.

Launch:  ./.venv/bin/streamlit run tools/ingest_app.py
(or just double-click "Ingest Videos.command" in the project root)

Runs entirely on your Mac (residential IP → reliable) and writes to the live
production database, so ingested videos appear globally in the app.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os  # noqa: E402

import streamlit as st  # noqa: E402

from local_ingest import (  # noqa: E402
    clear_downloads,
    downloads_size_mb,
    expand_playlist,
    ingest_one,
    is_playlist,
    resolve_admin_user_id,
)
from pipeline.ingest import parse_video_id  # noqa: E402
from pipeline.video_quality import (  # noqa: E402
    DEFAULT_TYPE,
    QUALITY_PRESETS,
    suggest_video_type,
)

st.set_page_config(page_title="EduVidQA — Local Ingest", page_icon="🎓", layout="centered")

st.title("🎓 EduVidQA — Local Ingest")
st.caption(
    "Runs on your Mac (reliable — bypasses the YouTube block on the server). "
    "Writes to the live database, so videos appear globally in the app."
)

# ── Storage cleanup ───────────────────────────────────────────────
with st.sidebar:
    st.header("🗑️ Storage")
    mb = downloads_size_mb()
    st.write(f"Downloaded-video cache: **{mb:.0f} MB**")
    st.caption("Videos here are temporary and re-downloadable. Safe to clear anytime.")
    if st.button("Clear downloaded videos", disabled=mb < 0.1, use_container_width=True):
        freed = clear_downloads()
        st.success(f"Freed {freed:.0f} MB")
        st.rerun()

user_id = resolve_admin_user_id()
if user_id:
    st.success(f"Target library: admin ({user_id[:8]}…)")
else:
    st.warning("No ADMIN_EMAILS set — videos will ingest but won't be linked to a library.")

url = st.text_input(
    "YouTube video or playlist URL",
    placeholder="https://www.youtube.com/watch?v=…  or  …&list=…",
)

# ── Video type / keyframe quality (per-playlist) ──────────────────
_TYPE_KEYS = list(QUALITY_PRESETS.keys())

if "video_type" not in st.session_state:
    st.session_state.video_type = DEFAULT_TYPE
# Apply a pending AI suggestion BEFORE the widget is created (Streamlit rule).
if st.session_state.get("_suggested_type"):
    st.session_state.video_type = st.session_state.pop("_suggested_type")

col_sel, col_ai = st.columns([3, 1])
with col_sel:
    video_type = st.selectbox(
        "Video type (keyframe quality)",
        _TYPE_KEYS,
        format_func=lambda k: QUALITY_PRESETS[k]["label"],
        key="video_type",
        help="Higher resolution = sharper on-screen text, but more storage. "
             "This choice applies to every video in the playlist.",
    )
with col_ai:
    st.write("")
    st.write("")
    if st.button("🤖 Suggest", disabled=not url.strip(), use_container_width=True,
                 help="Sample a few frames and let AI guess the best setting."):
        try:
            _vid = parse_video_id(url)
        except Exception:
            _vid = None
        if is_playlist(url):
            try:
                _vids = expand_playlist(url)
                _vid = _vids[0] if _vids else _vid
            except Exception:
                pass
        if _vid:
            with st.spinner("Looking at the video…"):
                key, note = suggest_video_type(_vid, os.getenv("GROQ_API_KEY") or None)
            st.session_state["_suggested_type"] = key
            st.session_state["_suggest_note"] = note
            st.rerun()
        else:
            st.warning("Enter a valid video URL first.")

st.caption(f"📐 {QUALITY_PRESETS[video_type]['help']}")
if st.session_state.get("_suggest_note"):
    st.caption(f"🤖 {st.session_state.pop('_suggest_note')}")

st.caption(
    "💡 Playlists ingest one-by-one. If it stops (quota/limit), just run the **same "
    "playlist again later** — already-done videos are skipped automatically (resume)."
)

if st.button("🚀 Ingest", type="primary", disabled=not url.strip()):
    if is_playlist(url):
        with st.spinner("Reading playlist…"):
            try:
                vids = expand_playlist(url)
            except Exception as e:
                st.error(f"Couldn't read playlist: {e}")
                st.stop()
        st.info(f"Playlist has **{len(vids)}** videos. Ingesting one by one…")
        prog = st.progress(0.0)
        done = skipped = failed = 0
        for i, vid in enumerate(vids, 1):
            with st.status(f"[{i}/{len(vids)}] {vid}", expanded=False) as status:
                res = ingest_one(vid, user_id, log=status.write, video_type=video_type)
                if res["status"] == "ready":
                    if res.get("skipped"):
                        skipped += 1
                        status.update(label=f"⏭️ [{i}/{len(vids)}] {res['title'][:55]} (already done)", state="complete")
                    else:
                        done += 1
                        status.update(label=f"✅ [{i}/{len(vids)}] {res['title'][:55]}", state="complete")
                else:
                    failed += 1
                    status.update(label=f"❌ [{i}/{len(vids)}] {vid} — {str(res.get('error',''))[:60]}", state="error")
            prog.progress(i / len(vids))
        st.success(f"Playlist finished — {done} new, {skipped} skipped, {failed} failed.")
        if failed:
            st.info("Some failed (often a daily API/quota limit). Re-run the same playlist later to resume — done videos are skipped.")
    else:
        with st.status("Ingesting…", expanded=True) as status:
            res = ingest_one(url, user_id, log=status.write, video_type=video_type)
            if res["status"] == "ready":
                status.update(label=f"✅ {res['title']}", state="complete")
                if res.get("skipped"):
                    st.info("Already ingested — re-linked to your library.")
                else:
                    st.success(f"Done — {res['chunks']} chunks, {res['keyframes']} keyframes. Refresh your library!")
            else:
                status.update(label="❌ Failed", state="error")
                st.error(res.get("error"))
