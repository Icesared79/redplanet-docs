# How the Pipeline Works & Self-Correction & Healing

Atlas operates as a continuous ingestion and enrichment engine. At any given moment hundreds of runners are executing across dozens of data source categories — pulling, normalizing, verifying, and storing records without human intervention. Understanding how this works is essential to understanding what the data asset actually is, how it stays current, and how it stays healthy at scale.

<!-- SCREENSHOT: Pipeline health view showing live runner activity and nightly cycle status -->

## Source Discovery

Atlas does not rely on a fixed list of manually curated sources. The engine includes an autodiscovery layer that continuously identifies new data sources across government portals, court record systems, county assessor databases, state entity registries, and similar public-record domains. When a new source is identified it is added to the source registry, categorized, and queued for ingestion development.

Currently Atlas tracks **985** source baselines across **24** categories. Of those, **447** are active and ingesting data. The remainder are in various stages of discovery, development, or remediation.

## The Runner Framework

Each data source has a dedicated runner responsible for connecting to that source, extracting the data, normalizing it to Atlas schema, and writing it into the data asset. Runners are standardized in structure but customized per source. They handle authentication, pagination, rate limiting, and error recovery independently.

**606** runners are currently in the system. Every execution is logged — status, records processed, errors encountered, and timing — creating a complete audit trail of every data operation Atlas has ever performed.

## Ingestion & Normalization

Raw data arrives in many formats — HTML, XML, CSV, JSON, PDF, API responses. The normalization layer converts everything to a consistent schema before it lands in Atlas. Property identifiers are standardized, addresses are parsed and validated, dates are normalized, and duplicate records are detected and resolved before writing.

## Verification & Quality Tiering

Once normalized, records are evaluated for quality. Atlas maintains a four-tier classification system — Verified, Usable, Review, and Unreliable — based on source reliability, corroboration across multiple sources, and internal consistency checks. Quality classification runs automatically and records are re-evaluated as new corroborating data arrives.

## Signal Generation

After ingestion and verification, signal generation runs against new and updated records. Signals evaluate records against defined criteria — distress indicators, equity thresholds, ownership patterns, market velocity metrics — and the resulting derived intelligence is written into the signals layer. This is the step that converts raw records into actionable intelligence.

## Nightly Cycle

The full pipeline runs nightly. Source runners execute concurrently, followed by gap discovery, quality evaluation, and signal generation. The cycle is engineered to maintain a high completion rate across hundreds of concurrent operations. Failed runs are logged, flagged, and prioritized for the self-correction layer.

## Self-Correction & Healing

A data platform that requires constant human intervention to stay healthy does not scale. Atlas is designed to detect, diagnose, and recover from failures automatically — without a human in the loop for routine problems. The self-correction layer is what makes the nightly cycle sustainable at this concurrency without a team behind it.

## How Failures Are Detected

Every runner execution is logged and continuously monitored. Failures, silent sources, and quality regressions are identified automatically and routed to the appropriate response path. Detection is not reactive — the system identifies degradation patterns before they become failures, so investigation begins before a source goes fully offline.

## Automated Recovery

When a problem is detected the self-correction layer attempts recovery automatically. Issues that can be resolved programmatically are resolved without human involvement. Issues that cannot are escalated with full diagnostic context so a human can intervene with complete information rather than diagnosing from scratch.

## Source Health Monitoring

Every source in Atlas carries a health status that updates automatically based on execution history and data-flow patterns. A real-time view of the entire source ecosystem is maintained at all times — which sources are performing, which are degrading, and which need attention.

This visibility is what makes managing a platform of **447** active sources tractable. At any given moment the health of every data source is known, classified, and actionable.

<!-- SCREENSHOT: Source ecosystem health overview -->

## Gap Discovery

Beyond monitoring existing sources Atlas actively identifies coverage gaps — geographies, data categories, or asset classes where coverage is thin or missing entirely. The gap discovery system scores these gaps by priority and automatically queues new source development to fill them. The platform does not wait to be told where it is incomplete — it finds out on its own.

---

*All figures current as of 2026-05-05 13:56 UTC. Atlas ingests new data nightly — record counts update automatically.*
