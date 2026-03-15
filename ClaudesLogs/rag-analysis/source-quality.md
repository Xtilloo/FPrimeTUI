# RAG Source Quality Analysis

Tracking which sources the RAG retrieves per question and whether they're on-target.

## Observed Pattern (early sessions)

`Svc/FileManager/docs/sdd.md` and `Svc/ComLogger/README.md` appear repeatedly as sources
across unrelated questions (Q1, Q2). These are "sticky" off-target sources — likely have
high BM25 scores for generic fprime terms but low semantic relevance.

**Hypothesis:** These files contain many common F' keywords (component, port, queue, etc.)
causing false BM25 hits. The keyword re-ranking pass doesn't filter them because the
query keywords (e.g. "ActiveComponent") appear in their text incidentally.

**Fix candidates:**
- Boost weight of source_file path when ranking (e.g., `Fw/Comp` files should rank higher
  for component architecture questions than `Svc/` service docs)
- Increase FINAL_K threshold for keyword re-ranking selectivity
- Add negative source filtering for clearly irrelevant document types

## Per-Question Source Log

| Q# | Expected Source | Retrieved Sources | On-Target? |
| :--- | :--- | :--- | :---: |
| 1 | `Fw/Comp` | `Svc/FileManager`, `rate-group.md`, `Svc/ComLogger` | ❌ |
| 2 | `state-machines.md` | `Svc/FileManager`, `state-machines.md`, `Svc/ComLogger` | ⚠️ |
| 3 | `04-cmd-evt-chn-prm.md` | `building-topology.md`, `custom-framing.md`, `04-cmd-evt-chn-prm.md` | ⚠️ |
