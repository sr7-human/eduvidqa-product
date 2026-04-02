"""Generate sorting video digest using Gemini Flash (Groq is rate-limited)."""
import json, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types

client = genai.Client(api_key="GEMINI_KEY_REDACTED")
DATA_DIR = "data/processed"
vid = "oZgbwa8lvDE"

transcript = (Path(DATA_DIR) / vid / "transcript" / "full.txt").read_text()
manifest = json.loads((Path(DATA_DIR) / vid / "keyframes" / "manifest.json").read_text())
manifest.sort(key=lambda x: x.get("timestamp", 0))

# Pick ~10 evenly spaced keyframes
step = max(1, len(manifest) // 10)
selected = manifest[::step][:10]
print(f"Using {len(selected)} keyframes out of {len(manifest)}")

prompt = """Create a detailed, comprehensive digest of this entire lecture.

This is NOT a summary — do NOT shorten or condense. Capture ALL:
- Key concepts explained
- Formulas, code, algorithms shown
- Diagrams and visual content described from the frames
- Examples given by the professor
- Important definitions and terminology

TRANSCRIPT:
""" + transcript + "\n\nLECTURE FRAMES (sampled):"

contents = [prompt]
for kf in selected:
    p = Path(kf["file"])
    if p.is_file():
        contents.append(types.Part.from_bytes(data=p.read_bytes(), mime_type="image/jpeg"))

resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=contents,
    config=types.GenerateContentConfig(max_output_tokens=8192, temperature=0.3),
)
digest = resp.text.strip()
print(f"Digest generated: {len(digest)} chars")

out = Path(DATA_DIR) / vid / "digest.txt"
out.write_text(digest, encoding="utf-8")
print(f"Saved to {out}")
print(digest[:400] + "...")
