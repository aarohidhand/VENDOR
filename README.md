# VENDOR: Verified Evidence Negotiation Dialogue Benchmark for Supplier Recommendation

This repository holds the **VENDOR** dataset and the pipeline that generated it:
715 multi turn dialogues between a buyer and a negotiator for B2B supplier
recommendation, in which a buyer states firm requirements, concedes flexible ones, and
the negotiator closes on a ranked shortlist of the nearest available matches, together
with what each one still leaves open.

Procurement recommenders are usually judged on the list they return. VENDOR records what
happens before the list: a buyer deciding what to give up, one requirement at a time,
with the evidence for every decision. Language models write the utterances; the
compliance labels, relaxation decisions and rankings come from deterministic code, so
every label can be recomputed from the record.

> **Anonymous artifact for double blind review.** This repository deliberately carries no
> author, institution, or contact information, and its history starts at the submitted
> snapshot. Please do not add identifying metadata before the review period ends.

## What is here

```
README.md                 this file
config/settings.yaml      every tunable constant: gates, levels, weights, tiers, limits
prompts/                  the 16 prompt versions that produced the released dialogues
src/gtgen/                the generation pipeline
  contracts.py            the schema every record is validated against (pydantic)
  data/                   loading, scenario construction, persona, calibration, call planning
  dialogue/               the turn loop, buyer policy, negotiator, final offer, assembly
  llm/                    client, batching, pacing, prompt rendering, output checks
  matching/               compliance, evidence, relaxation front, buyer decision, offer
  ranking/                the ranking matrix
scripts/live_all_bids.sh  one bid per process, sequential, checkpointed
show_conv.py              pretty-print a dialogue from a JSONL file
tools/make_splits.py      rebuild the bid-disjoint train/validation/test split
data/                     the released dataset: train/validation/test dialogues,
                          the catalogue CSVs, splits.json, and two sample dialogues
docs/DATASET.md           data card: counts, schema, distributions, known issues
docs/ANONYMIZATION.md     what was removed or tokenised, and what was verified
```

## The dataset

Look at one dialogue:

```bash
python show_conv.py data/train.jsonl.gz
```

Nothing needs unpacking first. The large files are gzipped one by one, and the pipeline,
the viewer and the splitter all read `.gz` directly; `gunzip -k` them if you would rather
work with plain text.

The dialogues ship already split by bid (seed 42, 70/10/20) as `train.jsonl.gz` (500),
`validation.jsonl.gz` (73) and `test.jsonl.gz` (142); no bid crosses a split, and the 160
dialogues whose wording fell back to the template are kept, not dropped. Concatenating the
three restores the full 715, so the split can be ignored or redone:

```bash
zcat data/train.jsonl.gz data/validation.jsonl.gz data/test.jsonl.gz > conversations.jsonl
```

715 dialogues over 431 source requirement sets, 2,770 utterances, mean 3.87 turns,
5,662 candidate products from 1,440 suppliers, median 47 buyer requirements per scenario
of which 3 are hard. Counts, the full record schema, the outcome and tier distributions,
and the known issues are in **[docs/DATASET.md](docs/DATASET.md)**. Read that before
training on the data; it states which claims the data supports and which it does not.

## How a dialogue is built

Requirements come from publicly posted government tender documents. A requirement the
tender marks as a golden parameter is **hard**; every other requirement, and the
synthetic commercial terms added on top (budget, quantity against minimum order, preferred
states), is **soft**. Candidates are public marketplace listings: price, minimum order
quantity, specifications, description, brochure text, location, rating, tenure.

Each requirement set becomes a scenario in five stages:

1. **Reframe.** Rewrite the requirements as a commercial brief, deciding per requirement
   whether to keep, translate, drop or merge it. Nothing that identifies the tender
   process survives into what either speaker says.
2. **Evidence.** A keyword prefilter and an LLM classifier read each listing against each
   requirement and label the claim PASS, FAIL or UNKNOWN. A failed call yields UNKNOWN,
   never PASS, and a documentary claim counts only if the quote it cites occurs in the
   listing text.
3. **Roles.** Requirements that no candidate in the pool can evidence are demoted to
   verification only, so missing evidence is never silently scored as a pass.
4. **Persona.** Fix the buyer's hardness level, per category tolerances, patience, a
   concession cap and ranking weights, then tighten the commercial terms until fewer
   candidates are feasible than the minimum shortlist, so there is something to negotiate.
5. **Gates.** Validate the scenario, and record its tier and its distance from that
   tier's target feasibility band.

Then the dialogue runs. The buyer opens with part of the brief and reveals more as asked.
The negotiator sees only the transcript and the catalogue; it never sees the buyer's
hidden requirements, the feasibility counts, the persona weights or the reference scores.
It extracts beliefs from what it has heard. It proposes the smallest bundle of relaxations
that would make a candidate eligible, over soft requirements only, and only where the
catalogue shows a candidate would actually be gained.

The buyer's reply is code, not a model: hard requirements are refused; documentary
requirements are bypassed pending verification; a soft requirement with tolerance `T` and
a proposed level `r ≤ T` is accepted, and otherwise countered or refused by a seeded
decision rule.

## The closing move

**Every dialogue ends with a best available offer, and that is the intended terminal
move, not a failure branch.** A procurement negotiation is informative exactly when the
catalogue cannot satisfy every requirement at once: the useful output is the ranked
nearest matches, each annotated with what it fails and what remains unverified.

The offer is reached once no further relaxation would add a feasible candidate
(`no_feasible`), once the open requirements cannot be verified from the listings
(`nothing_verified`), once the buyer's patience is spent (`patience_exhausted`), or at the
turn cap. All 715 released dialogues close this way; the reason is recorded per dialogue
in `final.best_available_reason`.

