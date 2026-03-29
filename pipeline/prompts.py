"""Prompt templates for Qwen2.5-VL answer generation and quality evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipeline.models import RetrievedContext

SYSTEM_PROMPT = (
    "You are an expert AI teaching assistant helping students understand lecture videos.\n"
    "Your answers must be:\n"
    "1. CLEAR — explain every technical term, use simple language, logical flow\n"
    "2. COMPLETE — cover the concept fully using the provided lecture context\n"
    "3. PEDAGOGICAL — use examples, analogies, step-by-step breakdowns where helpful\n"
    "4. ACCURATE — only state facts supported by the lecture content provided\n\n"
    "You have access to the lecture transcript and video frames around the student's question."
)

MAX_FRAMES_PER_SEGMENT = 3
MAX_TOTAL_FRAMES = 15


def build_answer_prompt(
    question: str,
    contexts: list[RetrievedContext],
) -> list[dict]:
    """Build the multimodal prompt for Qwen2.5-VL.

    Returns a list of message dicts in the chat format Qwen2.5-VL expects:
    [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",  "content": [mixed text + image items]}
    ]
    """
    user_content: list[dict] = []

    # -- lecture context (transcripts + frames) --------------------------------
    user_content.append(
        {"type": "text", "text": "Here is the relevant lecture context:\n"}
    )

    total_frames_added = 0

    for ctx in contexts:
        seg = ctx.segment
        header = (
            f"\n--- Segment {ctx.rank} (relevance {ctx.relevance_score:.2f}, "
            f"{seg.start_time:.0f}s – {seg.end_time:.0f}s) ---\n"
        )
        user_content.append({"type": "text", "text": header})
        user_content.append({"type": "text", "text": seg.transcript_text})

        # Add frames (up to MAX_FRAMES_PER_SEGMENT per segment, MAX_TOTAL_FRAMES overall)
        frames_to_add = seg.frame_paths[:MAX_FRAMES_PER_SEGMENT]
        for frame_path in frames_to_add:
            if total_frames_added >= MAX_TOTAL_FRAMES:
                break
            user_content.append({"type": "image", "image": f"file://{frame_path}"})
            total_frames_added += 1

    # -- student question ------------------------------------------------------
    user_content.append(
        {"type": "text", "text": f"\n\nStudent question: {question}"}
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


EVAL_PROMPT_TEMPLATE = (
    "Rate the following answer on a scale of 1-5 for each quality:\n\n"
    "Question: {question}\n"
    "Answer: {answer}\n\n"
    "Rate EACH on 1-5:\n"
    "1. Clarity (1=jargon-filled, incoherent → 5=crystal clear, logical, beginner-friendly)\n"
    "2. ECT - Encouraging Critical Thinking "
    "(1=purely factual → 5=poses follow-ups, discusses alternatives)\n"
    "3. UPT - Uses Pedagogical Techniques "
    "(1=no examples → 5=rich examples, analogies, step-by-step)\n\n"
    'Return JSON only: {{"clarity": X, "ect": X, "upt": X}}'
)
