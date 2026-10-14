# CancerBench UI and Phase 3 Design Guide

## Purpose

This file is the visual and product reference for the CancerBench research UI.
Every new CancerBench interface component should follow these rules unless this
guide is deliberately revised.

CancerBench is a research-only drug-response exploration tool. A researcher
enters a medicine and cancer cell line, receives a predicted `LN_IC50` response,
reviews the model's SHAP explanation, and inspects supporting scientific
literature without leaving the workspace.

The interface must never imply that a prediction is a diagnosis, treatment
recommendation, or established biological causality.

## Phase 3: Literature Retrieval Service

### Goal

Retrieve relevant, traceable scientific evidence for a drug, gene, or predicted
response. Prefer Postgres with `pgvector` so document metadata and embeddings
remain together. Qdrant is acceptable, but is not the default because it adds a
specialized infrastructure service without materially improving this portfolio
project.

### Dataset and provenance

- Curate approximately 200–500 abstracts.
- Preserve PubMed ID, DOI when available, title, abstract, authors, publication
  year, journal, and canonical source URL.
- Document how articles were selected and record each ingestion date.
- Respect dataset and abstract usage terms.
- Store either the static source data or a reproducible download manifest.
- Make provenance visible in the product; citations must not be anonymous cards.

### Ingestion

- Normalize drug and gene aliases before retrieval.
- Divide documents into semantically sensible chunks.
- Generate embeddings in batches.
- Store the embedding model and version with every record.
- Make ingestion idempotent and prevent duplicate PMID records.
- Log counts for inserted, updated, skipped, and failed documents.

### Retrieval API

Implement `POST /retrieve`.

Example request:

```json
{
  "query": "TP53-associated resistance to Cisplatin",
  "top_k": 5,
  "filters": {
    "year_from": 2015
  }
}
```

Example response:

```json
{
  "results": [
    {
      "pmid": "12345678",
      "title": "Example study",
      "snippet": "Relevant passage...",
      "score": 0.82,
      "year": 2024,
      "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/"
    }
  ],
  "embedding_version": "..."
}
```

### Retrieval evaluation

Create 15–25 small evaluation queries covering:

- Drug-name queries.
- Gene-name queries.
- Drug-plus-gene queries.
- Resistance and sensitivity language.
- Known aliases.
- A query that should return no strong evidence.

Measure recall at k, mean reciprocal rank, whether the expected PMID appears,
citation metadata completeness, and retrieval latency. The endpoint returning a
document is not sufficient evidence of retrieval quality.

### Definition of done

Given a gene or drug question, the service returns relevant passages with stable
PubMed identifiers and links, and the evaluation set demonstrates reasonable
retrieval quality.

## Product experience

### Primary workflow

1. The researcher starts a new analysis.
2. They select or type a medicine and cell line in the composer.
3. CancerBench validates both values and begins the prediction.
4. The assistant response shows predicted `LN_IC50`, an interpretation label,
   model version, and uncertainty or limitations where available.
5. SHAP contributions explain which mutation and drug features moved the
   prediction higher or lower.
6. A literature query is assembled from the medicine, cell line context, and
   strongest relevant gene features.
7. Cited passages appear in the evidence rail and are referenced inline with
   numbered citation links such as `[1]` and `[2]`.
8. Selecting a citation focuses its evidence card; selecting a SHAP feature can
   refine the literature rail to that gene or feature.

### Desktop layout

Use a quiet three-part shell:

```text
+----------------+--------------------------------------+----------------------+
| History        | Conversation and explanation         | Scientific evidence  |
|                |                                      |                      |
| New analysis   | Researcher prompt                    | [1] Paper title      |
| Recent queries | Assistant prediction summary         | Relevant passage     |
|                | SHAP contribution chart              | PMID · Year · Journal|
|                | Limitations and model metadata       |                      |
|                |                                      | [2] Paper title      |
|                | [ Medicine ] [ Cell line ] [ Send ]  | Relevant passage     |
+----------------+--------------------------------------+----------------------+
```

- Left history rail: 216–240 px and collapsible.
- Main conversation: flexible, with a readable content width of 680–800 px.
- Evidence rail: 340–400 px, sticky within the viewport, independently
  scrollable when needed.
