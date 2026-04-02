"""EduVidQA — Gradio UI for HuggingFace Spaces deployment."""

import os
import gradio as gr

# Ensure .env is loaded
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from pipeline.ingest import ingest_video, parse_video_id
from pipeline.rag import LectureIndex
from pipeline.inference_groq import GroqInference
from pipeline.evaluate import QualityEvaluator

# Globals
_index = LectureIndex(persist_dir="./data/chroma")
_engine = GroqInference()

try:
    _evaluator = QualityEvaluator(method="hf_inference")
except Exception:
    _evaluator = None


async def answer_question(youtube_url: str, timestamp_str: str, question: str):
    """Full pipeline: URL + timestamp + question → AI answer."""
    if not youtube_url or not question:
        return "❌ Please enter a YouTube URL and a question.", "", "", ""

    # Parse timestamp
    try:
        parts = timestamp_str.strip().split(":")
        if len(parts) == 2:
            timestamp = int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 1:
            timestamp = int(parts[0])
        else:
            timestamp = 0
    except (ValueError, IndexError):
        timestamp = 0

    # Parse video ID
    try:
        video_id = parse_video_id(youtube_url)
    except ValueError as e:
        return f"❌ Invalid URL: {e}", "", "", ""

    # Ingest if needed
    if not _index.is_indexed(video_id):
        try:
            result = await ingest_video(youtube_url, output_dir="./data")
            _index.index_segments(result.segments)
        except Exception as e:
            return f"❌ Failed to process video: {e}", "", "", ""

    # Retrieve
    try:
        retrieval = _index.retrieve(question, video_id, top_k=5)
    except Exception as e:
        return f"❌ Retrieval failed: {e}", "", "", ""

    # Generate answer
    try:
        answer_result = _engine.generate_answer(retrieval)
    except Exception as e:
        return f"❌ Inference failed: {e}", "", "", ""

    # Quality scores
    quality_text = ""
    if _evaluator:
        try:
            scores = _evaluator.score(question, answer_result.answer)
            quality_text = f"Clarity: {scores.clarity}/5  |  ECT: {scores.ect}/5  |  UPT: {scores.upt}/5"
        except Exception:
            quality_text = "⚠️ Scoring unavailable"

    # Sources
    sources_text = "\n".join(
        f"📎 {int(s['start_time']//60)}:{int(s['start_time']%60):02d} – "
        f"{int(s['end_time']//60)}:{int(s['end_time']%60):02d} "
        f"(relevance: {s['relevance_score']:.0%})"
        for s in answer_result.sources
    )

    meta = f"Model: {answer_result.model_name}  |  Time: {answer_result.generation_time_seconds}s"

    return answer_result.answer, quality_text, sources_text, meta


# Build Gradio Interface
with gr.Blocks(
    title="EduVidQA — AI Teaching Assistant",
    theme=gr.themes.Base(primary_hue="indigo", neutral_hue="slate"),
    css="""
    .gradio-container { max-width: 800px !important; }
    footer { display: none !important; }
    """
) as demo:
    gr.Markdown(
        """
        # 🎓 EduVidQA — AI Teaching Assistant
        **Ask questions about any YouTube lecture video and get AI-powered educational answers.**

        Based on the [EduVidQA paper](https://sr7-human.github.io/eduvidqa-explained/) (EMNLP 2025).
        Uses RAG (BGE-M3 + ChromaDB) + Llama 3.3 70B (via Groq) for answer generation.
        """
    )

    with gr.Row():
        url_input = gr.Textbox(
            label="YouTube URL",
            placeholder="https://www.youtube.com/watch?v=...",
            scale=3,
        )
        ts_input = gr.Textbox(
            label="Timestamp (MM:SS)",
            placeholder="3:01",
            scale=1,
        )

    question_input = gr.Textbox(
        label="Your Question",
        placeholder="What concept is being explained at this point?",
        lines=3,
    )

    ask_btn = gr.Button("🔍 Ask Question", variant="primary", size="lg")

    answer_output = gr.Markdown(label="Answer")

    with gr.Row():
        quality_output = gr.Textbox(label="Quality Scores", interactive=False)
        meta_output = gr.Textbox(label="Model Info", interactive=False)

    sources_output = gr.Textbox(label="Sources (lecture segments used)", interactive=False, lines=3)

    ask_btn.click(
        fn=answer_question,
        inputs=[url_input, ts_input, question_input],
        outputs=[answer_output, quality_output, sources_output, meta_output],
    )

    gr.Examples(
        examples=[
            ["https://www.youtube.com/watch?v=g-Hb26agBFg", "3:01", "What formula is being shown? Explain it to me."],
            ["https://www.youtube.com/watch?v=aircAruvnKk", "2:00", "What is a neural network and how does it learn?"],
        ],
        inputs=[url_input, ts_input, question_input],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=True)
