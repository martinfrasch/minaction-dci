# ARC-AGI-2.5 benchmark

A benchmark for **Domain-Complete Intelligence (DCI)**: autonomous, closed-loop discovery within a
domain governed by an executable verifier `R` and a compressed prior `Pi`. Companion to the paper in
the repository root.

## Contents

```
ARC_AGI_2p5_SPEC.md        # families A & B: interfaces, scoring, difficulty ladders (read this first)
ARC_AGI_2p5_FAMILY_F.md    # scope-condition / negative-control battery (tests paper section 8)
schemas/                   # JSON Schemas (draft 2020-12) for the 4 interfaces
generators/
  A_dynamics.py            # RUNNABLE: Family A, Level 1 (law recovery) + DCI compare + integrity check
  A_levels.py              # RUNNABLE: Family A, Levels 2-4 (composition, multi-body, latent quantity)
  B_physio.py              # RUNNABLE: Family B, L1/L2/L4 (graph recovery, lesion AUC, experiment design)
suites/A_L1.jsonl          # a generated sample suite
```

Every level ships a `selfcheck` that gates shipping by asserting its held-out criterion actually
discriminates the truth. Current status: **all seven selfchecks pass.**

```bash
cd generators
python3 A_dynamics.py selfcheck                 # A-L1
python3 A_levels.py  selfcheck --level 2        # A-L2 (also 3, 4)
python3 B_physio.py  selfcheck --level 1        # B-L1 (also 2, 4)
python3 A_dynamics.py integrity --n 100 --seed 3   # shuffled-invariant integrity gate
```

## The two-tier verification principle (why this benchmark is different)

Every task has two checks:
- **In-loop `R`** — machine-automated, queried by the agent during discovery; keeps experience `E` cheap.
- **Held-out `H`** — a human-endorsed criterion the agent cannot query, applied once at the end.

An answer that passes `R` but fails `H` is a **gaming incident**: it scores zero and is logged. This
makes the "result must be human-verifiable" requirement enforceable rather than aspirational.

## The runnable reference: Family A, Level 1

`generators/A_dynamics.py` implements the whole loop for law recovery from noisy 2-body dynamics:
- **generator** — samples a hidden central-force law + a noisy ~2-orbit observation;
- **`R`** — fits the coupling constant `k` and returns short-horizon RMSE (a local stand-in for the
  MAL pipeline, 2026b; swap in a MAL adapter behind the same `.query()` signature);
- **`H`** — long-horizon **energy-drift** along the true trajectory (which the agent never sees):
  the true law conserves energy, wrong laws do not. This is the anti-Goodhart tier.

```bash
cd generators
python3 A_dynamics.py selfcheck              # gates shipping: asserts H actually discriminates
python3 A_dynamics.py compare  --n 100 --seed 3            # DCI efficiency-gain G, clean verifier
python3 A_dynamics.py compare  --n 100 --seed 3 --r_noise 1.2   # G under a degraded verifier (Family F)
python3 A_dynamics.py generate --n 200 --seed 0 --out ../suites/A_L1.jsonl
```

### `selfcheck` is a shipping gate, not decoration

It asserts the held-out criterion `H` picks the true law in >=80% of cases. During development it
**caught a real potential-energy sign error** (`inverse_linear` needs `PE = +k ln r`, not `-k ln r`)
and refused to run until fixed. Keep this gate green; it is the benchmark's own integrity gate.

### What the reference demonstrates (honest reading)

The `full` (prior-guided) agent and the `pi_off` (exhaustive) agent test the **same five laws** — the
prior does **not** prune the hypothesis class (that would trade away accuracy). Instead `Pi` supplies
the physical parameter scale, so the prior-guided agent fits `k` over a narrow range with a coarse
grid: **the prior lowers experience `E`, not accuracy.** Representative numbers (n=100):

| condition | success | E (integrations) | efficiency |
|-----------|---------|------------------|------------|
| clean `R`, full (prior)      | ~0.85 | 20 | ~0.034 |
| clean `R`, pi_off (exhaustive) | ~0.98 | 70 | ~0.014 |

