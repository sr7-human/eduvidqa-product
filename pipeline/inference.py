"""Qwen2.5-VL-7B inference engine for educational answer generation."""

from __future__ import annotations

import logging
import platform
import time

import torch
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

from pipeline.models import AnswerResult, RetrievalResult
from pipeline.prompts import build_answer_prompt

logger = logging.getLogger(__name__)

MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"


def _detect_device() -> tuple[str, torch.dtype]:
    """Return (device_str, dtype) based on available hardware."""
    if torch.cuda.is_available():
        return "cuda", torch.float16
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps", torch.float16
    return "cpu", torch.float32


class QwenInference:
    """Qwen2.5-VL-7B inference engine."""

    def __init__(
        self,
        model_name: str = MODEL_ID,
        quantize_4bit: bool = True,
    ) -> None:
        self.model_name = model_name
        device, dtype = _detect_device()
        self._device = device

        logger.info("Loading %s on %s (4-bit=%s)", model_name, device, quantize_4bit)

        load_kwargs: dict = {"torch_dtype": dtype}

        if quantize_4bit and device == "cuda":
            from transformers import BitsAndBytesConfig

            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
            load_kwargs["device_map"] = "auto"
        elif device == "mps":
            load_kwargs["device_map"] = "mps"
        elif device == "cpu":
            load_kwargs["device_map"] = "cpu"
        else:
            load_kwargs["device_map"] = "auto"

        self.processor = AutoProcessor.from_pretrained(model_name)
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model_name, **load_kwargs
        )
        self.model.eval()
        logger.info("Model loaded successfully on %s", device)

    # --------------------------------------------------------------------- #

    def generate_answer(
        self,
        retrieval_result: RetrievalResult,
        max_new_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> AnswerResult:
        """Generate an educational answer from retrieved context."""
        messages = build_answer_prompt(
            retrieval_result.query,
            retrieval_result.contexts,
        )

        # Qwen2.5-VL processor expects the chat template applied
        text_prompt = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        # Collect image inputs from the messages
        from qwen_vl_utils import process_vision_info

        image_inputs, video_inputs = process_vision_info(messages)

        inputs = self.processor(
            text=[text_prompt],
            images=image_inputs or None,
            videos=video_inputs or None,
            padding=True,
            return_tensors="pt",
        ).to(self.model.device)

        t0 = time.perf_counter()
        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
            )
        elapsed = time.perf_counter() - t0

        # Decode only the generated tokens (skip the input prefix)
        generated_ids = output_ids[:, inputs["input_ids"].shape[1] :]
        answer_text = self.processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0].strip()

        sources = [
            {
                "start_time": ctx.segment.start_time,
                "end_time": ctx.segment.end_time,
                "relevance_score": ctx.relevance_score,
            }
            for ctx in retrieval_result.contexts
        ]

        return AnswerResult(
            question=retrieval_result.query,
            answer=answer_text,
            video_id=retrieval_result.video_id,
            sources=sources,
            quality_scores=None,
            model_name=self.model_name,
            generation_time_seconds=round(elapsed, 2),
        )

    # --------------------------------------------------------------------- #

    def unload(self) -> None:
        """Free GPU/MPS memory."""
        del self.model
        del self.processor
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        import gc

        gc.collect()
        logger.info("Model unloaded, memory freed.")
