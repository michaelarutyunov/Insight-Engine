# Block Catalog

All registered block implementations. Use `GET /api/v1/blocks` or `insights block list` to query at runtime.

---

## Data Types (edge vocabulary)

| Identifier | Description |
|---|---|
| `respondent_collection` | Tabular rows — survey data, customer records, any dataset |
| `segment_profile_set` | Cluster labels with centroid-based profiles |
| `concept_brief_set` | Product or creative concept descriptions |
| `evaluation_set` | Scored assessments with criteria and scores |
| `text_corpus` | Unstructured text documents |
| `persona_set` | Synthetic or real persona profiles |
| `generic_blob` | Fallback for untyped or experimental data |

---

## Sources

Entry points. No incoming edges. Execution starts here.

### `csv_loader` — CSVLoader
Loads a CSV **file** from disk into a `respondent_collection`. Each row becomes one record.

| | |
|---|---|
| **Inputs** | none |
| **Outputs** | `respondent_collection` |
| **Config** | `file_path` (required), `delimiter` (default `,`), `encoding` (default `utf-8`), `has_header` (default `true`) |
| **Use when** | Source data is a file on the server filesystem |

### `csv_source` — CSVSource
Parses a CSV **string** (inline data) into a `respondent_collection`.

| | |
|---|---|
| **Inputs** | none |
| **Outputs** | `respondent_collection` |
| **Config** | `csv_data` (required), `delimiter` (default `,`) |
| **Use when** | Source data is embedded in the pipeline config (testing, small datasets) |

---

## Transforms

Deterministic and cacheable. Same input → same output.

### `filter_transform` — FilterTransform
Filters rows in a `respondent_collection` by a column condition.

| | |
|---|---|
| **Inputs** | `respondent_collection` |
| **Outputs** | `respondent_collection` |
| **Config** | `column` (required), `operator` (`eq`/`neq`/`gt`/`lt`/`gte`/`lte`/`contains`, required), `value` (required) |
| **Use when** | Subsetting a dataset before downstream processing |

---

## Analysis

Question-driven blocks that produce structurally new output types. Analysis blocks are the primary consumers of the reasoning layer -- each block can carry a dimensional profile describing its analytical character along six ordinal dimensions (exploratory_confirmatory, assumption_weight, output_interpretability, sample_sensitivity, reproducibility, data_structure_affinity). The ResearchAdvisor matches research questions to Analysis blocks using these dimensions.

Practitioner workflows (in `reasoning_profiles/default/practitioner_workflows/`) provide method-specific guidance that the advisor can surface when recommending a block.

### `segmentation_kmeans` — KMeansAnalysis
Clusters respondents into segments using K-Means. Requires numeric features.

| | |
|---|---|
| **Inputs** | `respondent_collection` |
| **Outputs** | `segment_profile_set` |
| **Config** | `n_clusters` (2–20, required), `features` (list of column names, required), `scaling` (`standard`/`minmax`/`none`, default `standard`), `random_state` (default `42`) |
| **Use when** | Quantitative segmentation of survey or behavioural data |
| **Dimensional profile** | Not yet declared on the block (planned). Expected: exploratory_confirmatory=exploratory, assumption_weight=medium, output_interpretability=high, sample_sensitivity=medium, reproducibility=high, data_structure_affinity=numeric_continuous |
| **Practitioner workflow** | `reasoning_profiles/default/practitioner_workflows/segmentation.md` |

## Generation

Non-deterministic (LLM-powered). Version and seed tracking recommended.

### `llm_generation` — LLMGeneration
Generates text content from respondent data using a user-defined prompt template.

| | |
|---|---|
| **Inputs** | `respondent_collection` |
| **Outputs** | `text_corpus` |
| **Config** | `prompt_template` (required, use `{input}` placeholder), `model` (default `claude-sonnet-4-6`), `seed` (optional) |
| **Use when** | Producing summaries, narratives, or generated content from tabular data |
| **Note** | LLM call not yet wired in Phase 2 — returns rendered prompt as placeholder |

---

## Evaluation

Judges subject data against criteria. Requires 2+ input types.

### `concept_evaluator` — ConceptEvaluation
Evaluates product concepts from synthetic persona perspectives. Produces structured scores per dimension.

| | |
|---|---|
| **Inputs** | `concept_brief_set`, `persona_set` |
| **Outputs** | `evaluation_set` |
| **Config** | `evaluation_dimensions` (list, required; default: `appeal`, `uniqueness`, `purchase_intent`, `clarity`), `scoring_scale` (default 1–5), `model` (default `claude-sonnet-4-6`), `temperature` (default `0.3`) |
| **Use when** | Concept testing — scoring product or creative concepts against target personas |

### `rubric_evaluation` — RubricEvaluation
Scores text documents against named criteria using a fixed scoring mode.

| | |
|---|---|
| **Inputs** | `text_corpus`, `concept_brief_set` |
| **Outputs** | `evaluation_set` |
| **Config** | `criteria` (list of strings, required), `scoring_mode` (`binary`/`scale_5`/`scale_10`, default `scale_5`) |
| **Use when** | Structured quality assessment against a fixed rubric |
| **Note** | LLM call not yet wired — assigns max score as placeholder |

---

## LLM Flex

User-defined prompt with configurable I/O.

### `prompt_flex` — PromptFlex
Flexible LLM block. User writes the prompt; I/O shape is `text_corpus → text_corpus`.

