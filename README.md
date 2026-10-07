# TrustScientist: anonymous research artifact

Code, recorded results and reproducibility materials for the current AAMAS draft.
The files are split into three archives to fit browser upload limits. The
core CBR engine is also directly viewable in `counterfactual_revalidation.py`.

## Quick start

Download or clone this repository, then unpack the archives (checks SHA256):

```text
python unpack_artifact.py
```

Linux / Python 3.10+ is required for CBR file locking. Then run:

```text
python test_cbr.py
python run_branch_experiment.py prepare
python run_branch_experiment.py
python validate_branch_results.py
python analysis/recompute_recorded_results.py
```

Begin in a fresh extracted directory: experiment state persists between runs.
No model endpoint, API key or network is needed for these offline commands.
Install the plotting dependencies from `requirements-figures.txt` to redraw:

```text
python visualizations/scripts/plot_current_results.py --data-dir visualizations
```

## What is provided

- `artifact-code.zip`: portable implementation, recorded cases, four figure
  sources, frozen figure inputs, source provenance and the technical appendix.
- `artifact-cbr-inputs.zip`: archived witness bytes, controlled update cases and
  original 405-event branch results.
- `artifact-recorded-evidence.zip`: saved manifest, acquisition, semantic-gate,
  certificate, SciFact and fresh-execution records; archived model receipts.
- `TrustScientist_technical_appendix.pdf`: the current compiled appendix.

The complete extracted README gives the data layout and protocol boundaries.
Recorded-output count recomputation is distinct from rerunning model inference.
Original request IDs, source hashes and redaction provenance are retained;
local author paths, API credentials and author Git history are excluded.

## Results and limits

CBR and full replay both find 254/254 earliest rollback points, with 382 vs
416 decision evaluations. Graph and flat certificate tracking tie: 1,530
checks vs 2,888 full checks, all with 0/163 stale accepts. Unguarded acquisition
and structured LLM match all 82 budget-four outcomes; failed historical
calibration produces 0/82 guarded closures. These work counts are not total
cost; no SOTA, independent human validation or unrestricted autonomous
scientific repair is claimed. Controlled branch updates use authored histories.
The new figure set preserves negative results and strong-baseline ties.

See `AI_ASSISTANCE.md` and `ANONYMIZATION.json` after extraction. Document
binaries from the acquisition corpus and full production source are omitted;
saved outputs, public source IDs and offline reproduction inputs remain.
