# Evidence Schema (v1.0)

The Evidence pack is the engines' only output. The Brief Writer (Phase 3) and the UI/PDF (Phase 4) read nothing else.
It holds structured numbers with provenance, entities, sets, periods, labels and wording **template keys**. It never holds prose.

- Code: `src/kaaran/evidence.py`: `validate(pack)`, `finalize(pack)`, `llm_view(pack)`, plus the registries named below.
- Sample: `data/samples/evidence_pandharpur.json`. It is hand-built from seed-42 data (`"illustrative": true`) so UI work can start now. The Phase 2B pipeline replaces it with real output.
- Labels come from deterministic rules (`rule_id`) described in `docs/CONFIDENCE_RULES.md`. Labels are never LLM judgment.

## Top level
| Field | Meaning |
|---|---|
| `schema_version` / `template_registry_version` / `engine_version` / `mapping_sha256` | Versions needed to reproduce and compare packs |
| `synthetic`, `marker` | `synthetic` must equal any(source.synthetic). When true, UI, PDF and voice must show `marker` |
| `scope` | `{district, focus, subject, std, period, question}`; ids refer to entities, periods and text keys |
| `sources[]` | `{id, file, kind: xlsx\|csv\|pdf, sha256, synthetic, marker_at}` |
| `entities{}` | `id -> {kind: district\|taluka\|cluster\|school, code, name_en, name_mr?, taluka?, cluster?}`. Taluka ids are `T` + block code (`T08`); school ids are `S` + UDISE code |
| `entity_sets{}` | `id -> {kind, rule_id, members[]}`. Sets are always complete; shortening a list is the UI's job |
| `periods{}` | `id -> {kind: academic_year\|year_range\|month\|month_range, from, to}` |
| `numbers{}` | Number registry (below). Findings only reference ids, so a shared number cannot disagree with itself |
| `findings[]` | Finding list (below) |
| `outline[]` | `{section, finding_ids}`. Sections: `trend, election_check, main_cause, twin, data_warning, action, appendix`. Filled by a written rule in the pipeline, so Claude never decides which cause is "main" |

Ids are deterministic and meaningful (e.g. `n.score_mean.T08.2025-26`, `set.vacancy_maths.T08`), so packs diff cleanly across seeds.

## Number
`{value, unit, decimals, display{en, mr}, direction?, of?, out_of?, n?, entity?, derivation?{op, inputs[]}, provenance[]}`

- **Units**:
  - `score` and `score_change` (Std 3 marks).
  - `pct` and `pct_point_change`.
  - `count`, which needs `of`: schools, talukas, months, years, teachers, students or rows.
  - `rank`, which needs `out_of`.
  - `t_stat`, `corr`, `months`.
- **Display**: `finalize()` fills `display` with one formatter: Decimal ROUND_HALF_UP, Indian digit grouping, Devanagari digits for `mr`. Nobody else rounds.
  - Change units show the magnitude only. `direction` (`up|down|flat`) carries the sign, so Marathi can say "घसरण" or "वाढ".
- **Changes add up**: a displayed change equals the difference of its displayed inputs, within one last-digit unit. The validator checks every `diff`.
- **Traceability**: every number has `provenance` or `derivation.inputs`; inputs must have provenance in turn.
- **Derivation ops**: `mean, sum, count, count_distinct, diff, ratio, pct, share_of_decline, rank_desc, paired_t, corr, max_run, set_size, mean_change, count_where`.

## Provenance (tagged union)
| kind | Shape | Use |
|---|---|---|
| `cells` | `{source, sheet?, rows[], columns[]}`; PDF: `{source, page, section, sr_no[], columns[]}` | Up to about 20 exact cells |
| `query` | `{source, view, where{field: value \| [values]}, n_rows}` | Aggregates. Re-runnable on the canonical DuckDB views (equality / IN only) |
| `constant` | `{rule_id, name}` | A documented threshold from CONFIDENCE_RULES.md |

**Row numbering convention**
- Excel: sheet name + 1-based physical row, title rows included (A1 cells can be derived).
- CSV: 1-based physical line, including the title line and the header.
- PDF: 1-based page + section heading (`Taluka: <name> | <YYYY-MM>`) + Sr No. Sr No alone is not unique on a page.

**Canonical views** are built by ingest (Stage 2). Their columns mirror the clean truth tables plus ids, and every row also carries `src_id, src_sheet, src_page, src_section, src_row`.
- `talukas`: taluka_id, block_code, taluka, taluka_mr, n_schools
- `schools`: udise_code, short_code, school_name, village, taluka_id, cluster_code, cluster, enrol_std1-5, enrol_total, toilets, library, drinking_water, classrooms
- `scores`: udise_code, taluka_id, academic_year, std, subject (`maths`), mean_score, students_appeared
- `attendance`: udise_code, taluka_id, academic_year, month, enrolled, present_avg, attendance_pct
- `teacher_posts`: udise_code, taluka_id, academic_year, subject, sanctioned, working
- `election_duty`: taluka_id, academic_year, month, deployed_pct