Efficiency-gain **G ~ 2.4** on a clean verifier, from ~3.5x less experience at nearly matched accuracy;
**G ~ 3** under a noisy verifier (`--r_noise 1.2`). The prior's advantage *grows as the verifier
degrades*, because the prior is verifier-independent — which is exactly the Family F / paper-section-8
thesis: the DCI advantage concentrates where verification is unreliable. Under a perfect, cheap
verifier, brute force is already strong and the prior's edge is smaller. We report this rather than a
larger headline number because the point of the benchmark is to measure the effect honestly, including
where it is small.

### P/E commensuration

Efficiency is `success * GD / (P + E)`. `P` and `E` are put in the same unit (integration-equivalents);
the compressed prior is charged a small `P_EQUIV` (see `A_dynamics.py`), reflecting its short
description length relative to the experience it replaces. This weighting is a declared suite
parameter (SPEC section 4.1) — change it and report it.

## The higher A levels (`A_levels.py`)

All three use the same anti-Goodhart principle as L1 — a held-out **energy-conservation** criterion
the agent never queries — realized robustly by regressing kinetic energy onto candidate potentials
(exact velocities on the held-out trajectory, no fragile acceleration estimates):

- **L2 (composition):** the true force is a *sum* of two basis terms; recover the term set. H recovers
  the true composition in 30/30.
- **L3 (multi-body):** three bodies interact via one shared pairwise law; recover it from the N-body
  trajectory. H recovers the law in 20/20.
- **L4 (latent quantity):** recover a *non-obvious* conserved quantity. Angular momentum is conserved
  for every central force (the obvious one); the **Laplace-Runge-Lenz** vector is conserved only for
  inverse-square. Scoring its magnitude (precession-invariant) separates Kepler (0.0015) from other
  laws (0.23) cleanly — a genuine, falsifiable discovery rather than a trivially-constant quantity.

## Family B (`B_physio.py`)

A stable linear autonomic system stands in for the in-silico fetal model (swap in an adapter behind
the same `.simulate()/.perturb()` signature). Nodes: maternal BP/HR, fetal HR, fetal movement.

- **L1 (recover graph):** in-loop `R` = one-step prediction error (gameable: denser graphs fit
  better); held-out `H` = **counterfactual perturbation response**, which a graph missing a real edge
  cannot reproduce. H ranks the true graph below an edge-missing graph in 20/20.
- **L2 (lesion localization):** lesion one edge; the fitted coefficient for it collapses to ~0.
  Ranking edges by `-|coef|` gives **Violation AUC = 1.000** — violation as departure from Pi.
- **L4 (experiment design — the reflexivity crown jewel):** given two graphs that fit passive data
  equally, choose the perturbation that best separates them. Prior-guided design (argmax predicted
  divergence) disambiguates in 1 experiment vs 2 for random choice: **G = 2.0**. This is §4's
  strongest claim — meta-skill via the prior — made directly measurable.

## The shuffled-invariant integrity check (`A_dynamics.py integrity`)

The benchmark's own validity gate. For Family A the prior *is* the physical parameter scale, so
scrambling the invariant means handing the agent the **wrong** k-window. Result:

```
correct invariant  : success 0.90  G = 2.65
shuffled invariant : success 0.28  G = 0.81   (must be <= 1.10)
--> PASS: advantage collapses under the scrambled prior (no leakage).
```

If the advantage had survived a wrong prior, the "DCI gain" would have been leakage. No A/B result
should be reported without its shuffled-invariant G alongside (SPEC / FAMILY_F).

## Status

Specced: A, B, F. Runnable with passing selfchecks: **A-L1..L4, B-L1/L2/L4, and the integrity gate.**
Next: wire the A-L2..L4 and B generators to the JSON-schema instance format and the `compare`/ablation
harness (A-L1 is the template); add C-E specs; add the B-L3 counterfactual-transfer scorer.