- Keep the composer pinned near the bottom of the main conversation.
- Use borders and spacing to establish hierarchy, not floating card shadows.

### Mobile and narrow screens

- Collapse history behind a menu button.
- Place the conversation first.
- Move evidence into a full-width `Evidence` tab or bottom sheet; never squeeze
  paper cards into an unreadable side column.
- Stack medicine and cell-line inputs above the submit action below 640 px.
- Preserve inline citation links and make them open the matching evidence item.

## Visual direction

The visual reference is the supplied clean search/AI result screenshot: generous
white space, a readable answer column, a clearly separated sources rail, thin
neutral outlines, and a large grounded composer. It is inspiration for hierarchy
and density, not a pixel-for-pixel copy.

### Color tokens

```css
:root {
  --cb-background: #FFFFFF;
  --cb-surface: #FFFFFF;
  --cb-surface-subtle: #F6F6F6;
  --cb-text: #0A0A0A;
  --cb-text-muted: #5F6360;
  --cb-border: #DADDD9;
  --cb-border-strong: #AEB3AE;
  --cb-accent: #06A10B;
  --cb-accent-hover: #047E08;
  --cb-accent-soft: #EAF7EA;
  --cb-danger: #B42318;
  --cb-focus: #06A10B;
}
```

- The product is black and white first.
- `#06A10B` is the only brand highlight and primary action color.
- Use the accent for active states, links, focus rings, selected citations,
  positive chart direction, and small status marks.
- Never use gradients.
- Never use large decorative color fields.
- Do not use green for ordinary body text or large paragraphs.
- A negative SHAP direction may use black, charcoal, a pattern, or position on
  the opposite side of zero. Do not introduce an unrelated decorative palette.

### Typography

- Use `Inter`, `Arial`, or a system sans-serif stack.
- Body text: 15–16 px, line height 1.55–1.65.
- Page title: 24–30 px, line height 1.2, weight 650–700.
- Section title: 16–18 px, weight 650.
- Labels and metadata: 12–13 px, weight 500–600.
- Paper titles: 14–15 px, weight 650, no more than three lines before expansion.
- Prefer sentence case. Avoid all-caps headings except very short metadata labels.
- Use tabular numbers for scores, `LN_IC50`, latency, and SHAP values.

### Shape, borders, and depth

- Use 1 px neutral borders to separate regions.
- Default corner radius: 8 px.
- Composer radius: 14–18 px so it reads as the primary input surface.
- Pills are reserved for filters, statuses, and removable tokens.
- No heavy shadows. Default surfaces have no shadow.
- A transient popover may use `0 4px 16px rgba(0, 0, 0, 0.08)` at most.
- Do not use glassmorphism, bevels, glowing effects, or decorative blur.

### Spacing

- Base unit: 4 px.
- Common gaps: 8, 12, 16, 24, 32, and 48 px.
- Main page gutters: 24–32 px on desktop and 16 px on mobile.
- Evidence cards: 16 px internal padding and 16 px between cards.
- Keep long scientific text visually calm; do not compress paragraphs to fit
  more cards above the fold.

## Core components

### Application header

- CancerBench wordmark at left.
- `Research use only` label remains visible without appearing like an error.
- Model and embedding versions live in a compact details menu.
- Do not crowd the header with dashboard statistics.

### Conversation

- Researcher messages align to the right in a subtle gray surface.
- CancerBench responses align to the left and use the white page surface.
- Avoid avatar bubbles unless identities become important.
- Each response has one clear hierarchy: answer, explanation, evidence links,
  then technical metadata.
- Streaming or loading text should reserve space to avoid layout jumps.

### Query composer

- Provide labeled medicine and cell-line comboboxes with alias-aware search.
- Also accept a natural-language research question in the larger text area.
- Example placeholder: `Ask about Cisplatin response in SIDM00001...`
- Submit button uses `#06A10B`, white text, and a clear arrow or send icon.
- Enter submits; Shift+Enter adds a line.
- Disabled submission explains which required field is missing.
- Recent or valid selections should never be represented by placeholder text
  alone.

### Prediction summary

- Show the numeric `LN_IC50` prediction prominently but not theatrically.
- Always label the unit/target and explain that lower values indicate greater
  predicted sensitivity within the source research dataset.
