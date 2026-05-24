# Plan 007: Ground Truth, Evaluation & Example

## Status: DRAFT
## Date: 2026-05-24
## Depends on: Plan 006 (semantic layer integrated)

---

## 1. Goal

Build the ground truth pipeline from LaTeX sources, create an evaluation harness
to benchmark semantic backends, and produce a worked example demonstrating the
full pipeline from PDF to cross-reference graph.

## 2. GT pipeline: .tex → LaTeXML → CrossReferenceGraph

```
author.tex ──compile──→ author.pdf    (extraction target)
     │
     └──── LaTeXML ───→ author.tei.xml (ground truth)
                              │
                         TEI parser ──→ gt_cross_references.json
```

### 2.1 LaTeX corpus design

Controlled `.tex` documents that exercise all cross-reference types:

```
groundtruth/semantic/
├── article_simple/          # Few refs, numbered bibliography
│   ├── article.tex
│   ├── article.pdf
│   └── gt_cross_references.json
├── article_complex/         # Dense refs, author-year, footnotes
│   ├── article.tex
│   ├── article.pdf
│   └── gt_cross_references.json
├── book_chapter/            # Chapter structure, cross-chapter refs
│   ├── book.tex
│   ├── book.pdf
│   └── gt_cross_references.json
└── textbook_math/           # Theorems, definitions, equation refs
    ├── textbook.tex
    ├── textbook.pdf
    └── gt_cross_references.json
```

Each `.tex` includes at minimum:
- 3+ `\ref{}` to figures/tables/equations
- 5+ `\cite{}` to bibliography entries
- 2+ `\footnote{}`
- For books: cross-chapter `\ref{}`
- For math: `\label{thm:...}` / `\label{def:...}` with `\ref{}`

### 2.2 LaTeXML → TEI → GT parser

```python
def generate_gt(tex_path: Path, output_dir: Path) -> CrossReferenceGraph:
    """
    1. Run LaTeXML on .tex → TEI XML
    2. Parse TEI: extract all <ref>, <note>, <bibl> with targets
    3. Build CrossReferenceGraph with confidence=1.0, backend="ground_truth"
    """
```

LaTeXML preserves `\ref` → `<ref target="#id">`, `\cite` → `<ref target="#bib_id">`,
`\footnote` → `<note>` with anchors. All links are resolved — no ambiguity.

### 2.3 LaTeXML installation

```bash
# Perl-based, available via package managers
sudo apt-get install latexml    # Ubuntu
# or
cpanm LaTeXML                   # CPAN
```

No conda env needed. CLI tool: `latexml input.tex --dest=output.xml`

## 3. Evaluation harness

### 3.1 Metrics

```python
@dataclass
class SemanticEvalResult:
    # Marker detection
    marker_precision: float       # Detected markers that are real
    marker_recall: float          # Real markers that were detected
    marker_f1: float
    marker_f1_by_type: dict[RefType, float]  # Breakdown per type

    # Resolution accuracy
    resolution_accuracy: float    # Of detected markers, % linked correctly
    resolution_accuracy_by_type: dict[RefType, float]

    # Entity classification
    entity_precision: float
    entity_recall: float
    entity_f1: float

    # Per-backend breakdown
    backend: str
    document_id: str
```

### 3.2 Comparison logic

```python
def evaluate_semantic(
    extracted: CrossReferenceGraph,
    ground_truth: CrossReferenceGraph,
) -> SemanticEvalResult:
    """
    1. Align extracted markers to GT markers (by char_offset overlap)
    2. Compute precision/recall for detection
    3. For aligned markers, check if target_ref matches
    4. Compute resolution accuracy
    """
```

### 3.3 Benchmark runner

```bash
python -m pdf2md.eval.semantic_benchmark \
    --gt-dir groundtruth/semantic/ \
    --backends grobid,vlm,regex,ensemble \
    --output-dir results/semantic/
```

Produces:
- Per-document per-backend scores
- Aggregate comparison table
- CSV export for further analysis

## 4. Worked example

```
examples/semantic_cross_references/
├── README.md                    # Step-by-step walkthrough
├── input/
│   └── sample_article.pdf       # Article with cross-references
├── run.sh                       # Full pipeline: extract + semantic + eval
├── expected_output/
│   ├── docling_document.json    # Structural layer
│   ├── cross_references.json    # Semantic layer
│   └── eval_results.json        # Evaluation against GT
└── gt/
    ├── sample_article.tex       # Source
    └── gt_cross_references.json # Ground truth
```

The README walks through:
1. Running extraction → DoclingDocument
2. Running semantic backends → CrossReferenceGraph
3. Inspecting detected markers and resolved edges
4. Comparing against GT with the evaluation harness
5. Interpreting per-backend performance

## 5. Acceptance criteria

- [ ] ≥4 controlled `.tex` documents with diverse cross-reference patterns
- [ ] LaTeXML → TEI → CrossReferenceGraph parser produces valid GT
- [ ] Evaluation harness computes precision/recall/F1 per RefType per backend
- [ ] Benchmark runner produces comparison table across all backends
- [ ] Worked example runs end-to-end and produces documented output
- [ ] Results show meaningful differentiation between backends
