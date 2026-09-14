# ca-plant-heat

An AI-powered interactive map of **thermal exposure for California plant species**: where, within a
species' current range, projected daily maximum air temperatures approach or exceed its measured
photosynthetic heat tolerance.

Built on [geo-agent](https://github.com/boettiger-lab/geo-agent) from
[geo-agent-template](https://github.com/boettiger-lab/geo-agent-template) — the map, chat, agent and
tool modules load from CDN; this repo configures which data to show and how the agent should behave.

> **Status: pre-data.** The app shell is configured but `collections` in `layers-input.json` is empty
> — the underlying datasets have not been published yet. See [DATA-PLAN.md](DATA-PLAN.md) for what
> has to be ingested through
> [`boettiger-lab/data-workflows`](https://github.com/boettiger-lab/data-workflows) first, and the
> open questions still outstanding with the partner.

## The idea

A user picks a species, a thermal tolerance threshold (**Tcrit**, where photosynthetic capacity is
first impaired, or **T50**, where performance halves), a climate period and scenario, and an
assumption about how much hotter leaves run than the surrounding air. The map then shows the mean
annual number of days on which daily maximum air temperature exceeds the resulting air-temperature
threshold, across the species' current range — plus summary metrics: the share of the range seeing
at least 1, 5 or 10 exceedance days per year, and the largest exceedance.

Thermal tolerance values for 100+ California species are supplied as defaults, but users can enter
their own — the proposal is explicit that different populations, experiments and sources will yield
different values.

## Data

| Dataset | Source |
|---|---|
| Species current ranges | Calflora climate-model distributions (GeoTIFF), downloaded by the project team |
| Thermal tolerance (Tcrit, T50) | Measured by the project team under California's Fifth Climate Change Assessment |
| Daily max air temperature | LOCA2-Hybrid downscaled projections, UC San Diego Scripps, via [Cal-Adapt](https://analytics.cal-adapt.org/data/catalog/) (CC-BY-4.0) |

## Repository structure

```
index.html          ← HTML shell — loads core JS/CSS from CDN
layers-input.json   ← which STAC collections to show + LLM settings
system-prompt.md    ← agent persona, domain context, guardrails
DATA-PLAN.md        ← ingest plan and open questions (working document)
k8s/                ← Kubernetes deployment manifests
import-data/        ← raw partner data, git-ignored (goes to S3 via data-workflows)
```

## Local development

```bash
python -m http.server 8000
# open http://localhost:8000 — enter your API key in the settings panel
```

## Deployment

The Kubernetes manifests in `k8s/` deploy to the `biodiversity` namespace as `ca-plant-heat`, served
at `ca-plant-heat.nrp-nautilus.io`. The pod's init container clones `main` at startup, so **push
before restarting**:

```bash
git push
kubectl rollout restart -f k8s/deployment.yaml
kubectl rollout status  -f k8s/deployment.yaml
```

The `llm` block in `layers-input.json` supports the user-provided-key mode used for GitHub Pages;
the server-injected `config.json` takes precedence in the Kubernetes deployment.

## Documentation

- [geo-agent docs](https://boettiger-lab.github.io/geo-agent/docs/) — configuration reference,
  deployment guide, agent internals
- [AGENTS.md](AGENTS.md) — guidance for AI agents working in this repo