There is no separate "the requirements were all met, here is your match" branch in this
pipeline, in the schema, or in the data.

## Relaxation model

For candidate *i*, `p_i = Π_c p_ic` over the scored requirements: a pass contributes its
evidence confidence, discounted 10% when the evidence is unverified text; a soft fail
contributes 0.3; a soft unknown 0.5; a hard fail or unknown contributes 0, making the
candidate ineligible. The score is `s_i = p_i · Σ_f w_f φ_f(i)`, with features for
specification match, price, location, tenure, minimum order fit, Bayesian shrunk rating
and evidence confidence, under the persona's weights `w_f`.

A relaxation level is a relative change from the requirement's original value, drawn from
a fixed ladder (`relaxation.levels` in `config/settings.yaml`), never compounded. Bundle
cost is `Σ_c weight_c · r_c / L_c`, computed in exact rational arithmetic. The negotiator
enumerates the joint front over believed soft numeric rules, offers the authorised points,
and never proposes a change that gains no candidate. Hard requirements and documentary
requirements are never relaxed; both gates are off by default and the documentary kind is
immutable regardless.

## Reproducing the pipeline

Python 3.11 or newer.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
```

The pipeline reads the catalogue CSVs from a data folder and calls one open weight model
through an OpenAI compatible endpoint. Provide your own key through the environment; no
key, `.env` file or cached response is distributed with this repository.

| Variable | Used by |
|---|---|
| `OPENROUTER_API_KEY` | fallback for every role below |
| `OPENROUTER_API_KEY_PREP` | reframe, doc_classify, align, normalise |
| `OPENROUTER_API_KEY_CLAIMS` | doc_claim, claim_check |
| `OPENROUTER_API_KEY_PERSONA` | persona generation |
| `OPENROUTER_API_KEY_BUYER` | buyer opening, reply, reveal, reveal check |
| `OPENROUTER_API_KEY_NEGOTIATOR` | every negotiator prompt |

Separate keys only spread the provider's per key rate limit; one key in
`OPENROUTER_API_KEY` is enough to run.

One requirement set, one persona:

```bash
export GTGEN_RAW_DIR=data
python -m gtgen.cli pilot --live --personas 1 --bid GEM/2019/B/209245
```

`data/bids.txt` is the allowlist of 571 candidate bids; 431 of them
produced the released dialogues. To run every bid in it, one process each, checkpointed
after each finished dialogue:

```bash
scripts/live_all_bids.sh data
DRY_RUN=1 scripts/live_all_bids.sh data   # resolve the bid list and stop
```

Outputs land in `out/gt/pilot_<timestamp>_<hex>/`: `run_meta.json` written before the
first call, a `conversations.jsonl` appended and fsynced per dialogue, `skipped.jsonl` for
scenarios that failed validation, and per bid logs under `out/logs/`.

Run one bid per process. The rate limiter and the checkpoints assume sequential bids.

### What will and will not reproduce

The deterministic half reproduces exactly: compliance labels, the relaxation front, the
buyer's accept/counter/refuse decisions, feasibility probabilities, rankings and the
selection of the offered candidates are pure functions of the inputs, the settings and
the recorded seeds. Every record carries `persona_seed`, `negotiator_seed`, the prompt
versions, a settings hash and the identifier of every model call.

The wording will not reproduce exactly. The released dialogues were generated with
Gemma 4 26B at the temperatures in `config/settings.yaml`, and a rerun produces different
sentences carrying the same code built facts. `config/settings.yaml` ships as it was used;
changing a gate, a level ladder or a weight changes the labels, so compare against the
released data before concluding that a change is an improvement.

The prompt files are the ones that produced the data and are kept byte identical for
provenance. One consequence: `prompts/negotiator_final.v4.md` still describes two possible
message kinds, while the code now only ever passes `best_available`, which was also the
only kind used for all 715 released dialogues.

## Data provenance and terms of use

The requirements come from tender documents published by a government procurement portal.
The candidate records come from publicly accessible product listing pages on a
commercial marketplace. Nothing behind a login, paywall or account is included, no
personal data was sought, and the buyers in the dialogues are synthetic personas rather
than real people or real purchases.

Before release, supplier names, supplier URLs, product URLs, email addresses and
telephone numbers were removed from every file, including from the free text listing
fields and from the dialogue utterances. Supplier and product identifiers are keyed
pseudonymous tokens (`SUP_<hex>`, `PROD_<hex>`), not marketplace identifiers: the same
token stands for the same supplier or listing in every file, so the joins resolve, but a
token carries no route back to the record it came from. The key is not distributed.

Scans over the released files confirm it: no real supplier name, no marketplace or
supplier owned URL, no unredacted email address, and no raw marketplace identifier
remains anywhere. Listing content the ranking features read, namely product name,
specification values, city, state, rating and tenure, is retained; none of it carries a
contact detail or a supplier name. **[docs/ANONYMIZATION.md](docs/ANONYMIZATION.md)** records
exactly what was changed and what was checked.

This release is intended for noncommercial research on conversational recommendation and
negotiation dialogue. It is not a supplier directory, it is not an endorsement or an
assessment of any supplier, and nothing in it should be used to make or justify a real
purchasing decision. The rights to the underlying tender documents and marketplace
listings stay with their respective owners; what is released here is derived research
data. If you are a rights holder and want a record removed, raise an issue and it will be
taken down.

A formal licence is not attached to this snapshot and will accompany the camera ready
release.

## Reading the code

Docstrings and comments carry short `Dxxx` tags (`D050`, `D072`, ...). Each is an internal
id for a design decision taken during development; the surrounding sentence states the
rule, and no `Dxxx` tag is needed to read the code. `config/settings.yaml` is the single
place where every threshold, gate, ladder and weight lives, and the code reads them from
there rather than hardcoding them.

