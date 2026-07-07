# Engage2Win — Methodology Fundamentals

> Source of truth for the methodology the app supports. Extracted from the e2open
> **"Roadmap and Visioning Session — Activities Playbook"** (July 2025). This is what
> the app must understand: the workshop flow, the **maps** produced, each map's
> mechanics, and what a "good" map looks like (the basis for per-map-type RAG scoring).

The methodology itself already anticipates this tool: the playbook agenda calls out
*"Complete engage2win digital tool with map inputs"* and *"Use outcome from engage2win
digital tool"* (Day 2). The app is the digital counterpart to the hand-drawn maps.

---

## 1. The overall journey

Three phases (playbook p.2):

1. **Workshop Preparations** (3–5 weeks) — kick-off, scope, stakeholders, insight
   interviews, pre-workshop deliverables (problem-statement charters), asset selection.
2. **Visioning Workshop** (2 days) — the facilitated consensus session where the maps
   are created. **This is where the app is used.**
3. **Post-Workshop Activities** (1–2 weeks) — Paperflite, readouts, playback sessions,
   account alignment, value tracking; iterative engagement thereafter.

Transformation journey / consensus-building arc (p.7): Kick-off → SC Vision & Problem
Identification → Validation → Prioritization → Roadmap → Value Case → Implementation →
Value Tracking → Value Realization.

---

## 2. The 2-day Visioning Consensus Workshop

Agenda blocks and the **maps** each produces (playbook p.4–5, p.8–10):

| # | Agenda block | Day | Map produced |
|---|--------------|-----|--------------|
| 0 | Ice breaker (paper clip) | 1 | *Map Clip* (warm-up, not analysed) |
| 1 | Outside-In Perspectives | 1 | — (inspiration; optional partner) |
| 2 | Understand the SC Vision | 1 | **Vision Keywords Map** |
| 3 | Problem Statements | 1 | **Problem Statements Map** (SC-to-PS) |
| 4 | Define Success Metrics | 1 | **Metrics & Root-Cause Map** (value tree) |
| 5 | SC Planning Capability Map | 2 | **Capability Map** |
| 6 | Capabilities resolution paths | 2 | — (demos, stories) |
| 7 | Criteria Activity | 2 | **Criteria Map** |
| 8 | Rankings / Evaluation | 2 | **Capability Ranking Map** |
| 9 | Heatmap & Roadmap review | 2 | **Roadmap Map** |

Illustrative timings (p.9–10): Vision+PS 90m, Metrics 30m, Capabilities 180m, Criteria
30–60m, Ranking 120m, Roadmap 60m.

---

## 3. The map catalogue (what the app analyses)

