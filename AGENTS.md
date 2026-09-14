# AI Agent Guide — ca-ccca5

This is a **geo-agent client app**, created from
[`boettiger-lab/geo-agent-template`](https://github.com/boettiger-lab/geo-agent-template). The
template's `AGENTS.md` is the full reference for the `layers-input.json` schema, collection/asset
lookup, MapLibre filter syntax, deployment, and bug routing — **read it there rather than
duplicating it here**. Everything below is specific to this app.

## Repo relationship

| Repo | Purpose |
|---|---|
| `geo-agent` | Core library (map, chat, agent, tools), loaded from CDN. Never modified here. |
| `geo-agent-template` | The starter this repo was created from; authoritative for config schema. |
| `data-workflows` | Where the datasets this app depends on are built and published. |
| `ca-ccca5` (here) | `index.html`, `layers-input.json`, `system-prompt.md`, `k8s/`. |

**You do not write JavaScript here.**

## Current state

The app shell is configured but **`collections` is empty** — no dataset for this app has been
published yet. [DATA-PLAN.md](DATA-PLAN.md) records the ingest design, the data defects found in the
partner's raw files, and the questions still open with the partner. Read it before touching
`layers-input.json` or the dataset-specific parts of `system-prompt.md`.

Do not invent collection ids, asset keys, or column names. Fill them in from the STAC collection and
the MCP tools (`list_datasets`, `get_schema`) once the ingest lands.

## Domain rules that shape every answer

These are the app's substance, not decoration. They are stated in `system-prompt.md` and any change
to them belongs there:

- **Tcrit and T50 are leaf temperatures**; the climate data is air temperature. The comparison is
  always `τ = threshold − leaf-to-air offset`, and the offset is a user assumption that must be
  reported with every result.
- **Exceedance is exposure, not mortality.** Never let the app describe it as predicted death,
  dieback, or range loss.
- **The range cutoff is the denominator** for every summary percentage and must be identical between
  numerator and denominator, and stated in the answer.
- **Thresholds are interpolated** off a discrete precomputed grid, never extrapolated past its ends.
- **Figures are ensemble means** across GCMs unless a single model is requested.

## Deployment

Namespace and name come from `k8s/deployment.yaml` (`biodiversity` / `ca-ccca5`) — read them
from the manifest, never from an example. The init container clones `main` at pod start, so push to
GitHub **before** restarting, or you serve stale code:

```bash
git push
kubectl rollout restart -f k8s/deployment.yaml
kubectl rollout status  -f k8s/deployment.yaml
```

`index.html` pins the geo-agent CDN tag in four places (three stylesheets and `main.js`). Bump all
four together, and verify jsDelivr serves the new tag before merging to `main`.

## Reporting bugs upstream

| Symptom | Repo |
|---|---|
| Config/schema mistake here (`collection_id`, asset key, filter syntax) | here |
| Map/chat/agent behaviour, missing renderer capability | `boettiger-lab/geo-agent` |
| Published data or STAC is wrong (bad COG, bogus metadata) | `boettiger-lab/data-workflows` |
