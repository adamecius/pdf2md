/**
 * TypeScript counterparts to the Pydantic models in
 * src/pdf2md/models/. Hand-rolled. Update in lock-step with the python
 * side.
 *
 * Only the subset the validator UI renders is declared here. Add more
 * fields when the UI starts consuming them.
 */

// ---------------------------------------------------------------------------
// Enums (BlockKind / EntityType / SelectionMode / CalibrationStatus / ...)
// ---------------------------------------------------------------------------

export type BlockKind =
  | "paragraph"
  | "heading"
  | "caption"
  | "table"
  | "formula"
  | "footnote"
  | "list"
  | "list_item"
  | "page_number"
  | "header"
  | "footer"
  | "reference"
  | "bibitem"
  | "code"
  | "figure"
  | "unknown";

export type EntityType =
  | "section"
  | "caption"
  | "footnote"
  | "equation"
  | "table"
  | "figure"
  | "page_number"
  | "header"
  | "footer"
  | "reference_item"
  | "reference_section"
  | "bibliography_marker"
  | "document_title"
  | "toc_entry"
  | "unknown";

export type SelectionMode =
  | "single_source"
  | "agreed"
  | "fallback"
  | "unresolved";

export type CalibrationStatus =
  | "calibrated"
  | "underpowered"
  | "no_samples"
  | "uninformative";

// ---------------------------------------------------------------------------
// Geometry primitives
// ---------------------------------------------------------------------------

export interface BBox {
  l: number;
  t: number;
  r: number;
  b: number;
  coord_origin?: "topleft" | "bottomleft";
}

export interface PageSize {
  width: number;
  height: number;
}

// ---------------------------------------------------------------------------
// PageExtractionIR (per-backend per-page)
// ---------------------------------------------------------------------------

export interface ExtractionBlock {
  id: string;
  backend: string;
  page_no: number;
  kind: BlockKind;
  bbox?: BBox | null;
  order: number;
  text?: string | null;
  confidence?: number | null;
  metadata?: Record<string, unknown>;
}

export interface PageExtractionIR {
  schema_name: "pdf2md.PageExtractionIR";
  schema_version: string;
  document_id: string;
  backend: string;
  backend_version?: string | null;
  page_no: number;
  page_size: PageSize;
  blocks: ExtractionBlock[];
  metadata?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// EntityProposalDocument
// ---------------------------------------------------------------------------

export interface EntityProposal {
  id: string;
  entity_type: EntityType;
  subtype?: string | null;
  canonical_text?: string | null;
  page_no?: number | null;
  block_ids?: string[];
  confidence?: number | null;
  confidence_source?: string | null;
  calibration_key?: string | null;
  metadata?: Record<string, unknown>;
}

export interface EntityProposalDocument {
  schema_name: "pdf2md.EntityProposalDocument";
  schema_version: string;
  document_id: string;
  backend: string;
  page_count: number;
  entities: EntityProposal[];
  relations?: unknown[];
}

// ---------------------------------------------------------------------------
// ConsensusIR
// ---------------------------------------------------------------------------

export interface ConsensusBlock {
  id: string;
  page_no: number;
  kind: BlockKind;
  bbox?: BBox | null;
  text?: string | null;
  selection_mode: SelectionMode;
  agreement_score: number;
  candidate_ids: string[];
  conflict_ids?: string[];
  metadata?: Record<string, unknown>;
}

export interface ConsensusPage {
  page_no: number;
  blocks: ConsensusBlock[];
}

export interface ConsensusBackendEntry {
  backend: string;
  block_count?: number;
}

export interface ConsensusConflict {
  id: string;
  kind: string;
  block_ids: string[];
}

export interface ConsensusIR {
  schema_name: "pdf2md.ConsensusIR";
  schema_version: string;
  document_id: string;
  page_count: number;
  pages: ConsensusPage[];
  backends: ConsensusBackendEntry[];
  conflicts?: ConsensusConflict[];
  agreement_summary?: Record<string, unknown>;
  warnings?: string[];
}

// ---------------------------------------------------------------------------
// CalibrationPriorDocument (subset)
// ---------------------------------------------------------------------------

export interface CalibrationCounts {
  true_positive: number;
  false_positive: number;
  false_negative: number;
}

export interface CalibrationMetric {
  target: "block_kind" | "entity_type" | "relation_type" | "calibration_key";
  key: string;
  counts: CalibrationCounts;
  precision: number;
  recall: number;
  f1: number;
  support: number;
  calibrated_confidence: number;
  status: CalibrationStatus;
  metadata?: Record<string, unknown>;
}

export interface CalibrationPriorDocument {
  schema_name: "pdf2md.CalibrationPriorDocument";
  schema_version: string;
  backend: string;
  backend_version?: string | null;
  generated_from?: string[];
  min_samples: number;
  smoothing_alpha: number;
  smoothing_beta: number;
  default_confidence: number;
  block_kind_priors: CalibrationMetric[];
  entity_type_priors: CalibrationMetric[];
  relation_type_priors: CalibrationMetric[];
  calibration_key_priors: CalibrationMetric[];
  warnings?: string[];
  metadata?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// DoclingDocument (a tiny, lossy subset — we only render texts/pictures/tables)
// ---------------------------------------------------------------------------

export interface DoclingProv {
  page_no?: number;
  bbox?: { l: number; t: number; r: number; b: number };
}

export interface DoclingText {
  self_ref: string;
  label: string;
  text: string;
  orig?: string;
  level?: number;
  prov?: DoclingProv[];
  parent?: { $ref: string } | null;
  children?: { $ref: string }[];
}

export interface DoclingPicture {
  self_ref: string;
  prov?: DoclingProv[];
  parent?: { $ref: string } | null;
  children?: { $ref: string }[];
}

export interface DoclingTable {
  self_ref: string;
  prov?: DoclingProv[];
  parent?: { $ref: string } | null;
  children?: { $ref: string }[];
}

export interface DoclingDocument {
  schema_name: "DoclingDocument";
  version?: string;
  name?: string;
  body?: { children?: { $ref: string }[] };
  texts?: DoclingText[];
  pictures?: DoclingPicture[];
  tables?: DoclingTable[];
}

// ---------------------------------------------------------------------------
// Per-doc dataset descriptor used by the UI to drive its dropdowns
// ---------------------------------------------------------------------------

export interface DatasetAvailability {
  /** True when the compiled PDF is reachable in this deploy. */
  hasPdf: boolean;
  /** True when the ground-truth `.docling.json` is reachable. */
  hasDocling: boolean;
  /** Backends with per-page extraction IR available (may be synthesised). */
  hasBackends: string[];
  /** True when a ConsensusIR is reachable. */
  hasConsensus: boolean;
  /**
   * True when the backend pages + consensus IR shipped in this deploy were
   * synthesised from the ground truth by `webui/scripts/stage-data.mjs`,
   * rather than produced by a real pipeline run. The Compare view surfaces
   * a "demo data" banner when this is set.
   */
  demo_synthesized: boolean;
}

export interface DatasetEntry {
  id: string;
  label: string;
  pdfPath: string; // /api/-prefixed URL the validator fetches
  doclingPath: string;
  source: "groundtruth" | "papers_run";
  backends: string[]; // backends with connector output available
  availability: DatasetAvailability;
}

/** Shape of `/api/_availability.json` written by stage-data.mjs. */
export interface AvailabilityManifest {
  groundtruth: Record<string, DatasetAvailability>;
}
