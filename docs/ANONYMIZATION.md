# Anonymisation

This records what was removed from the released files and what was checked before
packaging. Every count below was measured on the released files themselves.

## Supplier and product identity

No supplier name, no supplier or product URL, and no marketplace identifier appears
anywhere in the release.

| Field | In the release |
|---|---|
| `supplier_name`, `supplier`, `page_supplier`, `supplier_native_id` | `SUP_<12 hex>` |
| `supplier_id` | the same `SUP_<12 hex>` token as that supplier's name |
| `product_id` | `PROD_<12 hex>` |
| `product_url` | `https://anon.invalid/product/PROD_<12 hex>` |
| `supplier_url`, `supplier_website_url` | blanked |
| `brochure_candidate_pdfimage_urls`, `image_urls`, `brochure_page_urls` | blanked |
| `brochure_candidate_pdf_urls`, `brochure_urls` | column dropped |
| `supplier_facts."Verified GST Number"` | already a bare `sha256:` digest upstream; left as is |

Tokens are keyed HMAC digests, over SHA256. The key is not distributed, and it is not needed
to use the data: one supplier and one product each carry one token everywhere they
appear, so every join across every file still resolves. Identity runs one way only:
a token cannot be turned back into the marketplace record it came from.

The identifier columns the loader requires are kept present and anonymised by value rather
than deleted, because `load_suppliers`, `load_products` and `load_product_constraints`
select a fixed canonical column list and raise `ValueError: missing canonical columns`
if one is absent.

## Free text

`description`, `jsonld_raw`, `brochure_text`, `brochure_page_text`, `raw_text`,
`commercial_text` and every dialogue utterance were scrubbed: a supplier name becomes
that supplier's token, a URL becomes `[URL-REDACTED]`, an email address becomes
`[EMAIL-REDACTED]`. 36 URL redactions and 12 email redactions remain in
the dialogue files; they are the complete set.

Listing content that the ranking features read, namely `product_name`, specification
values, `city`, `state`, `rating`, `rating_count` and `member_since`, is retained. Those fields
carry no contact detail and no supplier name, and the matching, scoring and
"preferred states" behaviour cannot be reproduced without them.

## What is kept intact

Structural fields are never scrubbed by pattern: `constraint_id`, `scenario_id`, `run_id`,
`bid_ref`, `llm_call_ids`, `settings_hash`, `evidence_anchor`, every seed, score,
bound, rank and negotiated value. An earlier pass applied a telephone number pattern
across all string fields, which matched digit runs inside such values; that pass was
rebuilt to work from the record schema instead, and the damage was repaired:

- 1,081 identifier, hash and evidence anchor values restored to their true values
  (928 `evidence_anchor`, 44 `merged_from`, 36 `framing_reason`, 18 `kept`, 18
  `evidence`, 15 `settings_hash`, 12 `qa_flags`, 10 `members`)
- 8 supplier tokens whose hex digits had been partly eaten, rebuilt
- 10 material and part codes welded to letters (`FF8121070040`), restored

No telephone number was found anywhere in the dialogue files after the repair: every
one of the pattern's 1,099 original matches there was a false positive on an
identifier. The released dialogue files contain zero `[PHONE-REDACTED]` markers.

## Bid requirements

`final_constraints.csv`, `gem_bids_metadata.csv` and `bids.txt` come from tender
documents published on a public government procurement portal, and are released as
published, with two exceptions. One buyer email address and one consignee telephone
number (attribute `consignee_contact_no`) were removed from `final_constraints.csv`.
Neither string occurs in any dialogue file, and `consignee_contact_no` is never a
dialogue requirement, so no dialogue, ranking or reported figure depends on either.

## Trimmed to what the dialogues use

The catalogue originally held every discovered listing, most of which no dialogue ever
ranked, compared or quoted. Every CSV was filtered to the rows actually referenced by
the dialogues, through `reference_ranking`, `reference_ranking_initial`,
`negotiator_ranking`, `best_available.items`, `compliance_detail_truth` and
`compliance_detail_belief`.

| file | before | after | removed |
|---|---|---|---|
| `suppliers.csv` | 1,828 | 1,440 | 388 |
| `products.csv` | 7,237 | 5,662 | 1,575 |
| `product_constraint.csv` | 95,949 | 73,833 | 22,116 |
| `supplier_products.csv` | 15,234 | 11,925 | 3,309 |

## Verified before packaging

- Zero occurrences of any of the 1,828 real supplier names, and zero real marketplace
  or supplier owned URLs, in any released file.
- Zero unredacted email addresses in any released file.
- Zero raw marketplace identifiers: every `supplier_id` is a `SUP_` token and every
  `product_id` a `PROD_` token, in the dialogue files and in all four catalogue CSVs.
- Join integrity: all 1,440 supplier tokens and all 5,662 product tokens referenced by
  the dialogues resolve to a row in `suppliers.csv` and `products.csv`; zero orphans
  in either direction.
- The real loaders accept the released files unchanged, with the shapes the pipeline
  expects:

```
load_suppliers OK:            (1440, 14)
load_products OK:             (5662, 31)
load_product_constraints OK:  (73833, 19)
```

- Every statistic reported from this dataset was recomputed on the released files after
  anonymisation and matches: 715 dialogues, 431 bids, 2,770 utterances, mean 3.87
  turns, 654 relaxation proposals (201 accepted / 315 countered / 121 refused / 17
  split), 187 dialogues with an accepted relaxation, 91 top 1 changes, 121 dialogues
  where the negotiator's top 1 differs from the reference, all 715 closing on a
  best available offer (481 `no_feasible`, 212 `nothing_verified`, 22
  `patience_exhausted`), and tiers 210 / 162 / 155 / 188.

## Rerunning the pipeline on this data

The CSVs load and build scenarios normally, but rerunning generation will not
reproduce the dialogue files byte for byte, for a reason worth knowing.

Every model call is cached under
`sha256(model, backend, provider, prompt_name, prompt_version, canonical-JSON inputs, seed)`.
The supplier's name is part of `CandidateView`, which is a canonical input to the
negotiator prompts, so once it is a token the cache key differs and those calls cannot
replay from `.cache/llm/`; they become live calls again.

What does come out identical: every deterministically computed field, meaning the
compliance matrix, the rankings, `best_available`, the actions, the turn counts, and the
outcome with its reason. None of those depend on the literal supplier name; they depend on the
numeric and categorical constraint values and on the join keys, all of which are
intact. What differs is the model authored wording, because a fresh call now sees a
token where a company name used to be.
