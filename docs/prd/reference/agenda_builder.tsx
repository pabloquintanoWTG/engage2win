// REFERENCE ONLY — source of truth for porting the agenda builder into the
// Flask app (see docs/prd/engage2win-app-enhancements.md, Epic A / R4).
// This is the facilitator-built React (Claude Artifact) SPA. We are NOT running
// this file; we port its DATA (DEFAULT_SECTIONS, CATEGORIES, setup fields), its
// time-budget logic, and its HTML/PDF export into server-side Flask + vanilla JS,
// persisting to SQLite. Kept verbatim so nothing is lost.

import { useState, useEffect, useCallback } from "react";

/* --- Persistent Storage helpers (Artifacts window.storage) --- */
const store = {
  async get(k) { try { const r = await window.storage.get(k); return r ? JSON.parse(r.value) : null; } catch { return null; } },
  async set(k, v) { try { await window.storage.set(k, JSON.stringify(v)); return true; } catch { return false; } },
  async del(k) { try { await window.storage.delete(k); return true; } catch { return false; } },
  async list(prefix) { try { const r = await window.storage.list(prefix); return r?.keys || []; } catch { return []; } },
};

/* --- Brand colors (corporate palette used by the artifact) --- */
const BRAND = {
  sage: "#6B8E4E", sageLt: "#EBF2E4", sageMd: "#A8BF6E",
  cadet: "#1A6B6A", cadetLt: "#DFF0EF", cadetMd: "#5CC8C4",
  violet: "#5B2D8E", violetLt: "#ECE4F5", violetMd: "#9B7FC0",
  gold: "#8B7B22", goldLt: "#F5F0D8", goldMd: "#C5A332",
  mint: "#6BADA0", mintLt: "#E4F3F0",
  lime: "#8CC63F", limeLt: "#EDF7E0",
  carbonDk: "#2D2E2C", carbonMed: "#4A4A4A", carbonLt: "#8A8A8A",
  white: "#FFFFFF", offWhite: "#F7F6F3", warmGray: "#EEECE7",
  text: "#2D2E2C", textMuted: "#6E6E6A",
  breakBg: "#F0EDE6", breakColor: "#9E9A8E",
  inspire: "#1A6B6A", inspireLt: "#DFF0EF",
};

// Agenda categories — these map onto the Epic B map types:
//   Vision->vision, Value->value_visual, Problem->problem_statement,
//   Prioritise->ranking, (Criteria section)->criteria. Supply-chain map: no section yet.
const CATEGORIES = [
  { label: "Inspire", color: BRAND.mint, colorLt: BRAND.mintLt },
  { label: "Vision", color: BRAND.violet, colorLt: BRAND.violetLt },
  { label: "Value", color: BRAND.lime, colorLt: BRAND.limeLt },
  { label: "Problem", color: BRAND.gold, colorLt: BRAND.goldLt },
  { label: "Capability", color: BRAND.sage, colorLt: BRAND.sageLt },
  { label: "Prioritise", color: BRAND.carbonMed, colorLt: BRAND.warmGray },
  { label: "Next steps", color: BRAND.cadet, colorLt: BRAND.cadetLt },
  { label: "Intro / Closing", color: BRAND.carbonMed, colorLt: BRAND.warmGray },
  { label: "Custom", color: BRAND.violet, colorLt: BRAND.violetLt },
];

