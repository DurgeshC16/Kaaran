export const meta = {
  name: 'phase2-plan-review',
  description: 'Sequential read-only adversarial review of the Phase 2 plan from three lenses',
  phases: [
    { title: 'Requirements', detail: 'coverage of the user request + feasibility' },
    { title: 'Rules', detail: 'trust/confidence rule validity across seeds' },
    { title: 'Contract', detail: 'evidence schema + mapping JSON fitness for Phase 3/4' },
  ],
}

const ROOT = 'C:\\Users\\durge\\Documents\\System Desktop\\Projects\\Kaaran'
const PLAN = 'C:\\Users\\durge\\.claude\\plans\\cached-brewing-pinwheel.md'

const COMMON = `You are reviewing an implementation PLAN (not code) for Phase 2 of the Kaaran project.
Repo root: ${ROOT}. Plan file: ${PLAN}. Key context files: CLAUDE.md, PROGRESS.md, docs/PROJECT_CONTEXT.md, docs/SYNTHETIC_DATA_SPEC.md, and the Phase 1 generator in src/kaaran/synth/ (config.py, plant.py, tables.py, messy.py, writers.py, ground_truth.py, generate.py) plus tests/.
Seed-42 generated data exists (git-ignored) at data/synthetic/demo/ (raw/, clean/*.parquet, ground_truth.json, manifest.json).
STRICTLY READ-ONLY: do not edit or create any file, do not run git commands that change state, do not install packages. If you run Python, use the project venv (.venv/Scripts/python) with a heredoc on stdin (python - <<'EOF' ... EOF), compute in memory only (e.g. kaaran.synth.generate.build_clean(seed, 'solapur') returns (clean_tables_dict, planted) without writing files). Do not read whole data files; use head/row counts.
The user's Phase 2 request (verbatim) is:
---
${args.request}
---
Be adversarial and concrete: find real problems that would make execution fail, violate the user's rules, or waste the tight schedule. Do not pad with generic advice. Cite files/lines or computed evidence. Return at most 10 issues, most severe first, plus any decision the user must make that the plan's question list misses.`

const SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string' },
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
          area: { type: 'string' },
          problem: { type: 'string' },
          evidence: { type: 'string' },
          recommendation: { type: 'string' },
        },
        required: ['severity', 'area', 'problem', 'recommendation'],
      },
    },
    missing_questions: { type: 'array', items: { type: 'string' } },
  },
  required: ['verdict', 'issues', 'missing_questions'],
}

const LENSES = [
  {
    phase: 'Requirements',
    label: 'review:requirements',
    prompt: `LENS: requirements coverage and feasibility.
Check the plan against every instruction in the user's request: Stage 0 items (PROGRESS schedule text, slow marker semantics, CLAUDE.md commands, git workflow subject/body rule), Stage 1 (schema fields demanded: id, type, label set, structured numbers, sample sizes, provenance file/sheet-page/row-or-cell, template keys, no prose; committed sample path; commit+push right away), Stage 2 (deterministic loaders to DuckDB with provenance columns; ingest report listing every fix; column mapping as a JSON object applied+validated by code with a rule-based baseline; handle EVERY messiness item in ground_truth.json -- enumerate the actual messiness kinds produced by src/kaaran/synth/messy.py and check each has a concrete handling path; round-trip test >=99% rows and values within tolerance for seed 42 + two other seeds), Stage 3 (flat runs, z-score jumps vs history, missing months/schools, duplicates; tests: all T5 flagged, no T8 flagged, T6 insufficient; confirm detectability from RAW first), global rules (no LLM, provenance on every number, labels from rules documented in docs/CONFIDENCE_RULES.md, thresholds documented constants not tuned to a seed, commit+push per stage, stop after 3 identical failures, final PROGRESS update and report).
Also judge feasibility: Stages 0-3 should finish within about one working day so Phase 2B (causes, twins, confidence rules, eval harness) fits Oct 24-25. Identify scope that should be cut or simplified, and any ordering problem (e.g. Stage 1 schema depending on things only known later).`,
  },
  {
    phase: 'Rules',
    label: 'review:rules',
    prompt: `LENS: statistical validity and seed robustness of the trust rules (Stage 3) and the 2B rule sketches.
Study how the generator plants T1-T8 and the background noise (src/kaaran/synth/config.py, plant.py, tables.py, messy.py incl. PDF_MONTHS, PDF omissions, crosswalk gaps, background missing months/years). Then try to break each proposed rule in the plan: flat-run rule (>=3 consecutive months at 100% -- note the raw PDF window Jan-Mar 2024 + Jun-Dec 2024 has a Mar->Jun gap: what does 'consecutive' mean there, and do T5 noise runs starting Jun 2024 still count?), taluka RED_FLAG concentration rule, attendance jump rule (own-history z after removing district seasonal change, |delta|>=10), score jump rule (n-scaled z>=5 and |delta|>=20; persisting vs reverting), insufficient-school rule and taluka INSUFFICIENT >=20% (consider raw-layer extra gaps: PDF omissions + background gaps + unresolved links), CLEARED (bottom 5% attendance that passes all checks -- will all 15 T8 schools reliably land in the bottom 5% over seeds? will any T5 school?), and 2B sketches (trend STRONG via paired t, election WEAK via comparison talukas within +/-1, vacancy STRONG via exposed-vs-unexposed + replication + share, infra RULED_OUT, twin LEARN_FROM with decoy rejected by outcome).
Where possible, verify with in-memory Python across many seeds (e.g. 20-40 seeds using build_clean; you may also call kaaran.synth.messy.attendance_names / replicate crosswalk selection logic in memory as messy.py does, without writing files). Report concrete failure rates and propose principled (not seed-tuned) fixes with exact constants.`,
  },
  {
    phase: 'Contract',
    label: 'review:contract',
    prompt: `LENS: contract and integration design.
Evaluate the Evidence schema (Stage 1) and the ingest mapping JSON (Stage 2) for fitness with later phases described in docs/PROJECT_CONTEXT.md: Phase 3 (Claude intent parser; Claude proposes the column mapping from headers + format summaries only; Claude Brief Writer that must not invent numbers and works from template keys + params; a verifier that re-checks every number in the text against computed results), Phase 4 (web demo UI, Marathi-first one-page Evidence Brief PDF with provenance, one-minute voice summary, school drill-down list), and the eval harness (scoring planted-truth recovery and invented numbers).
Check: is every number traceable (provenance for aggregates such as a taluka mean over 140 schools: row ranges vs filter expressions vs both; PDF provenance as page + Sr No); can the brief writer render each of the six Evidence Brief items from PROJECT_CONTEXT.md (trend, election check, main cause, twin, data warning, suggested action) with only template keys + params; are labels/types/units/decimals sufficient for Marathi number formatting; does the schema support drill-down lists (e.g., the 11 vacancy schools, 23 flat-attendance schools) without bloating; versioning; synthetic marker propagation; how the mapping JSON's closed normalizer vocabulary acts as a guardrail for an LLM proposal and what validation errors look like; whether rule 5 (only aggregates to the LLM) is respected by the 'headers + format summaries' idea.
Propose concrete, minimal schema changes (field names and shapes) where needed. Avoid gold-plating: the user wants tight scope.`,
  },
]

const results = []
for (const lens of LENSES) {
  phase(lens.phase)
  const r = await agent(`${COMMON}\n\n${lens.prompt}`, { label: lens.label, phase: lens.phase, schema: SCHEMA, agentType: 'Plan' })
  results.push({ lens: lens.label, review: r })
  log(`${lens.label}: ${r ? r.issues.length + ' issues' : 'no result'}`)
}
return results
