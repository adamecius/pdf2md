# Backend Matrix for Robust Offline Processing

This project should not choose one permanent backend. It should orchestrate several.

## Priority view

| Tier | Backend | Role | Why it matters |
|---|---|---|---|
| 0 | deterministic PyMuPDF | Always-on baseline | Fast, cheap, transparent, good for clean text layers |
| 1 | Docling | Structural baseline | Mature document representation, chunking and exporters |
| 2 | MinerU / MinerU2.5 | Strong all-in-one parser | Excellent target for scientific documents and books |
| 3 | PaddleOCR-VL-1.5 | Compact visual parser | Strong OCR, tables, formulas, scanned pages |
| 3 | GLM-OCR | Strong visual OCR/parser | Good candidate for high-quality local GPU parsing |
| 3 | dots.ocr | Structured visual extraction | Natural fit for bbox, Markdown, LaTeX and HTML outputs |
| 3 | FireRed-OCR | Additional visual candidate | Improves robustness through backend diversity |
| 4 | Marker | PDF-to-Markdown baseline | Useful comparison for Markdown and chunking |
| 4 | olmOCR | OCR and linearisation baseline | Useful for long document and OCR comparisons |
| 4 | PaddleOCR PP-StructureV3 | Classical OCR/layout/table fallback | Useful as component baseline |
| 5 | Tesseract | Minimal OCR fallback | Slow/limited but useful for sanity checks |

## Recommended integration order

1. deterministic backend emits DocIR
2. Docling backend adapter
3. MinerU backend adapter
4. PaddleOCR-VL backend adapter
5. GLM-OCR backend adapter
6. dots.ocr backend adapter
7. FireRed-OCR backend adapter
8. Marker and olmOCR comparison adapters

## Why Docling early

Docling is useful even if it is not the highest scoring visual parser because its architecture is close to the desired DocIR model.

It can validate whether the internal representation is expressive enough.

## Why MinerU early

Since commercial licensing is not a blocker for this offline use case, MinerU can be treated as a high-priority leading backend.

It should be integrated after the backend interface exists, not before.

## Why PaddleOCR-VL early

PaddleOCR-VL-1.5 is compact enough to be practical and strong enough to be useful for visual parsing.

It is a good first GPU-backed visual parser.

## Why GLM-OCR and dots.ocr

GLM-OCR and dots.ocr are attractive because they can produce strong visual extraction and are aligned with structured output.

dots.ocr is especially interesting if its output includes categories, boxes and markup-like content.

## Backend output requirement

Every backend must produce or be converted into:

```text
DocumentIR
PageIR
BlockIR
MediaRef
Provenance
```

Raw backend output must be preserved.

## Do not compare backends only by Markdown

Backends should be compared by:

- text extraction
- reading order
- layout structure
- table structure
- formula quality
- figure and caption association
- RAG chunk quality
- runtime
- failure rate
- memory use
- page-level robustness
