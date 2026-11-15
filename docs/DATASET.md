# VENDOR: data card

Every figure below was counted from the released dialogue files themselves, after
anonymisation, not from an earlier version of the data.

## At a glance

| | |
|---|---|
| Dialogues | 715 |
| Source bid requirement sets | 431 |
| Utterances | 2,770 |
| Turns per dialogue | mean 3.87, range 2 to 8 |
| Distinct products in the rankings | 5,662 |
| Distinct suppliers in the rankings | 1,440 |
| Buyer requirements per scenario | median 47 (median 3 hard) |
| Terminal move | best available offer, in all 715 |
| Language | English |

## Files

Everything sits in `data/`, ready to read. The large files are gzipped individually so
every file stays well inside GitHub's size limits; the loaders, `show_conv.py` and
`tools/make_splits.py` all read `.gz` directly, so nothing has to be unpacked. `gunzip -k`
any of them if you prefer plain text.

| File | Rows | Size | What it is |
|---|---|---|---|
| `train.jsonl.gz` | 500 | 21 MiB | one dialogue per line, with rankings, compliance detail and provenance |
| `validation.jsonl.gz` | 73 | 2.9 MiB | same shape |
| `test.jsonl.gz` | 142 | 5.9 MiB | same shape |
| `splits.json` | n/a | 11 KiB | the seed, the targets, and the bid ids assigned to each part |
| `final_constraints.csv.gz` | 35,053 | 3.0 MiB | buyer side requirements extracted from the source bids |
| `gem_bids_metadata.csv` | n/a | 470 KiB | bid level metadata (category, department, dates) |
| `bids.txt` | 571 | 11 KiB | the candidate bid allowlist, one id per line; 431 produced dialogues |
| `suppliers.csv` | 1,440 | 263 KiB | supplier records referenced by the dialogues |
| `products.csv.gz` | 5,662 | 3.0 MiB | candidate listings referenced by the dialogues |
| `product_constraint.csv.gz` | 73,833 | 1.9 MiB | per product extracted specification claims |
| `supplier_products.csv` | 11,925 | 2.4 MiB | supplier to product mapping |
| `sample_dialogues.jsonl` | 2 | 1.5 MiB | the first two dialogues of `train.jsonl`, uncompressed |

The three dialogue files are a partition: concatenated, they are exactly the 715 records,
and no bid appears in more than one of them. `docs/ANONYMIZATION.md` records what the
anonymisation changed.

The catalogue CSVs hold exactly the rows some dialogue references: a ranking, an offer,
a compliance row or a quoted utterance. Rows no dialogue ever touches were dropped.

## One dialogue

```
scenario_id, run_id, bid_ref
buyer_profile       company_name, industry, city, style
persona             tier, tau, tolerance, patience_rounds, decision_randomness,
                    max_relaxations, counter_band, ranking_weights, persona_seed
commercial_brief    constraints[], scenario_meta
turns[]             speaker, turn_idx, action, utterance,
                    proposal, item_responses, counter_value, proposal_outcome,
                    buyer_truth_state_after, negotiator_belief_state,
                    feasible_count_truth, feasible_count_belief,
                    revealed_constraint_ids, proof_requests, llm_call_ids
final               outcome, best_available, best_available_reason,
                    reference_ranking, reference_ranking_initial, negotiator_ranking,
                    compliance_detail_truth, compliance_detail_belief,
                    accepted_relaxations, pending_verification_docs, proof_requests
relaxation_analysis[]   per-turn front points, chosen point, bounds before/after
provenance          prompt_versions, persona_seed, negotiator_seed, settings_hash,
                    llm_model, llm_backend, llm_calls, n_candidates
qa_flags[]
top1_match_original, top1_perfect_deal
```

### A requirement

Each entry of `commercial_brief.constraints` carries `constraint_id`, `attribute`,
`operator`, `buyer_value`, `unit`, `hardness`, `scope`, `constraint_category`,
`constraint_type`, `golden_param`, `is_doc_proof`, `evidence_coverage`,
`scenario_role`, `role_reason`, `framing_decision`, `framing_reason`, `provenance`,
`raw_text` and `evidence_anchor` (the span in the source document the requirement was
read from).

`hardness` is `HARD` or `SOFT`. A requirement marked as a golden parameter in the source
bid is hard; everything else, including the synthetic commercial terms, is soft.

### Identifiers

