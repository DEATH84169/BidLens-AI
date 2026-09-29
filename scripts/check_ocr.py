"""Real OCR smoke check; run on a host with ONNX Runtime native prerequisites."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from orchestrator.ai_processing import extract_document_data

sample = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "sample_bids"
    / "Scanned_Letter_ApexLabs.png"
)
result = extract_document_data(str(sample))
if result["unread_pages"] or not result["raw_text"].strip():
    raise SystemExit(
        "OCR smoke check failed. Check ONNX Runtime native prerequisites; unread pages must remain review findings."
    )
print(
    f"OCR passed: {result['page_count']} page(s), {len(result['raw_text'])} extracted characters."
)
