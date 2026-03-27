# Insights IDE — Product Vision & Architecture Overview

## Core Thesis

Today, insight outputs are shared — reports, dashboards, presentations. Insight *processes* are not. The methodology behind a segmentation study, the analytical pipeline for a brand tracker, the workflow connecting social listening to product recommendations — these live as tacit knowledge in someone's head, or as a loose chain of disconnected tools. They are not inspectable, not reproducible, not shareable, and not reusable.

Insights IDE makes the research process itself a first-class artifact. The unit of work is the research design, not the analysis. A pipeline built in Insights IDE can be saved, versioned, shared, critiqued, and reused — just as source code can. This changes insight generation from a craft performed in isolation to a discipline with composable, auditable methodology.

## What It Is

A visual, modular platform where insights professionals build research pipelines as node-and-edge graphs. Customizable blocks bridge the multiple stages of insight generation — from diverse data sources (customer databases, consumer panels, syndicated data, social platforms, review sites) through analysis, enrichment, and validation to client-ready deliverables.

The metaphor is an IDE for research: just as VSCode makes software development structure visible and manipulable, Insights IDE makes research design visible, inspectable, reproducible, and shareable.

The platform supports three interaction modes — a visual canvas for designing pipelines, a chat panel for natural language assistance and pipeline modification, and a CLI for programmatic control. All three operate on the same underlying data structures. This makes the platform accessible to visual thinkers, conversational users, and automation scripts (including AI agents) equally.

## The Problem (Commercial)

Insight generation is fragmented across dozens of disconnected tools — survey platforms, statistical packages, visualization tools, qualitative analysis software, and a growing number of AI wrappers. Each step lives in a different tool with manual handoffs between them. This fragmentation has direct costs:

**Time.** A research team running a social listening study manually extracts data from Reddit or review sites, cleans it in Python or Excel, codes themes in a qualitative tool, analyzes frequencies in another tool, writes a report in PowerPoint. Each handoff requires formatting, re-importing, and context-switching. A workflow that could run in hours takes days or weeks.

**Money.** Concept testing is expensive because there is no structured way to pre-screen ideas before committing fieldwork budget. Teams test too many concepts at full scale because the alternative — ad hoc internal review — is unstructured and unreliable.

**Knowledge loss.** When a researcher leaves, their methodology leaves with them. There is no artifact that captures how a brand tracker was processed, what decisions were made during segmentation, or why a particular analytical approach was chosen. The next person rebuilds from scratch.

**Quality variance.** Without standardised workflows, the same type of study executed by different team members produces inconsistent results. There is no shared methodology, no audit trail, and no systematic way to improve process over time.

## The Solution

Insights IDE addresses each of these directly:

**Connect** to diverse data sources — customer databases, consumer datasets, syndicated data snapshots, social media extracts (Reddit, X), review platforms (Amazon, Trustpilot), survey panels, and any API-accessible data service.

**Bridge** the stages of insight generation in a single visual pipeline — ingestion, cleaning, segmentation, analysis, enrichment, evaluation, fieldwork, and reporting become connected blocks rather than isolated tasks.

**Experiment** with research design itself — swap analytical approaches, reroute pipelines, compare workflow variants, iterate on methodology as easily as editing code.

**Execute** end-to-end — from raw data through to client-ready deliverables, including optional connections to sample providers and fieldwork services for real-world validation.

**Preserve and share** methodology — save pipelines as reusable templates, share proven workflows across teams, build organisational research capability that survives personnel changes.

## Commercial Wedge — Entry Use Cases

Each of the following represents a specific workflow where the current process is painful and the platform delivers measurable improvement. Any one of these is a viable entry point; all use the same block library and execution engine.

### Social Listening & Review Mining

**Current pain:** A brand team wants to understand customer sentiment across Reddit, Amazon reviews, and Trustpilot. An analyst manually extracts data from each platform, cleans it in separate tools, codes themes by hand or using a basic AI wrapper, analyses frequencies in a spreadsheet, and produces a report in PowerPoint. This takes 1–2 weeks and is repeated quarterly with no process continuity.

**Platform workflow:**
Source (Reddit API extract) → Source (Amazon reviews) → Source (Trustpilot extract) → Transform (merge, deduplicate, clean) → LLM Flex (thematic coding with custom prompt) → Transform (theme frequency analysis) → Comparator (compare themes across sources or time periods) → HITL Checkpoint (analyst reviews themes) → Reporting (insight report as PDF) → Sink (save to project)