`product_id` and `supplier_id` are keyed pseudonymous tokens, `PROD_<12 hex>` and
`SUP_<12 hex>`. The same token stands for the same listing or supplier in every file,
the catalogue CSVs included, so every join resolves; it is not a marketplace identifier
and carries no route back to one. `scenario_id`, `run_id`, `bid_ref` and `constraint_id`
are the pipeline's own ids and are intact.

### A ranking row

`reference_ranking`, `reference_ranking_initial` and `negotiator_ranking` share one row
shape: `product_id`, `supplier_id`, `rank`, `score`, `utility`, `p_feasible`,
`p_recommend`, `match_original`, `eligible`, the per feature scores (`spec_match`,
`price_score`, `price_vs_budget`, `moq_fit`, `location_match`, `tenure_years`,
`rating_bayes`, `rating_count`, `evidence_confidence`), the compliance counts
(`hard_pass`, `hard_fail`, `hard_unknown`, `soft_pass`, `soft_fail`, `soft_unknown`),
and `verification_required` / `pending_verification_docs`.

`p_feasible` is the product of the per requirement pass probabilities; `score` is
`p_feasible` times the persona weighted utility; `p_recommend` is the softmax of `score`
over eligible rows, so it is a selection probability over the shortlist, not a second
ranking signal.

`reference_ranking_initial` is computed on the buyer's requirements before any
concession; `reference_ranking` on the requirements after the accepted ones are applied.
`negotiator_ranking` is computed from the negotiator's beliefs, so the cost of a wrong
belief is measurable against the reference.

## Splits

The dialogues arrive in three parts, train / validation / test at 70 / 10 / 20, purely as
a convenience. The split is on `bid_ref` with seed 42, because one bid yields several
dialogues that share a requirement set: a split by record would put the same requirements
in two parts.

| Part | Dialogues | Bids | of which template worded |
|---|---|---|---|
| train | 500 | 298 | 117 |
| validation | 73 | 48 | 20 |
| test | 142 | 85 | 23 |

No bid is shared between any two parts, and nothing is held back: all 715 dialogues are
there, the 160 with a template worded turn included.

Treat the three files as one dataset if that suits you better. Concatenated they are
exactly the 715 records, so you can ignore the split entirely, or split again them your own
way:

```bash
zcat train.jsonl.gz validation.jsonl.gz test.jsonl.gz > conversations.jsonl
```

`splits.json` records the seed, the targets and the bid ids in each part.
`tools/make_splits.py` regenerates the same assignment from a combined file, so the split
can be reproduced or replaced:

```bash
python tools/make_splits.py conversations.jsonl out/splits
```

## Distributions

**Persona tier.** lenient 210, medium 162, medium_strict 155, strict 188.

**Turn actions.** OPEN_REQUEST 715, PROPOSE_RELAXATION 654, BEST_AVAILABLE 715,
COUNTER 315, YES 201, NO 121, WRAP_UP 22, MIXED 17, ACKNOWLEDGE 10.

**Relaxation proposals.** 654 proposals: 31% accepted, 48% countered, 18% refused,
3% split across items. 187 dialogues (26.2%) end with at least one accepted relaxation.
In 91 of those (12.7% of all dialogues) the accepted relaxation changes the top 1
candidate; every top 1 change falls inside the 187.

**Belief error.** The negotiator's top 1 differs from the reference top 1 in 121
dialogues (16.9%).

**Why the dialogue closed.** All 715 close on a best available offer:
`no_feasible` 481, `nothing_verified` 212, `patience_exhausted` 22.

**Calibration.** `scenario_meta.calibration.in_band` is true for 164 of 715 scenarios
(22.9%): lenient 124/210, medium 1/162, medium_strict 2/155, strict 37/188. The per tier
feasibility targets in `config/settings.yaml` are the targets the scenario builder aimed
at, not a property the released scenarios have. Treat the tier label as the persona's
hardness band, not as a calibrated difficulty level.

**Wording fallback.** 160 dialogues (22.4%) contain at least one turn whose wording came
from the deterministic template rather than the model, covering 187 turns (6.8% of all
turns). They carry a `template_fallback` qa_flag. The facts in such a turn are the same
code built facts; only the phrasing differs.


## If you split again

Group by `bid_ref`, not by `scenario_id`: one bid produces several dialogues that share a
requirement set, so splitting on the dialogue id leaks those requirements across parts.
`tools/make_splits.py` does this, and `splits.json` records what the release used.
