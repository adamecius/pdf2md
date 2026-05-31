from pdf2md.connectors.common import markdown_to_pages, recognize_entities
from pdf2md.models.entities import EntityType
from pdf2md.models.ir import BlockKind


def _doc(markdown: str):
    warnings: list[str] = []
    pages = markdown_to_pages(
        markdown,
        backend="mineru",
        backend_version=None,
        document_id="doc",
        raw_ref="output.md",
        warnings=warnings,
    )
    return recognize_entities(
        pages,
        backend="mineru",
        backend_version=None,
        document_id="doc",
        warnings=warnings,
    )


def _theorem_entities(markdown: str):
    family = {
        EntityType.THEOREM,
        EntityType.DEFINITION,
        EntityType.COROLLARY,
        EntityType.PROOF,
        EntityType.EXAMPLE,
    }
    return [entity for entity in _doc(markdown).entities if entity.entity_type in family]


def test_detects_theorem_family_paragraphs_with_expected_types_and_numbers() -> None:
    markdown = "\n\n".join(
        [
            "**Theorem 3.2.** Let X be a finite group...",
            "Definition 1. A topological space...",
            "Corollary 3.2. It follows...",
            "Proof. We proceed by induction...",
            "Example 4. Consider...",
            "Lemma 2.1. For all n...",
            "Remark. Note that...",
        ]
    )

    entities = _theorem_entities(markdown)

    observed = [
        (
            entity.entity_type,
            entity.metadata.get("theorem_number"),
            entity.metadata.get("theorem_kind"),
        )
        for entity in entities
    ]
    assert observed == [
        (EntityType.THEOREM, "3.2", "Theorem"),
        (EntityType.DEFINITION, "1", "Definition"),
        (EntityType.COROLLARY, "3.2", "Corollary"),
        (EntityType.PROOF, None, "Proof"),
        (EntityType.EXAMPLE, "4", "Example"),
        (EntityType.THEOREM, "2.1", "Lemma"),
        (EntityType.EXAMPLE, None, "Remark"),
    ]


def test_detects_theorem_family_heading_blocks() -> None:
    pages = markdown_to_pages(
        "# Theorem 5.1\n\nBody text.",
        backend="mineru",
        backend_version=None,
        document_id="doc",
        raw_ref="output.md",
        warnings=[],
    )
    assert pages[0].blocks[0].kind == BlockKind.HEADING
    doc = recognize_entities(
        pages,
        backend="mineru",
        backend_version=None,
        document_id="doc",
        warnings=[],
    )

    theorem = next(entity for entity in doc.entities if entity.entity_type == EntityType.THEOREM)
    assert theorem.metadata["theorem_number"] == "5.1"


def test_does_not_emit_theorem_family_for_index_entries_or_references() -> None:
    markdown = "\n\n".join(
        [
            "# Index",
            "definition, 50",
            "# References",
            "[15] Theorem proving in FOL",
            "Theorem proving in first-order logic. Journal X.",
        ]
    )

    doc = _doc(markdown)
    assert any(entity.entity_type == EntityType.INDEX_ENTRY for entity in doc.entities)
    assert any(entity.entity_type == EntityType.REFERENCE_ITEM for entity in doc.entities)
    assert _theorem_entities(markdown) == []


def test_mixed_content_preserves_existing_entity_detectors() -> None:
    markdown = "\n\n".join(
        [
            "# 1 Introduction",
            "**Theorem 3.2.** Let X be a finite group...",
            r"\[ E = mc^2 \tag{7} \]",
            "Figure 2. A diagram.",
            "![diagram](diagram.png)",
            "Table 1. Values.",
            "<table><tr><td>x</td></tr></table>",
            "# References",
            "[1] A. Paper.",
        ]
    )

    types = [entity.entity_type for entity in _doc(markdown).entities]

    assert EntityType.SECTION in types
    assert EntityType.THEOREM in types
    assert EntityType.EQUATION in types
    assert EntityType.CAPTION in types
    assert EntityType.FIGURE in types
    assert EntityType.TABLE in types
    assert EntityType.REFERENCE_SECTION in types
    assert EntityType.REFERENCE_ITEM in types