| | |
|---|---|
| **Inputs** | `text_corpus` |
| **Outputs** | `text_corpus` |
| **Config** | `user_prompt_template` (required, use `{input}` placeholder), `system_prompt` (optional), `output_format` (`text`/`json`/`bullet_list`, default `text`) |
| **Use when** | Custom LLM transformations that don't fit a typed block |

---

## Routing

Conditional edge activation. Only selected output edges are active; others are marked skipped.

### `threshold_router` — ThresholdRouter
Routes based on an aggregated evaluation metric vs a threshold.

| | |
|---|---|
| **Inputs** | `evaluation_set` |
| **Outputs** | `evaluation_set` (on selected branch) |
| **Config** | `metric` (dimension name, required), `threshold` (number, required), `comparison` (`above`/`below`/`equal`, default `above`), `aggregation` (`mean`/`median`/`min`/`max`, default `mean`), `pass_edge_label` (default `pass`), `fail_edge_label` (default `fail`) |
| **Use when** | Post-evaluation branching — e.g. "if average appeal > 3.5, go to report; else loop back" |

### `conditional_router` — ConditionalRouter
Routes based on row count conditions in a `respondent_collection`.

| | |
|---|---|
| **Inputs** | `respondent_collection` |
| **Outputs** | `respondent_collection` (on selected branches) |
| **Config** | `rules` (list of `{branch_id, condition, threshold_value?}`, required). Conditions: `always`, `non_empty`, `threshold` |
| **Use when** | Branching on data volume — e.g. "if >100 rows, use full model; else use simplified model" |

---

## HITL (Human-in-the-Loop)

Suspends execution and persists full pipeline state. Resumes via `POST /api/v1/hitl/{run_id}/respond`.

### `approval_gate` — ApprovalGate
Pauses execution and presents data to a human reviewer. Type-passthrough — accepts and outputs any data type. Reviewer can approve, reject, or modify.

| | |
|---|---|
| **Inputs** | any type (all vocabulary types accepted) |
| **Outputs** | same type as input (passthrough) |
| **Config** | `prompt_text` (message shown to reviewer, default `"Please review and approve..."`), `require_comment` (bool, default `false`), `allow_modification` (bool, default `false`) |
| **Human response shape** | `{"approved": bool, "comment": str?, "modified_data": any?}` |
| **Use when** | QA checkpoints, client approval gates, editorial review before downstream steps |
| **Note** | Dynamically discovers the input data type key at runtime; no need to configure types |

---

## Comparator

Sync point — waits for all N parallel branches before continuing.

### `side_by_side_comparator` — SideBySideComparator
Collects `evaluation_set` results from multiple parallel branches and produces a combined comparison.

| | |
|---|---|
| **Inputs** | `evaluation_set` (N parallel) |
| **Outputs** | `evaluation_set` |
| **Config** | `expected_branches` (int ≥ 2, required), `mode` (`rank`/`diff`/`aggregate`, default `aggregate`) |
| **Use when** | Comparing parallel concept tests, A/B evaluation branches, or method comparisons |

---

## Reporting

Draws on multiple named upstream outputs (not just adjacent nodes).

### `markdown_report` — MarkdownReport
Assembles evaluation results and text documents into a structured Markdown report.

| | |
|---|---|
| **Inputs** | `evaluation_set`, `text_corpus` |
| **Outputs** | `text_corpus` |
| **Config** | `title` (required), `sections` (list of custom section headings, optional) |
| **Declares pipeline inputs** | `evaluation_set`, `text_corpus` |
| **Use when** | End-of-pipeline report generation combining scores and narrative content |

---

## Sinks

Terminal blocks. No outgoing edges. Persist final outputs.

### `json_sink` — JSONSink
Persists pipeline output as a named JSON artifact. Accepts any data type.

| | |
|---|---|
| **Inputs** | any type (all vocabulary types accepted) |
| **Outputs** | none |
| **Config** | `output_key` (artifact name, required), `pretty_print` (bool, default `true`) |
| **Use when** | Persisting final pipeline results for downstream retrieval or export |

---

## Example Pipelines

### Minimal end-to-end (linear)
```
CSVLoader → FilterTransform → KMeansTransform → JSONSink
```
Load survey CSV → filter to target age group → segment into clusters → persist results. JSONSink accepts any data type, so this works with `segment_profile_set` directly.

### Concept test with approval
```
CSVLoader(survey) → KMeansTransform → PersonaGeneration ──→ ConceptEvaluation → ApprovalGate → JSONSink
CSVLoader(concepts) ──────────────────────────────────────↗
```
Load survey data → segment → generate personas → evaluate concepts (needs both personas AND concept briefs from a second source) → human reviews scores → persist. Note: ConceptEvaluation requires two inputs (`concept_brief_set` + `persona_set`), so the pipeline has two entry points converging at that node.

### Conditional re-work loop
```
CSVLoader → ConceptEvaluation → ThresholdRouter
                                    ├── pass → MarkdownReport → JSONSink
                                    └── fail → PromptFlex → ConceptEvaluation (loop)
```
Evaluate concepts → if scores above threshold, report; if not, refine with LLM and re-evaluate.

### Parallel comparison
```
CSVSource → [ConceptEvaluation branch A] ─┐
          └ [ConceptEvaluation branch B] ─┴→ SideBySideComparator → JSONSink
```
Run two concept evaluations in parallel → compare results side by side.