- Show cell line, medicine, model version, and prediction timestamp.
- Include a persistent `Research only — not clinically validated` note.

### SHAP explanation

- Use a horizontal diverging contribution chart centered on zero.
- Show 8–10 strongest features by absolute contribution by default.
- Positive direction uses `#06A10B`; negative direction uses charcoal.
- Label the chart ends in plain language, not color alone.
- Every row includes feature name, signed value, and an accessible tooltip.
- Include base value, prediction, and `other_contribution` in a details section
  so the displayed explanation can reconstruct the result.
- State that SHAP describes model behavior, not biological causality.

### Scientific evidence rail

- Heading: `Scientific evidence`, with result count and active filters.
- Each card shows citation number, title, relevant snippet, PMID, year, journal,
  retrieval score, and a `View on PubMed` link.
- Show DOI and authors in expandable metadata when available.
- Highlight query terms sparingly with a pale green background and black text.
- Citation numbers are stable within an assistant response.
- Selecting an inline citation scrolls to and outlines the matching card in
  `#06A10B`.
- External links open safely in a new tab and retain the canonical source URL.
- Never present retrieval similarity as confidence that a scientific claim is
  true.
- If there is no strong evidence, say so directly and do not fill the rail with
  weakly related papers merely to occupy space.

### Filters

- Optional controls: year from/to, drug, gene, journal, and minimum relevance.
- Keep common filters visible; place advanced filters in a small disclosure.
- Active filters appear as removable outlined pills.
- A reset action must restore the unfiltered evidence set.

## States and feedback

- Empty: explain how to begin and provide two realistic example queries.
- Validating: show field-level progress without blocking the whole page.
- Predicting: skeleton only the response region.
- Explaining: prediction can render before SHAP if the service is still working.
- Retrieving: evidence rail shows compact line skeletons and its own status.
- Partial success: preserve prediction or explanation if literature retrieval
  fails, and offer a targeted retry.
- No evidence: distinguish no strong match from a service error.
- Error: plain-language summary, retry action, and a copyable request ID.
- Completed: announce updates with an ARIA live region without stealing focus.

## Interaction and accessibility

- Meet WCAG 2.2 AA contrast.
- All controls and chart details must work by keyboard.
- Use a 2 px `#06A10B` focus outline with a 2 px offset.
- Minimum interactive target: 44 by 44 px where practical.
- Do not use color alone to communicate SHAP direction, selected evidence, or
  service status.
- Honor `prefers-reduced-motion`.
- Motion is limited to short opacity or position transitions under 180 ms.
- Paper snippets and chart labels remain selectable and copyable.
- Use semantic headings, lists, forms, and links before adding ARIA.

## Content rules

- Say `medicine` in approachable form labels and `drug` in scientific metadata
  where that wording is more precise.
- Keep gene symbols uppercase and preserve official names in metadata.
- Use `cell line`, not `patient`.
- Never write `recommended treatment`, `best drug`, or similar clinical language.
- Differentiate model prediction, model explanation, and retrieved literature.
- Every scientific claim derived from retrieval must link to a visible citation.
- Display dates unambiguously and include ingestion date in provenance details.

## Implementation notes

- Build from reusable primitives: `AppShell`, `HistoryRail`, `Conversation`,
  `ResearchComposer`, `PredictionSummary`, `ShapChart`, `EvidenceRail`,
  `CitationCard`, `FilterBar`, `ServiceStatus`, and `ResearchDisclaimer`.
- Keep raw API records separate from view models so citation metadata and scores
  are formatted consistently.
- Preserve PMID as a string.
- Use URL state for the selected conversation, filters, and focused citation so
  research views can be shared and restored.
- Instrument prediction, explanation, and retrieval latency separately.
- Add component tests for loading, partial success, no evidence, long titles,
  missing DOI, keyboard citation navigation, and narrow screens.

## Explicit non-goals

- No clinical decision support.
- No treatment ranking presented as medical advice.
- No generic analytics dashboard as the primary experience.
- No gradient backgrounds, heavy shadows, oversized rounded cards, decorative
  glass effects, or multiple competing accent colors.
- No evidence card without a stable identifier and canonical link.
