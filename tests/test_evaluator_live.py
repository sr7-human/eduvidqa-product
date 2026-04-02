#!/usr/bin/env python3
"""Integration test for QualityEvaluator with HF Inference API."""
import time
from pipeline.evaluate import QualityEvaluator

question = "How does backpropagation work in neural networks?"
answer = (
    "Backpropagation is a crucial technique used in training neural networks. "
    "Let me break it down step-by-step:\n\n"
    "Step 1: Forward Pass - The network makes predictions based on its inputs, "
    "processing data through several layers.\n\n"
    "Step 2: Calculate Loss - We compare the prediction to the actual output "
    "using a loss function like mean squared error.\n\n"
    "Step 3: Compute Gradient - Using the chain rule of calculus, we calculate "
    "how much each weight contributed to the error.\n\n"
    "Step 4: Propagate Error Backward - Starting from the output layer, we move "
    "towards the input layer, adjusting weights based on gradients.\n\n"
    "Step 5: Update Weights - Using gradient descent, we adjust weights to "
    "minimize the loss function.\n\n"
    "Think of it like baking a cake that tastes bad - you trace back to find "
    "which step caused the problem. Backpropagation is this systematic "
    "blame-tracing process."
)

print("Testing QualityEvaluator (hf_inference)...")
print(f"Question: {question[:50]}...")
print(f"Answer: {len(answer)} chars")
print()

t0 = time.time()
evaluator = QualityEvaluator(method="hf_inference")
scores = evaluator.score(question, answer)
elapsed = time.time() - t0

print(f"Clarity: {scores.clarity}/5")
print(f"ECT:     {scores.ect}/5")
print(f"UPT:     {scores.upt}/5")
print(f"Time:    {elapsed:.1f}s")
print()
assert 1 <= scores.clarity <= 5
assert 1 <= scores.ect <= 5
assert 1 <= scores.upt <= 5
print("All assertions passed — PASS")