**Value:** Build the pipeline once. Run it quarterly with new data in minutes instead of weeks. Compare across waves automatically. Methodology is documented in the pipeline structure itself. New team members can run the same study without training.

### Customer Segmentation & Profiling

**Current pain:** A CRM team runs segmentation annually. Each time, a data scientist pulls data, writes segmentation code from scratch (or adapts last year's notebook), evaluates segments informally, and produces a static PowerPoint deck. If the data scientist changes, the entire approach may change with them.

**Platform workflow:**
Source (customer database) → Transform (feature engineering) → Transform (k-means segmentation) → Evaluation (LLM-powered segment assessment) → HITL Checkpoint (review segments) → Reporting (segment playbook document) → Sink (save to project, notify stakeholders)

**Value:** Segmentation becomes a repeatable, documented process. Swap k-means for LCA or RFM by changing one block. Compare approaches side by side. The segment playbook is generated directly from the pipeline output, not manually assembled.

### Concept Pre-Screening & Validation

**Current pain:** A product team has 10+ concept ideas and budget to fieldwork-test 3. Currently, the narrowing is done by internal opinion, loosely structured workshops, or expensive early-stage quant testing at full scale.

**Platform workflow:**
Source (customer data) → Transform (segmentation) → Generation (synthetic personas from segments) → Evaluation (concept test against personas) → Router/HITL (optimization loop) → Source (sample provider API) → Transform (fieldwork execution) → Transform (data cleaning) → Reporting (validation report) → HITL Checkpoint (final review) → Sink (archive project)

**Value:** Synthetic pre-screening narrows from 10+ concepts to 3 finalists before any fieldwork spend. The synthetic loop is explicitly a pre-screening tool — a structured replacement for gut-feel internal review — not a substitute for real-world validation. Fieldwork budget is concentrated on the strongest candidates.

### Brand Tracker Processing

**Current pain:** Syndicated tracking data arrives quarterly. Processing it — cleaning, weighting, computing KPIs, comparing waves, writing narrative — is a manual multi-day exercise repeated identically each wave, often by different people with slightly different approaches.

**Platform workflow:**
Source (syndicated data snapshot) → Transform (data cleaning, weighting) → Transform (KPI computation) → Comparator (wave-over-wave comparison) → LLM Flex (narrative interpretation of movements) → HITL Checkpoint (analyst review) → Reporting (tracker update presentation) → Sink (push to dashboard API)

**Value:** Tracker processing becomes a one-click operation per wave. Methodology is locked in the pipeline — no drift between analysts or quarters. Wave-over-wave comparison is automatic. Analyst time shifts from data processing to interpretation and strategic response.

### Review Mining for Product Development

**Current pain:** A product team wants to mine Amazon and Trustpilot reviews for feature requests and pain points. Currently done ad hoc in spreadsheets with no systematic process, no comparability across products, and no connection to product development workflows.

**Platform workflow:**
Source (Amazon reviews API) → Source (Trustpilot extract) → Transform (merge and deduplicate) → LLM Flex (sentiment and feature extraction) → Transform (feature-sentiment matrix) → Comparator (compare across products or competitors) → Generation (product improvement briefs) → Reporting (product team report) → Sink (save and distribute)

**Value:** Systematic, repeatable extraction of product intelligence from review data. Feature-sentiment matrices enable prioritisation. Competitive comparison across products. Automated product improvement briefs feed directly into development planning.

## Target Users

Three personas, in order of product-market fit:

### Research Engineer / Research Ops (Day-One User)
Already thinks in pipelines. Frustrated by manual glue work across tools. Immediately grasps the node graph metaphor. Small market but high intent and low switching cost — they're cobbling things together in notebooks and scripts anyway. This persona builds pipelines and shares them as templates for others to use.

### Research Manager (Growth Market)
Needs a gentler on-ramp. Would primarily use pre-built workflow templates rather than building from scratch. Cares about the output (the report, the recommendation) more than pipeline elegance. Templates and a guided experience are essential. This persona benefits from the graph's visibility and auditability without needing to build from blank canvas.

### Technically Savvy Marketer (Aspirational)
Would need substantial domain scaffolding built into blocks. Risky as a primary target at launch — essentially requires a more guided, wizard-like experience rather than an IDE. Phase 4+ via templates and simplified interfaces.

## Block Taxonomy

Ten abstract base types define the operational vocabulary of the platform. Each type represents a behavioral contract with the execution engine.

### Source
Entry points that bring data into the pipeline. No meaningful input, produces output. Examples: database connection, file upload, sample provider response, API fetch. Engine behavior: execution can begin here.

### Transform
Deterministic or near-deterministic data processing. Takes input, applies logic, produces output. Examples: segmentation, data cleaning, recoding, weighting, merging. Engine behavior: given same input and configuration, output is reproducible; results can be cached.

### Generation
Creates new content that didn't exist in the input. Non-deterministic by nature. Examples: synthetic personas, concept drafts, discussion guides, stimulus materials. Engine behavior: output varies across runs; versioning and seed tracking matter.

### Evaluation
Judges a thing against criteria. Requires two or more inputs (typically a subject and evaluation criteria). Examples: concept testing against personas, quality scoring, compliance checks. Engine behavior: requires multiple input types; produces assessment output.

### Comparator
Compares multiple same-typed inputs against each other. A synchronization point in the graph — waits for all parallel branches to complete before executing. Examples: comparing three segmentation approaches, consolidating evaluations across persona sets, wave-over-wave tracker comparison. Engine behavior: accepts N inputs of compatible types; acts as a join for parallel branches.

### LLM Flex
The generic programmable node. Takes input, applies a user-defined prompt, produces output. Input/output shapes are user-configured rather than preset. Examples: custom analysis, freeform evaluation, thematic coding, narrative interpretation. Engine behavior: validation depends on user configuration; supports prompt versioning and A/B testing.

### Router
Inspects input and directs flow. Controls graph traversal by activating specific output edges based on conditions. Examples: convergence checks, threshold gates, conditional branching, loop termination. Engine behavior: multiple output edges, activates subset per execution.

### HITL Checkpoint
Pauses execution for human input. Presents data to a human, waits for response with no time guarantee. Examples: review gates, approval steps, manual annotation, qualitative judgment. Engine behavior: execution suspends, full pipeline state persists, resumes on external event.

### Reporting
Assembles, narrates, and formats outputs from across the pipeline into a deliverable. Unlike Generation (which creates new content from immediate input), Reporting draws on multiple upstream outputs — potentially from several stages of the pipeline — and structures them into a cohesive narrative with format-awareness. Examples: PDF report combining segmentation profiles with fieldwork results, executive presentation, podcast script summarizing key findings, dashboard update, client-ready article. Engine behavior: accepts multiple named inputs from across the pipeline (not just adjacent nodes); configuration includes output format and narrative structure.

### Sink
Terminal nodes where pipeline branches end. A Sink is a project closure point — it persists final outputs and signals that this branch of work is complete. Examples: save to project storage, push to external system via API, archive dataset, trigger notification. Engine behavior: no downstream nodes.

## Competitive Positioning

### vs. n8n / Zapier / Make
General-purpose automation platforms can handle 40-50% of the functionality — API connections, workflow orchestration, basic data piping. They cannot handle domain-specific data modeling (survey data structures, segment profiles, social listening themes), meaningful analytical blocks (segmentation, sentiment extraction, thematic coding), or the narrative layer from analytical output to client-ready insight stories. Insights IDE should not reinvent generic orchestration but should differentiate on research-specific block intelligence, typed data objects, and the ability to bridge diverse insight sources into coherent analytical workflows.

### vs. Jupyter / Python Notebooks
A notebook lets you build *a* workflow. Insights IDE lets you explore the *workflow design space* — swap approaches, reroute pipelines, compare variants. The unit of work is the research design, not the analysis. Additionally, pipelines are visual, shareable, reproducible, and auditable by non-technical stakeholders — something notebooks fundamentally are not.

### vs. Qualtrics / SurveyMonkey / Dovetail
Point solutions that cover one phase of the research lifecycle. Insights IDE spans the full lifecycle and treats each phase as a connectable module. Survey platforms become potential integration targets (as Source or Transform blocks) rather than competitors.

### Distinctive Moat
No existing tool lets you visually architect a multi-stage insight generation workflow — connecting diverse data sources through analysis, enrichment, and validation to deliverables — and then save that architecture as a reusable, shareable template. The combination of visual pipeline design, domain-specific typed data objects, a research-aware block library, and composability across the full insight lifecycle is unique.

## Agent Integration & AI Infrastructure

The current industry conversation around agentic AI in insights is largely unstructured — autonomous chatbots that do one thing at a time with no persistent plan, or fully automated systems that nobody trusts for consequential decisions. Insights IDE can occupy a distinctive middle position: structured, governed, auditable AI infrastructure for insight generation.

A pipeline graph is essentially a structured plan. It defines goals (what the pipeline produces), steps (the blocks), dependencies (the edges), decision points (routers), and human oversight requirements (HITL checkpoints). This is exactly what an agentic system needs as its operating structure. Three integration modes are envisioned, in order of increasing autonomy:

### Agent as Pipeline Executor
A business deploys an agent whose job is to monitor triggers — new data arrives, a tracker updates, a quarterly review is due — and execute predefined pipelines automatically, pausing at HITL checkpoints for human judgment. The platform provides the plan; the agent provides scheduling and monitoring. This is the most conservative mode: the agent follows a human-designed workflow.

### Agent as Pipeline Composer
A more advanced mode where a business describes a goal ("we need to understand why our NPS dropped in the Midwest") and an agent assembles an appropriate pipeline from the block library — selecting data sources, choosing analytical methods, wiring the graph. A human reviews the proposed pipeline at an HITL checkpoint before anything executes. The platform provides the vocabulary of blocks and their contracts; the agent provides the research design reasoning.

### Platform as Agent Workspace
The most expansive framing. An insights agent that operates across a business's intelligence needs — fielding ad hoc questions, maintaining ongoing trackers, triggering research when anomalies are detected — uses the pipeline graph as its working memory and planning structure. Every action the agent takes is a block execution within a visible, auditable graph. The business can inspect exactly what the agent did, why, and intervene at any point.

### Architectural Implications (Current Phase)
Agent integration is a phase 4–5 feature, but it should inform architectural decisions now:

- The pipeline definition schema should be LLM-readable and LLM-writable (already satisfied — it's structured JSON)
- Block contracts should be described clearly enough that an LLM can reason about compatibility
- The execution API should support programmatic triggering, not just UI-driven runs
- The audit trail built into the graph structure provides exactly the governance layer businesses need to deploy agentic AI responsibly in a domain where decisions have real budget and strategic consequences

This positions the platform not just as a tool for human researchers, but as **infrastructure for governed AI in insights**.

## Key Risks & Assumptions

### Assumption: Insights professionals want to build workflows
Most insights managers want templates and point-and-click, not an IDE. The people who would love an IDE (research engineers, research ops) are a smaller market. The platform needs both: a power-user graph editor and a template library for less technical users. The sequencing is deliberate: build for engineers first, expand to managers via templates.

### Assumption: Sample providers will offer API access
Some do (Cint, Lucid/Federated Sample). Many legacy providers are API-hostile. Platform value depends partly on integration breadth that is outside direct control. Mitigation: the platform delivers value without fieldwork integration (social listening, tracker processing, segmentation workflows all work with existing data sources).

### Assumption: Agencies want a marketplace
Agencies monetize through relationships and bespoke work. Productizing methodology into reusable components threatens their billable-hours model. Marketplace viability needs validation.

### Risk: Circular validation in synthetic workflows
Workflows that use synthetic personas or LLM-based evaluation loops optimize against the platform's own model of consumers. Where synthetic pre-screening is used, it must be transparently positioned as a narrowing tool, not a replacement for real-world validation. HITL checkpoints and clear conventions help mitigate this. This applies to a subset of workflows, not the platform as a whole.

### Risk: Scope creep
Every block is itself a complex product. The temptation to build deep functionality in every block must be resisted. Strategy: build the graph orchestration layer well, let most blocks be thin wrappers around existing services initially, go deep only where no adequate external service exists. The priority for deep investment: the orchestration engine, the Reporting block family, and the LLM Flex block (since custom prompts are the platform's most flexible capability).

### Risk: Value perceived as "too meta"
"A better way to structure work" is a builder's framing, not a buyer's framing. The commercial case must always lead with outcomes — faster turnaround, lower fieldwork costs, methodology preserved when people leave, consistent quality across team members — not with architectural elegance.

## Analogues & Reference Points

- **Hex** (hex.tech) — IDE-like notebook for data science, positioned between Jupyter and BI tools. Instructive journey from "notebook for data teams" to "broader analytics platform."
- **VSCode** — the metaphor source. Valuable not because alternatives don't exist, but because it makes the structure of work visible and manipulable. Extension ecosystem as moat.
- **Node-RED** — visual flow-based programming for IoT. Similar node-and-edge paradigm, different domain. Demonstrates viability of visual pipeline builders for technical-but-not-developer audiences.
- **Figma** — relevant for the collaboration angle. Figma didn't win by being a better drawing tool; it won by making design work visible, shareable, and collaborative. Insights IDE aims to do the same for research methodology.
