## 1. Problem statement

The current canonical schema in `pdf2md` is linear and optimized for reconstruction of reading order:

- `Document`
  - `Pages`
    - `Blocks` ordered by `page_number` and `order`

This works for straightforward Markdown rendering, but it cannot explicitly represent semantic relations between content elements.

For example, consider a page with:

- Paragraph: `As shown in Figure 2, the method follows Smith et al. [12].¹`
- Image: architecture diagram
- Caption: `Figure 2. System architecture.`
- Footnote: `¹ Additional explanation.`
- Bibliography entry: `[12] Smith, J. ...`

The current schema can store all of these as blocks in reading order, but it cannot explicitly encode that:

- `Figure 2` refers to a specific image or caption target.
- `[12]` cites a specific bibliography entry.
- `¹` points to a specific footnote body.
- The caption belongs to the image.
- The image and caption form one logical figure object.
- The paragraph belongs to a section in a document/book hierarchy.

## 2. Desired behaviour

The canonical model should remain linear at its foundation.

Linear block stream remains source of truth for Markdown reconstruction:

- `page -> ordered blocks -> Markdown`

In addition, the model should support semantic reconstruction through annotations and explicit relations layered on top of that linear stream.

The future model should support questions like:

- Which figure does this paragraph reference?
- Which caption belongs to this image?
- Which bibliography entry does this citation point to?
- Which footnote body belongs to this footnote marker?
- Which section does this block belong to?
- What is the logical tree of the book?
- Which image text is embedded inside a figure rather than normal page text?

## 3. Core design idea

Semantic reconstruction should be represented using four layers:

1. Linear blocks
2. Inline spans
3. Target objects
4. Relations

Do **not** split every reference into a separate block.

A paragraph remains a paragraph block, while references inside that paragraph become typed inline spans.

Example:

- Block
  - `id = block_002`
  - `type = paragraph`
  - `text = "As shown in Figure 2, the method follows Smith et al. [12].¹"`

- Inline spans
  - `"Figure 2" -> type=figure_ref`
  - `"[12]" -> type=bibliographic_citation`
  - `"¹" -> type=footnote_marker`

Then relations connect spans to resolved targets.

## 4. Proposed schema additions

Planned model additions are listed below.

### InlineSpan

Purpose: represent semantic fragments inside a block.

Suggested fields:

- `id`
- `block_id`
- `type`
- `text`
- `char_start`
- `char_end`
- `target_label`
- `confidence`
- `metadata`

Suggested span types:

- `figure_ref`
- `table_ref`
- `equation_ref`
- `bibliographic_citation`
- `footnote_marker`
- `section_ref`
- `link`
- `emphasis`
- `unknown`

### Relation

Purpose: represent links between spans, blocks, media, sections, and bibliography entries.

Suggested fields:

- `id`
- `type`
- `source_id`
- `target_id`
- `confidence`
- `evidence`
- `metadata`

Suggested relation types:

- `contains`
- `caption_of`
- `refers_to`
- `cites`
- `footnote_of`
- `embedded_in`
- `continues`
- `same_as`
- `belongs_to_section`

### Media

Purpose: represent extracted images or other media independently from image placeholder blocks.

Suggested fields:

- `id`
- `path`
- `type`
- `page_number`
- `bbox`
- `caption_block_id`
- `source_refs`
- `metadata`

Suggested media types:

- `image`
- `figure`
- `chart`
- `diagram`
- `table_image`
- `equation_image`
- `unknown`

### Section

Purpose: represent the logical book tree derived from heading blocks and ordered content.

Suggested fields:

- `id`
- `title`
- `level`
- `heading_block_id`
- `parent_id`
- `children`
- `block_ids`

### BibliographyEntry

Purpose: represent bibliography targets separately from ordinary paragraphs.

Suggested fields:

- `id`
- `label`
- `text`
- `page_number`
- `block_id`
- `parsed_authors`
- `year`
- `title`
- `metadata`

This should start simple; full bibliographic parsing is not required in the first implementation.

## 5. How to distinguish relation types

### Figure references

Typical forms:

- `Figure 2`
- `Fig. 2`
- `Fig. 2a`
- `see Figure 3`
- `as shown in Fig. 4`

Likely targets:

- image block
- caption block
- media object

Resolution strategy:

- detect figure labels in inline text
- detect caption labels beginning with `Figure`, `Fig.`, etc.
- link the reference span to a matching caption or media object

### Bibliographic citations

Typical forms:

- `[12]`
- `[12, 13]`
- `[4-7]`
- `(Smith et al., 2020)`
- `Smith and Jones (2021)`

Likely target:

- `bibliography_entry`

Resolution strategy:

- detect numeric and author-year citation spans
- detect bibliography/references section
- link citation spans to matching bibliography entries

### Footnote markers

Typical forms:

- `¹`
- `²`
- `*`
- `†`
- `‡`
- superscript numbers or letters

Likely target:

- footnote block

Resolution strategy:

- detect marker spans in paragraph/caption/table/heading text
- detect matching footnote blocks on same or nearby pages
- use layout cues where available (e.g., bottom-of-page position)
- link marker span to resolved footnote block

