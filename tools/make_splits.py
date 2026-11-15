"""Build the bid disjoint train/validation/test split used by the VENDOR release."""
import json, random, argparse, collections, gzip
from pathlib import Path

SEED = 42
TARGETS = {"train": 500, "validation": 73, "test": 142}

def _open(p: Path):
    """Read a plain or gzipped JSONL file."""
    return gzip.open(p, "rt", encoding="utf-8") if p.suffix == ".gz" else p.open(encoding="utf-8")


def build(src: Path, outdir: Path):
    by_bid = collections.OrderedDict()
    for line in _open(src):
        d = json.loads(line)
        by_bid.setdefault(d["bid_ref"], []).append(d["scenario_id"])
    bids = sorted(by_bid)
    random.Random(SEED).shuffle(bids)

    assign, used = {}, {k: 0 for k in TARGETS}
    for b in bids:
        n = len(by_bid[b])
        for name in ("train", "validation", "test"):
            if used[name] + n <= TARGETS[name]:
                assign[b] = name; used[name] += n; break
        else:
            raise RuntimeError(f"no split fits bid {b} ({n} dialogues)")
    if used != TARGETS:
        raise SystemExit(
            f"expected {sum(TARGETS.values())} dialogues, got {sum(used.values())}: "
            f"{used}.  Pass the combined file, not one part; "
            f"cat train.jsonl validation.jsonl test.jsonl > conversations.jsonl")
    return by_bid, assign, used

def write(src: Path, outdir: Path, by_bid, assign):
    outdir.mkdir(parents=True, exist_ok=True)
    fh = {k: (outdir / f"{k}.jsonl").open("w", encoding="utf-8") for k in TARGETS}
    counts = collections.Counter()
    for line in _open(src):
        d = json.loads(line)
        name = assign[d["bid_ref"]]
        fh[name].write(line if line.endswith("\n") else line + "\n")
        counts[name] += 1
    for f in fh.values(): f.close()
    manifest = {
        "seed": SEED, "grouped_by": "bid_ref", "proportions": "70/10/20",
        "dialogues": dict(counts),
        "bids": {k: sorted(b for b, v in assign.items() if v == k) for k in TARGETS},
    }
    (outdir / "splits.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return counts

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("outdir")
    a = ap.parse_args()
    src, out = Path(a.src), Path(a.outdir)
    by_bid, assign, used = build(src, out)
    counts = write(src, out, by_bid, assign)
    nb = collections.Counter(assign.values())
    print("dialogues:", dict(counts))
    print("bids:", dict(nb))
