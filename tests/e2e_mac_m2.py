#!/usr/bin/env python3
"""End-to-end test: Load Qwen2.5-VL on Mac M2 and generate a real answer.

Usage:
    python3 tests/e2e_mac_m2.py

Uses Qwen2.5-VL-3B-Instruct for local dev (fits in 16GB).
The 7B model is for GPU environments (Kaggle/HF Spaces).
"""

from __future__ import annotations

import gc
import sys
import time

import torch


def main() -> None:
    print("=" * 60)
    print("EduVidQA Session C — E2E Mac M2 Test")
    print("=" * 60)

    # ── 1. Hardware check ─────────────────────────────────────────
    device = "cpu"
    dtype = torch.float32
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
        dtype = torch.float16
        print(f"✓ MPS (Apple Silicon) available — using float16")
    else:
        print("⚠ MPS not available — falling back to CPU float32 (slow)")

    # ── 2. Model selection ────────────────────────────────────────
    # 3B fits comfortably on 16GB Mac; 7B is too tight without 4-bit
    MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
    print(f"\nLoading {MODEL_ID} on {device}...")
    t0 = time.perf_counter()

    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL_ID,
        torch_dtype=dtype,
        device_map=device,
    )
    model.eval()

    load_time = time.perf_counter() - t0
    param_count = sum(p.numel() for p in model.parameters()) / 1e9
    print(f"✓ Model loaded in {load_time:.1f}s ({param_count:.1f}B params)")

    # ── 3. Create a test image (simple gradient) ──────────────────
    from PIL import Image
    import numpy as np

    # Create a simple "whiteboard" test image
    img = Image.fromarray(
        np.full((224, 224, 3), 240, dtype=np.uint8)  # light gray
    )
    test_frame_path = "/tmp/eduvidqa_test_frame.jpg"
    img.save(test_frame_path)
    print(f"✓ Test frame saved to {test_frame_path}")

    # ── 4. Build prompt (using our pipeline code) ─────────────────
    sys.path.insert(0, ".")
    from pipeline.models import RetrievedContext, RetrievalResult, VideoSegment
    from pipeline.prompts import build_answer_prompt

    retrieval_result = RetrievalResult(
        query="How does backpropagation work in neural networks?",
        video_id="test_e2e",
        contexts=[
            RetrievedContext(
                segment=VideoSegment(
                    video_id="test_e2e",
                    segment_index=0,
                    start_time=120,
                    end_time=240,
                    transcript_text=(
                        "Backpropagation is the core algorithm for training neural networks. "
                        "It works by computing the gradient of the loss function with respect to "
                        "each weight in the network, using the chain rule of calculus. First, we "
                        "do a forward pass to compute the predicted output. Then we calculate the "
                        "loss — the difference between predicted and actual output. Finally, we "
                        "propagate the error backwards through each layer, computing how much each "
                        "weight contributed to the error, and adjust the weights accordingly."
                    ),
                    frame_paths=[test_frame_path],
                ),
                relevance_score=0.95,
                rank=1,
            ),
            RetrievedContext(
                segment=VideoSegment(
                    video_id="test_e2e",
                    segment_index=1,
                    start_time=240,
                    end_time=360,
                    transcript_text=(
                        "The key insight of backpropagation is the chain rule. If you have a "
                        "composition of functions, f(g(x)), the derivative of the whole thing is "
                        "f'(g(x)) times g'(x). In a neural network, each layer is a function, "
                        "so the gradient flows backwards through each layer using this rule. This "
                        "is why it's called 'back' propagation — the gradient flows from the output "
                        "layer back to the input layer."
                    ),
                    frame_paths=[],
                ),
                relevance_score=0.88,
                rank=2,
            ),
        ],
        total_segments=10,
    )

    messages = build_answer_prompt(
        retrieval_result.query, retrieval_result.contexts
    )
    print(f"✓ Prompt built: {len(messages)} messages")

    # ── 5. Run inference ──────────────────────────────────────────
    print("\nGenerating answer (this may take 1-3 minutes on MPS)...")

    text_prompt = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    from qwen_vl_utils import process_vision_info

    image_inputs, video_inputs = process_vision_info(messages)

    inputs = processor(
        text=[text_prompt],
        images=image_inputs or None,
        videos=video_inputs or None,
        padding=True,
        return_tensors="pt",
    ).to(model.device)

    input_tokens = inputs["input_ids"].shape[1]
    print(f"  Input tokens: {input_tokens}")

    t0 = time.perf_counter()
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=512,  # shorter for speed on local test
            temperature=0.3,
            do_sample=True,
        )
    gen_time = time.perf_counter() - t0

    generated_ids = output_ids[:, inputs["input_ids"].shape[1] :]
    output_tokens = generated_ids.shape[1]
    answer = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()

    tokens_per_sec = output_tokens / gen_time

    # ── 6. Print results ──────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"ANSWER ({len(answer)} chars, {output_tokens} tokens):")
    print(f"{'─' * 60}")
    print(answer)
    print(f"{'─' * 60}")
    print(f"⏱  Generation: {gen_time:.1f}s")
    print(f"📊 Speed: {tokens_per_sec:.1f} tokens/sec")
    print(f"📊 Input: {input_tokens} tokens, Output: {output_tokens} tokens")

    # ── 7. Validate ───────────────────────────────────────────────
    passed = True
    if len(answer) < 50:
        print("✗ FAIL: Answer too short (< 50 chars)")
        passed = False
    else:
        print("✓ Answer length OK")

    if any(kw in answer.lower() for kw in ["gradient", "chain rule", "backprop", "loss", "weight"]):
        print("✓ Answer references key concepts from transcript")
    else:
        print("⚠ Answer may not reference transcript content")

    # ── 8. Cleanup ────────────────────────────────────────────────
    del model, processor, inputs, output_ids
    if device == "mps":
        torch.mps.empty_cache()
    gc.collect()
    print("\n✓ Memory freed")

    # ── Summary ───────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"SUMMARY")
    print(f"  Model:     {MODEL_ID}")
    print(f"  Device:    {device} ({dtype})")
    print(f"  Load time: {load_time:.1f}s")
    print(f"  Gen time:  {gen_time:.1f}s ({tokens_per_sec:.1f} tok/s)")
    print(f"  Answer:    {len(answer)} chars, {output_tokens} tokens")
    print(f"  Status:    {'PASS' if passed else 'FAIL'}")
    print(f"{'=' * 60}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