### Caption to image

Captions are blocks, not inline spans.

Resolution strategy:

- detect caption labels such as `Figure 2.` or `Table 1.`
- link caption block to nearby image/table block via `caption_of`
- preserve both reading order and explicit relation

### Text inside images

Image-internal text should not be mixed into normal page text.

Represent image-internal text as a dedicated block/object category, e.g.:

- `image_text`
- `image_note`
- `embedded_text`

Then link it to media with `embedded_in`.

This preserves distinctions among:

- page text
- caption text
- footnote text
- text embedded inside figures

## 6. Desired conceptual output

Input text:

`As shown in Figure 2, the method follows Smith et al. [12].¹`

Desired representation:

- `block_002`
  - `type: paragraph`
  - `text: "As shown in Figure 2, the method follows Smith et al. [12].¹"`

- `span_001`
  - `type: figure_ref`
  - `text: "Figure 2"`
  - `block_id: block_002`
  - `target_label: "Figure 2"`

- `span_002`
  - `type: bibliographic_citation`
  - `text: "[12]"`
  - `block_id: block_002`
  - `target_label: "12"`

- `span_003`
  - `type: footnote_marker`
  - `text: "¹"`
  - `block_id: block_002`
  - `target_label: "1"`

- `relations`
  - `span_001 refers_to media_002 or caption_002`
  - `span_002 cites bib_012`
  - `span_003 footnote_of fn_001`
  - `caption_002 caption_of media_002`

## 7. Implementation order

### Step 1: Extend the schema only

Add model classes for:

- `InlineSpan`
- `Relation`
- `Media`
- `Section`
- `BibliographyEntry`

Extend `Document` with optional lists:

- `spans`
- `relations`
- `media`
- `sections`
- `bibliography`

Requirements:

- maintain backward compatibility with existing tests and simple documents
- do not implement extraction logic yet

### Step 2: Update serialisation tests

Add tests that verify `Document` serialisation/deserialisation with:

- paragraph block
- image block
- caption block
- footnote block
- bibliography entry
- inline spans
- relations between entities


### Step 2b: Align `description.md` with semantic relations plan

The repository-level `description.md` should be updated in a follow-up documentation task so it remains consistent with the canonical schema direction.

Documentation updates should explicitly add:

- linear-first + semantic-annotations model positioning
- the new semantic entities (`InlineSpan`, `Relation`, `Media`, `Section`, `BibliographyEntry`)
- examples of figure/citation/footnote/caption relation semantics
- note that adapters and consensus remain future steps

Constraint:

- keep `description.md` wording forward-looking (planned work), not as already implemented

### Step 3: Update Markdown rendering carefully

- keep Markdown rendering linear by default
- continue to drive rendering from ordered blocks
- do not make rendering depend on relation resolution yet
- ensure image/media placeholders still render correctly

### Step 4: Add section tree construction

Implement a helper that derives section objects from heading blocks.

Input:

- ordered blocks with heading levels

Output:

- section objects with parent-child hierarchy and `block_ids`

Constraint:

- build tree without altering the linear block stream

### Step 5: Add lightweight reference detection utilities

Add simple regex-based detectors for candidate inline spans:

- figure references
- table references
- equation references
- numeric citations
- footnote markers

These utilities should produce candidate `InlineSpan` objects only, not final resolved relations.

### Step 6: Add relation resolution helpers

Add helpers that attempt to resolve:

- `figure_ref` spans -> captions/media
- caption blocks -> media
- citation spans -> bibliography entries
- footnote markers -> footnote blocks

Output should be `Relation` objects with confidence values.

### Step 7: Integrate with adapters later

Do not implement backend adapters in the first schema task.

Later possibilities:

- `MinerUAdapter`: populate blocks, media, captions, and layout-related hints
- `DeepSeekAdapter`: populate text and visual extraction blocks
- `PaddleOCRAdapter`: populate OCR text blocks with confidence metadata

### Step 8: Integrate with consensus later

Consensus should compare canonical documents only after adapter-level outputs exist.

Relations can improve disagreement detection, such as:

- one backend links caption-to-image while another does not
- one backend detects a citation while another misses it
- one backend places a footnote differently in reading order

## 8. Constraints

The implementation plan must preserve these constraints:

- base document remains linear
- section tree is derived from linear blocks and heading levels
- semantic relations are annotations over the linear document
- do not replace `Block` with a tree-only structure
- do not force every inline reference to become a block
- do not implement consensus yet
- do not implement backend adapters yet
- keep schema extensible and serialisable via Pydantic

## 9. Acceptance criteria for this planning document

`next_plan.md` should:

- explain the problem clearly
- define desired behaviour
- describe `InlineSpan`, `Relation`, `Media`, `Section`, and `BibliographyEntry`
- explain how figure references, citations, footnotes, captions, and image text are distinguished
- provide implementation order for future incremental tasks
- avoid code changes
- avoid claiming this is already implemented
- include a follow-up note to keep `description.md` compatible with this semantic-relations direction
- be suitable as the starting point for the next Codex implementation task
