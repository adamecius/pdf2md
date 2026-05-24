# Plan 006: Semantic Layer Integration & Label Extension

## Status: DRAFT
## Date: 2026-05-24
## Depends on: Plan 005 (semantic backends installed and smoke-tested)

---

## 1. Goal

Integrate the three semantic backends into the `pdf2md` pipeline. Define the
CrossReferenceGraph schema. Extend labels/models to support semantic entity types.
Wire semantic backends into the profiler/router using the same Bayesian approach
as extraction backends.

## 2. Schema: CrossReferenceGraph (sidecar)

New dataclasses in `models.py`:

```python
class RefType(str, Enum):
    FIGURE = "figure"
    TABLE = "table"
    EQUATION = "equation"
    THEOREM = "theorem"
    DEFINITION = "definition"
    PROOF = "proof"
    COROLLARY = "corollary"
    EXAMPLE = "example"
    SECTION = "section"
    CHAPTER = "chapter"
    BIBLIOGRAPHY = "bibliography"
    FOOTNOTE = "footnote"

@dataclass
class RefMarker:
    source_ref: str               # JSON pointer to DocItem: "#/texts/42"
    marker_text: str              # Surface text: "Figure 3.2", "[15]", "†"
    marker_type: RefType
    char_offset: tuple[int, int]  # Span within source text
    confidence: float             # 1.0 for deterministic backends
    backend: str                  # "grobid" | "vlm" | "regex"

@dataclass
class RefEdge:
    marker: RefMarker
    target_ref: str | None        # JSON pointer to target: "#/pictures/7"
    resolved: bool
    resolution_method: str        # "exact" | "fuzzy" | "grobid_tei" | "unresolved"

@dataclass
class SemanticEntity:
    item_ref: str                 # JSON pointer to DocItem
    entity_type: RefType          # THEOREM, DEFINITION, PROOF, etc.
    label: str | None             # "Theorem 3.2"
    confidence: float
    backend: str

@dataclass
class CrossReferenceGraph:
    doc_hash: str                 # Links to DoclingDocument
    markers: list[RefMarker]
    edges: list[RefEdge]
    entities: list[SemanticEntity]
    backend_versions: dict[str, str]
```

Persisted as `cross_references.json` alongside DoclingDocument JSON.

## 3. Profiler extension

New signals computed from DoclingDocument (deterministic, no ML):

```python
has_bibliography: bool          # DOCUMENT_INDEX or text pattern detected
bibliography_style: str         # "numbered" | "author-year" | "footnote"
reference_density: float        # Regex-detected ref markers per page
has_toc: bool                   # Table of contents detected
chapter_count: int              # Estimated from section hierarchy depth
footnote_density: float         # FOOTNOTE items per page
```

These feed the router for semantic backend selection.

## 4. Router extension

No hardcoded paper/book routing. All semantic backends are candidates for all
documents. The router uses profiler signals + historical performance data:

```python
class SemanticStrategy(Enum):
    GROBID = "grobid"
    VLM = "vlm"
    REGEX = "regex"
    ENSEMBLE = "ensemble"       # Run multiple, merge results

def route_semantic(profile: DocumentProfile) -> list[SemanticStrategy]:
    """Returns ordered list of semantic backends to run."""
    # Initially: always ENSEMBLE (run all, collect data)
    # Over time: Bayesian selection based on GT benchmark results
```

## 5. Semantic backend adapter (unified interface)

```python
class SemanticBackend(ABC):
    @abstractmethod
    def extract(
        self,
        doc: DoclingDocument,
        pdf_path: Path,
        output_dir: Path,
    ) -> CrossReferenceGraph:
        ...

    @abstractmethod
    def name(self) -> str: ...
    @abstractmethod
    def version(self) -> str: ...
```

Each backend from Plan 004 gets wrapped in this interface.

## 6. Resolver

Deterministic module that takes detected RefMarkers and matches them to
DoclingDocument items:

- **Exact match**: "Figure 3" → search PictureItem captions for "Figure 3"
- **Fuzzy match**: "Fig. 3" / "fig. 3" / "Figure 3" → normalized lookup
- **Bibliography**: "[15]" → match against REFERENCE-labeled TextItems
- **Footnote**: superscript "3" → match against FOOTNOTE-labeled TextItems on same page
- **Cross-chapter**: "Chapter 5" → match against SECTION_HEADER with depth=0

Output: RefEdge list with resolution status.

## 7. Pipeline integration

```
CLI: python -m pdf2md --pdf input.pdf --output-dir out/

Existing flow:
  profiler → router → extraction backend → DoclingDocument

Extended flow:
  profiler → router → extraction backend → DoclingDocument
                  ↘
              semantic router → semantic backend(s) → CrossReferenceGraph
                                                          ↓
                                                      resolver
                                                          ↓
                                              cross_references.json
```

Both outputs land in the same output directory.

## 8. File changes

```
src/pdf2md/
├── models.py                    # Add RefType, RefMarker, RefEdge, etc.
├── profiler.py                  # Add semantic signals
├── router.py                    # Add semantic routing
├── semantic/
│   ├── __init__.py
│   ├── base.py                  # SemanticBackend ABC
│   ├── grobid_adapter.py        # Wraps backend/semantic/grobid/
│   ├── vlm_adapter.py           # Wraps backend/semantic/deepseek_vl2/
│   ├── regex_adapter.py         # Wraps backend/semantic/regex/
│   ├── resolver.py              # Marker → target resolution
│   └── ensemble.py              # Merge results from multiple backends
└── cli.py                       # Add --semantic flag
```

## 9. Acceptance criteria

- [ ] CrossReferenceGraph schema defined and serializable to/from JSON
- [ ] Profiler computes semantic signals for sample documents
- [ ] Each semantic backend wrapped in SemanticBackend interface
- [ ] Resolver matches markers to DoclingDocument items (exact + fuzzy)
- [ ] CLI produces `cross_references.json` alongside DoclingDocument
- [ ] Ensemble mode runs all backends and merges results
- [ ] No hardcoded paper/book routing — all backends available for all documents