// The engage2win workshop section library — reuse this content in the Flask port.
const DEFAULT_SECTIONS = [
  { id: "welcome", type: "intro", name: "Welcome & introductions", category: "Intro / Closing", minutes: 15, enabled: true, description: "Welcome participants, set the scene, introductions round, ground rules, and agenda walkthrough.", activities: ["Sponsor welcome (2 min)", "Participant introductions round", "Ground rules & ways of working", "Agenda overview"], tips: ["Keep intros to name + role + one expectation", "Display the agenda visually on a wall poster", "Establish a 'parking lot' for off-topic items"], roles: "Sponsor (welcome), Facilitator (agenda)", materials: "Printed agenda, name tents, ground rules poster", output: "Aligned group with clear expectations" },
  { id: "outside_in", type: "section", name: "Outside-in perspectives", category: "Inspire", minutes: 45, enabled: true, description: "Bring external expertise and inspiration to the group before diving into visioning. Share industry challenges, emerging operating models, latest AI advances, or thought-provoking trends relevant to the customer's context.", activities: ["Industry landscape & trends overview (presenter)", "Emerging operating models showcase", "Technology & AI innovation spotlight", "Provocations & 'what if' questions", "Open Q&A and reflection"], tips: ["Tailor content to the customer's industry - generic decks fall flat", "Use real examples and case studies, not theory", "Keep it concise and energising - this is a spark, not a lecture", "End with 2-3 provocative questions to carry into Visioning"], roles: "Presenter / SME (lead), Facilitator (moderator), All participants", materials: "Presentation deck (tailored), industry benchmarks, printed key stats handout", output: "Inspired group with shared external context, 2-3 provocative questions for Visioning" },
  { id: "visioning", type: "section", name: "Visioning & ambitions", category: "Vision", minutes: 45, enabled: true, description: "Uncover the customer's supply chain vision. Align the team around aspirational keywords.", activities: ["Silent keyword writing (individual)", "Keyword clustering on vision map", "Dot voting on top themes", "Consensus check & lock-in"], tips: ["Let the sponsor vote last to avoid anchoring bias", "If >5 clusters emerge, force a prioritisation round", "Keep it simple - no explanations, just keywords"], roles: "Facilitator (lead), Sponsor (last voter), All participants", materials: "Vision keyword map (A0 poster), sticky notes, dot stickers, sharpies", output: "Prioritised vision keyword map with 3-5 validated clusters" },
  { id: "value_drivers", type: "section", name: "Value drivers", category: "Value", minutes: 45, enabled: true, description: "Map strategic value imperatives that connect vision to measurable business outcomes.", activities: ["Value tree introduction (facilitator)", "Small group value mapping exercise", "Cross-group share-back & challenge", "Value driver prioritisation"], tips: ["Use the value tree template to keep groups on track", "Challenge vague drivers - push for specificity", "Link every driver back to the vision keywords"], roles: "Facilitator, Small groups (3-4 per group), Note-taker per group", materials: "Value tree templates (A1), markers, timer", output: "Completed value tree with ranked strategic drivers" },
  { id: "break_morning", type: "break", name: "Morning break", category: "Intro / Closing", minutes: 15, enabled: true, description: "Coffee break - allow networking and informal discussion.", activities: [], tips: ["Have coffee/tea ready before the break starts"], roles: "All participants", materials: "Refreshments", output: "" },
  { id: "fishbone", type: "section", name: "Fishbone analysis", category: "Problem", minutes: 60, enabled: true, description: "Root cause identification using Ishikawa diagram methodology to surface systemic issues.", activities: ["Problem statement framing", "Category brainstorm (6M framework)", "Root cause deep-dive per category", "Cross-pollination & pattern identification"], tips: ["Don't let the group jump to solutions - stay in 'problem mode'", "Use the 5-Why technique if causes are too surface-level"], roles: "Facilitator, Category leads (1 per arm), All participants rotating", materials: "Fishbone template (A0), coloured sticky notes per category, markers", output: "Completed fishbone diagram with prioritised root causes" },
  { id: "problem_statements", type: "section", name: "Problem statements", category: "Problem", minutes: 45, enabled: true, description: "Transform fishbone outputs into clear, actionable problem statements.", activities: ["Problem statement writing (individual)", "Peer review & refinement in pairs", "Group validation & deduplication", "Final statement selection"], tips: ["Use 'How might we...' format", "Reject statements that are solutions in disguise"], roles: "Facilitator, All participants (individual + pairs)", materials: "Problem statement cards, pens, validation checklist", output: "5-8 validated, actionable problem statements" },
  { id: "break_lunch", type: "break", name: "Lunch break", category: "Intro / Closing", minutes: 45, enabled: true, description: "Lunch break - encourage informal networking.", activities: [], tips: ["Announce restart time clearly before break"], roles: "All participants", materials: "Lunch catering", output: "" },
  { id: "capability_review", type: "section", name: "Capability review", category: "Capability", minutes: 60, enabled: true, description: "Evaluate existing and required capabilities against problem statements and value drivers.", activities: ["Capability mapping introduction", "Current-state assessment", "Target-state definition", "Gap analysis & heat mapping"], tips: ["Use capability maturity model (1-5 scale)", "Focus on capabilities, not tools"], roles: "Facilitator, Domain experts, All participants", materials: "Capability matrix template, heat map stickers, scoring guide", output: "Capability gap heat map with priority areas" },
  { id: "criteria", type: "section", name: "Criteria definition", category: "Prioritise", minutes: 30, enabled: true, description: "Establish and weight evaluation criteria for prioritising initiatives.", activities: ["Criteria brainstorm", "Criteria grouping & selection", "Pairwise weighting exercise", "Criteria validation"], tips: ["Limit to 5-7 criteria maximum", "Get sponsor buy-in on weightings"], roles: "Facilitator, Sponsor (validation), All participants", materials: "Criteria cards, weighting matrix", output: "Weighted evaluation criteria set (5-7 criteria)" },
  { id: "break_afternoon", type: "break", name: "Afternoon break", category: "Intro / Closing", minutes: 15, enabled: true, description: "Short coffee break to recharge.", activities: [], tips: ["Keep it short - energy dips here"], roles: "All participants", materials: "Refreshments", output: "" },
  { id: "prioritisation", type: "section", name: "Prioritisation & ranking", category: "Prioritise", minutes: 60, enabled: true, description: "Score and rank initiatives against weighted criteria.", activities: ["Initiative scoring (individual)", "Score calibration discussion", "Ranking matrix completion", "Top-5 deep dive & validation"], tips: ["Use silent scoring first, then discuss outliers", "The sponsor breaks ties, not the facilitator"], roles: "Facilitator, Sponsor (tie-breaker), All participants (scorers)", materials: "Scoring matrix, calculators, ranking board", output: "Prioritised initiative ranking with scores and rationale" },
  { id: "next_steps", type: "section", name: "Next steps & roadmap", category: "Next steps", minutes: 30, enabled: true, description: "Define action items, assign owners, build implementation timeline.", activities: ["Action item definition per initiative", "Owner assignment & commitment", "Timeline mapping (30/60/90 day)", "Closing round & reflections"], tips: ["Every action needs an owner AND a deadline", "Don't overcommit - focus on top 3-5 actions"], roles: "Facilitator, Sponsor (commitment), All participants (owners)", materials: "Action plan template, timeline board, commitment cards", output: "Signed-off action plan with owners, deadlines, and 90-day roadmap" },
  { id: "closing", type: "intro", name: "Closing & reflections", category: "Intro / Closing", minutes: 15, enabled: true, description: "Wrap up with reflections, key takeaways, and thank-yous.", activities: ["One-word checkout round", "Sponsor closing remarks", "Feedback form distribution", "Photo & thank-yous"], tips: ["Keep it positive - end on energy", "Confirm follow-up meeting date before people leave"], roles: "Facilitator, Sponsor", materials: "Feedback forms, camera", output: "Participant reflections and feedback collected" },
];

