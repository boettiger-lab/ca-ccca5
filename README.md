# ca-ccca5

An AI-powered interactive map of **thermal exposure for California plant species**: where, within a
species' current range, projected daily maximum air temperatures approach or exceed its measured
photosynthetic heat tolerance.

Built on [geo-agent](https://github.com/boettiger-lab/geo-agent) from
[geo-agent-template](https://github.com/boettiger-lab/geo-agent-template) — the map, chat, agent and
tool modules load from CDN; this repo configures which data to show and how the agent should behave.

> **Status: data preview.** The 99 usable Calflora species range rasters are cleaned, published to
> `s3://public-ca-ccca5/` and wired into the map, so the partner can see what we have. The LOCA2
> temperature projections are **not** ingested yet, so the exceedance-day calculation the tool exists
> for does not work in this preview. See [DATA-PLAN.md](DATA-PLAN.md) for the remaining ingest and
> the open questions with the partner.
>
> The range rasters in this preview predate the team's 2026-09-15 corrections. Seven species —
> `HESWHI HETARB ATRTOR BACPIL ERIUMB FOUSPL ENCFAR` — were re-downloaded and `ERIDIS` added, but the
> corrected files have not reached us yet, so **some of the seven are showing another species' range
> right now**. Rebuild the collection before the preview goes to anyone new.
>
> ⚠️ **Calflora redistribution terms are unconfirmed.** The range collection is deliberately *not*
> registered in the public STAC catalog, and the app reaches it by direct `collection_url`. Resolve
> the licence before publicising this more widely — see
> [data-workflows#668](https://github.com/boettiger-lab/data-workflows/issues/668).

## The idea

A user picks a species, a thermal tolerance threshold (**Tcrit**, where photosynthetic capacity is
first impaired, or **T50**, where performance halves), a climate period and scenario, and an
assumption about how much hotter leaves run than the surrounding air. The map then shows the mean
annual number of days on which daily maximum air temperature exceeds the resulting air-temperature
threshold, across the species' current range — plus summary metrics: the share of the range seeing
at least 1, 5 or 10 exceedance days per year, and the largest exceedance.

Thresholds are entered by the user. The project team has measured Tcrit and T50 for 109 California
species, but those values are unpublished and the app does not distribute them; they will become
defaults once the team's paper is out. The proposal is explicit in any case that different
populations, experiments and sources yield different values, so user-supplied thresholds are the
design, not a stopgap.

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

The Kubernetes manifests in `k8s/` deploy to the `biodiversity` namespace as `ca-ccca5`, served
at `ca-ccca5.nrp-nautilus.io`. The pod's init container clones `main` at startup, so **push
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