Seven analysable maps (the icebreaker is excluded). For each: **purpose**, **mechanics**
(how it's run), **expected output**, and **evaluation signals** — what "good" looks like,
which become that map's per-type RAG dimensions.

### 3.1 Vision Keywords Map  (`vision_keywords`)  — Activity 1
- **Purpose:** capture the DNA of the customer's supply-chain vision as keywords and reach
  consensus on the few that matter.
- **Mechanics:** each participant writes 1–2-word keywords in silence (3–5 min); facilitator
  captures and **clusters** similar keywords on a shared map; participants explain; then
  **dot-voting** (3 votes each, **sponsor votes last** to influence); confirm consensus.
- **Expected output:** a prioritised keyword map with **3–5 validated clusters** the group
  agrees define the vision (stays on the wall all workshop).
- **Evaluation signals:** keywords are concise (not sentences); clear clustering; a
  manageable 3–5 clusters (not a sprawl); evidence of prioritisation/voting; sponsor
  influence visible; clusters genuinely express a vision.

### 3.2 Problem Statements Map  (`problem_statements`)  — Activity 3 (+ SC-to-PS)
- **Purpose:** validate interview insights and reach consensus on the most important
  problems blocking the vision.
- **Mechanics:** present top ~20 problem statements (from interviews) on one view; discuss
  ("Are you missing any? Which top 3 hinder the vision? Are they connected?"); optionally
  place problem statements against a **Supply Chain map** (SC-to-PS) to locate where each
  hurts; facilitator stickies key insights.
- **Expected output:** a validated, prioritised set of problem statements with a clear
  **top 3**, ideally connected to each other and to the SC.
- **Evaluation signals:** statements are real problems (not solutions in disguise);
  "how-might-we" framing; top 3 identified; connections/causality shown; tied to the vision
  and to points on the supply chain.

### 3.3 Metrics & Root-Cause Map (Value Tree)  (`metrics_root_cause`)  — Activity 2/4-D1
- **Purpose:** connect the vision to measurable business impact and expose the root causes
  behind the numbers.
- **Mechanics:** build a **value tree** — Key Metrics that drive business impact → Tier 2/3
  metrics that impact the customer → problem statements/root causes that affect each metric;
  contribution to P&L; teams work in 2 groups (~30 min) then compare maps. (See playbook
  "From KPIs to Root Causes", p.23.)
- **Expected output:** a single-pane view from KPIs down to root causes and consequences,
  linked to P&L impact.
- **Evaluation signals:** metrics tie to business/P&L impact (not vanity metrics); clear
  cause→effect chains; root causes reach real drivers (5-why depth), not surface symptoms;
  Tier 2/3 metrics connect up to the key metric; coverage across SC functions.

### 3.4 Supply Chain Capability Map  (`capability_map`)  — Activity 4
- **Purpose:** align on the e2open capabilities that could address the customer's challenges.
- **Mechanics:** present the **e2open SC Capability Framework** (6 functional areas, L1–L3),
  pre-filtered by industry relevance; explain each; discuss how each applies by region/
  business area; add change-management capabilities; select relevant ones. Assess current vs
  target, produce a **gap heat map**.
- **Expected output:** selected capabilities across the 6 areas with current/target maturity
  and a gap heat map of priority areas.
- **Evaluation signals:** capabilities chosen map to the problem statements/value drivers;
  coverage across the 6 areas where relevant; current-vs-target and maturity indicated;
  industry-relevant filtering; change-management included.
- **The six capability areas** (see §4): Sense & Manage your Channel · Plan your Supply &
  Distribution · Collaborate with Suppliers · Manage your Global Trade Operations · Manage
  your Transport · Orchestrate & Operate with Resilience.

### 3.5 Criteria Map  (`criteria`)  — Activity 5
- **Purpose:** agree the criteria used to prioritise/rank capabilities.
- **Mechanics:** silent brainstorm (3 min), facilitator groups inputs; consensus on **3–5**
  criteria; **sponsor buy-in on weightings**; define a **1→5 scale** description for each.
- **Expected output:** 3–5 weighted criteria, each with a clear 1-to-5 definition. Typical
  set: **Maximize Value, Strategic Alignment, Expected Business Case, Ability to Execute.**
- **Evaluation signals:** 3–5 criteria (not too few/many); each has a concrete 1→5 anchor;
  criteria are decision-useful and distinct; consensus/sponsor sign-off evident; criteria
  connect back to the vision.

### 3.6 Capability Ranking Map  (`capability_ranking`)  — Activity 6
- **Purpose:** score each capability against each criterion to produce a ranking.
- **Mechanics:** for **one capability at a time, one criterion at a time**, everyone votes
  1–5 simultaneously; facilitator reads votes, checks consensus/discrepancies, ignites
  discussion; merge capabilities to accelerate where sensible; skip clearly-irrelevant ones
  (score 1). Often shown as a **radar/spider** per capability.
- **Expected output:** every relevant capability scored per criterion, with consensus and
  noted discrepancies; an overall ranking.
- **Evaluation signals:** consistent 1–5 scale applied; coverage of the selected
  capabilities; discrepancies surfaced/discussed (not silently averaged); scores traceable
  to the criteria; a usable ranking emerges.

### 3.7 Roadmap Map  (`roadmap`)  — Activity 7/9
- **Purpose:** sequence prioritised capabilities into a directional roadmap.
- **Mechanics:** after voting, facilitator computes rankings and presents back; group agrees
  a sequence into **Business Release 1 / 2 / 3 / X (to be defined)**; select items for
  further exploration and future releases; note dependencies and parallelisation.
- **Expected output:** capabilities grouped into releases (~12-month directional view) with
  exploration areas flagged. (See playbook p.37.)
- **Evaluation signals:** clear release sequencing; ordering reflects the ranking/criteria;
  dependencies and parallel-run considerations noted; realistic scope per release;
  exploration/"to-be-defined" items separated from committed ones.

---

## 4. The e2open Supply Chain Capability Framework (reference)

Six functional areas and their L2 capabilities (playbook p.28, detail p.41–46). Used by the
Capability Map, Ranking, and Roadmap maps, and to pre-filter by industry.

- **Sense & Manage your Channel:** Forecast Collaboration · Inventory Collaboration · Sales
  Order Collaboration · Channel Data Management · Demand Signal Management.
- **Plan your Supply & Distribution:** Demand Planning · Demand Sensing · Inventory
  Optimization (MEIO) · Supply Planning · Supply Sensing · Allocation & Order Promising ·
  Distribution Planning · Sales & Operations Planning.
- **Collaborate with Suppliers:** Trading Partner Management · Supplier Forecast
  Collaboration · Manufacturing Collaboration · Supplier Inventory Collaboration · Purchase
  Order Collaboration · Supplier Network Discovery / Product Lifecycle Management.
- **Manage your Global Trade Operations:** Due Diligence · Compliance · Trade Agreements ·
  Duty Management · Customs Filing.
- **Manage your Transport:** Sourcing, Rating & Contracting · Planning & Optimization ·
  Booking & Tendering · Appointment Scheduling · In-transit Monitoring · Freight Audit &
  Settlement.
- **Orchestrate & Operate with Resilience:** Foundational ASN Visibility · Real-time
  Transportation Visibility · Advanced Logistics Visibility · Logistics Network Integration
  & Execution · Supplier Shipment Collaboration · Control Tower & Logistics Resolution.

---

## 5. How this drives the app

- **Map mechanics guidance (Epic B / R5):** each map's Purpose + Mechanics + Expected output
  (above) is the content shown before its upload placeholder.
- **Per-map-type scoring (Epic B / R2 decision):** each map's **Evaluation signals** become
  its RAG dimensions — a Vision map is judged on clustering/consensus; a Ranking map on
  scale consistency/coverage; etc. Still reported Red/Amber/Green.
- **Agenda alignment (Epic A):** the agenda categories/section library map onto these maps,
  so an agenda activity can be linked to the map it produces.
- **Source doc:** "Activities & Training for Visioning Workshop e2open August25.pdf"
  (Roadmap and Visioning Session – Activities Playbook, July 2025).
