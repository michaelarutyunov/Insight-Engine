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

### `segmentation_kmeans` — KMeansTransform
Clusters respondents into segments using K-Means. Requires numeric features.

| | |
|---|---|
| **Inputs** | `respondent_collection` |
| **Outputs** | `segment_profile_set` |
| **Config** | `n_clusters` (2–20, required), `features` (list of column names, required), `scaling` (`standard`/`minmax`/`none`, default `standard`), `random_state` (default `42`) |
| **Use when** | Quantitative segmentation of survey or behavioural data |

### `filter_transform` — FilterTransform
Filters rows in a `respondent_collection` by a column condition.

| | |
|---|---|
| **Inputs** | `respondent_collection` |
| **Outputs** | `respondent_collection` |
| **Config** | `column` (required), `operator` (`eq`/`neq`/`gt`/`lt`/`gte`/`lte`/`contains`, required), `value` (required) |
| **Use when** | Subsetting a dataset before downstream processing |

---

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
Pauses execution and presents data to a human reviewer. Reviewer can approve, reject, or modify.

| | |
|---|---|
| **Inputs** | `generic_blob` |
| **Outputs** | `generic_blob` |
| **Config** | `prompt_text` (message shown to reviewer, default `"Please review and approve..."`), `require_comment` (bool, default `false`), `allow_modification` (bool, default `false`) |
| **Human response shape** | `{"approved": bool, "comment": str?, "modified_data": any?}` |
| **Use when** | QA checkpoints, client approval gates, editorial review before downstream steps |

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
Persists an `evaluation_set` as a named JSON artifact.

| | |
|---|---|
| **Inputs** | `evaluation_set` |
| **Outputs** | none |
| **Config** | `output_key` (artifact name, required), `pretty_print` (bool, default `true`) |
| **Use when** | Persisting final evaluation results for downstream retrieval or export |

---

## Example Pipelines

### Minimal end-to-end (linear)
```
CSVLoader → FilterTransform → KMeansTransform → JSONSink
```
Load survey CSV → filter to target age group → segment into clusters → persist results.

### Concept test with approval
```
CSVLoader → KMeansTransform → ConceptEvaluation → ApprovalGate → MarkdownReport → JSONSink
```
Load data → segment → evaluate concepts against personas → human reviews scores → generate report → persist.

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