// Setup fields captured by the artifact -> map to Customer + Session in the Flask port.
const DEFAULT_SETUP = { customer: "", industry: "", dayHours: [8], participants: "", roles: "", objectives: "", notes: "" };

const DURATION_PRESETS = [
  { label: "Half day", dayHours: [4] },
  { label: "Full day", dayHours: [8] },
  { label: "1.5 days", dayHours: [8, 4] },
  { label: "2 days", dayHours: [8, 8] },
  { label: "3 days", dayHours: [8, 8, 6] },
];

// ---- Time-budget + agenda-clock logic to port ----
const totalHours = (dh) => dh.reduce((s, h) => s + h, 0);
const formatTime = (minutes) => {
  const h = Math.floor(minutes / 60); const m = minutes % 60;
  return h > 0 ? (m > 0 ? `${h}h ${m}m` : `${h}h`) : `${m}m`;
};
const addTime = (st, min) => {
  const [h, m] = st.split(":").map(Number); const t = h * 60 + m + min;
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
};

// NOTE: The full React UI (Dashboard, SectionSelector drag/drop, EditModal, timeline,
// SectionDetail, PdfPreview) and the HTML/PDF export template live in the original
// artifact. When porting: rebuild these as Flask views + vanilla JS, and re-implement
// the export as a server-rendered print-friendly HTML page. The workflow is a 5-step
// wizard: Workshop setup -> Select sections -> Agenda timeline -> Section details -> Export.
//
// The remainder of the original component (UI rendering) is intentionally omitted from
// this reference to keep the reusable content (data + logic + brand + workflow) legible.
// If the full UI source is needed again, it is preserved in the project conversation
// history / the facilitator's Claude artifact.

export { store, BRAND, CATEGORIES, DEFAULT_SECTIONS, DEFAULT_SETUP, DURATION_PRESETS, totalHours, formatTime, addTime };