## Finding
`{id, type, label, rule_id, template_key, params{name: {number|entity|set|period|text_key: id}}, hypothesis?, origin?, criteria[], sample{}, caveats[{template_key, params}], related[], action?}`

| type | allowed labels |
|---|---|
| TREND | STRONG, WEAK, INSUFFICIENT |
| CAUSE | STRONG, WEAK, RULED_OUT, INSUFFICIENT (`hypothesis`: vacancy\|election\|infrastructure\|attendance; `origin`: asked\|default) |
| TWIN | LEARN_FROM, INSUFFICIENT |
| DATA | RED_FLAG, INSUFFICIENT, CLEARED |
| ACTION | ACTION (`action{actor_role: DEO\|BEO\|KENDRA_PRAMUKH, based_on[], targets?: set id, horizon, within_officer_powers}`) |

- **Label meanings**:
  - WEAK: a pattern exists, but similar blocks show it too.
  - RULED_OUT: tested, no link found in this data.
  - CLEARED: looks unusual but passed every trust check (protects honest schools).
- **Badges**: badge text keys are `label.<TYPE>.<LABEL>`, so the Marathi wording can differ by type (a WEAK cause vs a WEAK trend).
- **Criteria**: `criteria[]` lists each rule criterion `{id, number?, threshold?, passed}`, so the brief can explain why a label was given.

## Template keys (registry v1; required params)
- `trend.decline_rank`, `trend.rise_rank`: taluka, period, score_from, score_to, change, rank_from, rank_to
- `trend.no_clear_change`: taluka, period, change
- `cause.election.similar_blocks_no_drop`: taluka, period, focus_change, similar (set), n_similar_no_drop
- `cause.vacancy.concentrated`: taluka, subject, schools (set), since, group_change, others_change, share_of_decline
- `cause.infra.no_link`: taluka, r, lowest_infra_taluka, lowest_infra_change
- `cause.attendance.no_link`: taluka, r
- `twin.learn_from`: twin, focus, twin_change, twin_rank_from, twin_rank_to, n_schools_twin, n_schools_focus (optional: decoy, decoy_change)
- `data.flat_attendance`: taluka, schools (set), months (period), n_months, share, rest_share
- `data.insufficient`: taluka, schools (set), share
- `data.cleared_low_attendance`: taluka, schools (set)
- `action.redeploy_teachers`: taluka, subject, schools (set)
- `action.exposure_visit`: twin, focus
- `action.verify_registers`: taluka, schools (set)
- `action.collect_missing_data`: taluka, schools (set)

**Caveat keys**:
- `caveat.synthetic_data`
- `caveat.associated_not_caused`
- `caveat.concentrated_in_few_schools` (schools)
- `caveat.poverty_not_available`
- `caveat.static_infra_snapshot`
- `caveat.small_sample`
- `caveat.flagged_data_excluded` (schools)

**Text keys**: `subject.maths`, `subject.language`, `question.why_decline`.

## What may go to an LLM (rule 5)
Only `llm_view(pack)`:
- Removed: school entities, set members (replaced by sizes), numbers about a single school, raw row lists and `where` filters, file hashes.
- Kept: talukas, labels, template keys, aggregate numbers with their `display` strings.

The UI and PDF build drill-down lists from the full pack in code. Recommended Phase 3 contract: Claude writes placeholders like `{{n:<id>}}`, and code fills in `display.mr`. That makes the number verifier exact.

## Answer-key mapping (for the eval harness)
| ground_truth verdict | expected evidence |
|---|---|
| STRONG (T1) | TREND finding, label STRONG, focus taluka |
| WEAK_CAUSE (T2) | CAUSE, hypothesis `election`, label WEAK |
| STRONG (T3) | CAUSE, hypothesis `vacancy`, label STRONG; set equals the planted schools |
| LEARN_FROM (T4) | TWIN, label LEARN_FROM, twin = planted twin (not the decoy) |
| RED_FLAG (T5) | DATA `data.flat_attendance`, label RED_FLAG; set equals the planted schools |
| INSUFFICIENT (T6) | DATA `data.insufficient`, label INSUFFICIENT, sparse taluka |
| NOT_A_CAUSE (T7) | CAUSE, hypothesis `infrastructure`, label RULED_OUT |
| NOT_FLAGGED (T8) | none of the planted schools in any RED_FLAG/INSUFFICIENT set (scored by recall of CLEARED, not precision) |
