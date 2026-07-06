# ARC-AGI-2.5 — Benchmark Specification

**Families A (law recovery) and B (physiological mechanism discovery)**
Companion to *Domain-Complete Intelligence* (this repo). Version 0.1 — draft for internal review.

---

## 1. Scope and the 2.5 boundary

ARC-AGI-2.5 tests **Domain-Complete Intelligence (DCI)**: autonomous, closed-loop discovery of any
law or structure *derivable within a domain's rules*, measured for efficiency. It is deliberately
placed between two existing benchmarks:

- **Harder than ARC-AGI-2** — tasks require *closed-loop experimentation* against a verifier, not
  single-shot pattern completion.
- **More scoped than ARC-AGI-3** — an **executable verifier `R`** exists and a **compressed prior `Pi`**
  is available. There are no open-world unknown-unknowns; the reachable answer set is fixed by a
  stated grammar.

A task is *in scope* iff (a) its ground truth is derivable within a declared rule substrate, and
(b) the correct answer is a **human-checkable artifact** (a closed-form law; a labeled graph), not an
opaque policy. If either fails, the task belongs in ARC-AGI-3, not here.

## 2. Core principles

### 2.1 Two-tier verification (anti-Goodhart)

Every task carries **two** criteria:

1. **In-loop verifier `R`** — machine-automated, queried by the agent during discovery. Keeps
   experience `E` cheap. *Never* human-gated (that would destroy the efficiency claim).
2. **Held-out scoring criterion `H`** — a human-endorsed check the agent **cannot query**, applied
   once at the end. `H` is chosen to be discriminative where `R` is gameable.

An answer that passes `R` but fails `H` is a **gaming incident**: it scores zero *and* is logged
separately. (MAL already works this way: short-horizon fit is `R`; long-horizon energy conservation
is `H`.)

### 2.2 Human-checkable, not human-derivable

`H` must be checkable by a domain expert in bounded time, even if the answer would have been hard for
a human to *find* (the AlphaGeometry standard). Legibility of the *result* is mandatory; legibility of
the *search* is not.

### 2.3 Everything in Chollet's currency

Scoring instantiates the efficiency ratio of *On the Measure of Intelligence* (Eq. 1 in the paper):
skill acquired, weighted by generalization difficulty, divided by priors plus experience. See §4.

## 3. Common protocol

### 3.1 Episode lifecycle

```
load(TaskInstance)                      # agent receives observation + budget + answer schema
repeat until budget exhausted or agent halts:
    proposal  = agent.step(history)     # a candidate answer OR an experiment
    response  = R.query(proposal)       # in-loop signal + cost (debited from budget)
final      = agent.submit()             # the human-checkable artifact
report     = H.score(final)             # held-out criterion, GD, P, E, gaming_flag
```

### 3.2 Interfaces

**TaskInstance** (given to the agent):
```json
{
  "task_id": "A-L2-000473",
  "family": "A",
  "level": 2,
  "domain": "newtonian_dynamics",
  "observation": { "series": [[t, x, y, ...], ...], "snr": 1.6, "units": "SI" },
  "budget": { "unit": "integrations", "E_max": 500 },
  "prior": { "pi": "action_noether", "provided": true },
  "answer_schema": "symbolic_law_sexpr",
  "grammar_id": "phys_basis_v1",
  "verifier": "rho://A/000473"
}
```

**R.query** (in-loop verifier):
```
query(task_id, proposal) -> {
  "signal":  <float | dict>,     # family-specific fidelity signal (NOT the held-out score)
  "cost":    <float>,            # E units consumed by this query
  "budget_remaining": <float>,
  "valid":   <bool>              # proposal well-formed under grammar_id
}
```

**FinalSubmission** (agent -> scorer):
```json
{ "task_id": "A-L2-000473", "answer": "<sexpr | graph_json>",
  "confidence": 0.0, "trace_uri": "optional://run/xyz" }
```

**ScoreReport** (returned by `H`, logged):
```json
{ "task_id": "A-L2-000473", "success": 1.0, "gaming_flag": false,
  "held_out_value": 3.2e-4, "GD": 2.0, "P_bits": 41.0,
  "E_used": 138.0, "E_norm": 0.276, "efficiency": 6.51, "notes": "" }
```

### 3.3 Budgets and `E`

`E` is the **total experience/energy** spent against `R`, in the task's declared unit
(integration count, simulated experiments, or kWh where a real energy meter exists — preferred, since
it matches the NWAP energy signature). `E_norm = E_used / E_max ∈ (0, 1]`.

### 3.4 Mandatory ablations and baselines

Each task **must** be run in all of:

| Condition | `Pi` | `R` | Purpose |
|-----------|------|-----|---------|
| `full`        | on  | on  | the DCI agent |
| `pi_off`      | off | on  | isolate the prior's contribution (prior-free search) |
| `R_off`       | on  | off | open-loop control (no verifier feedback) |
| `baseline`    | off | on  | scale-matched general searcher (reference denominator) |

The headline DCI signal is the **efficiency-gain ratio** `G = efficiency(full) / efficiency(pi_off)`
(§4.3). `R_off` quantifies how much the closed loop (not the prior) is doing.

### 3.5 Instance-generator contract

A generator for a family emits `(TaskInstance, hidden_truth, H_config)` triples and must:
- sample `hidden_truth` from the declared grammar only (in-scope guarantee);
- expose all difficulty knobs (§5.4, §6.4) and record them in a reproducible `seed`;
- guarantee no leakage: nothing in `observation` or any `R.signal` reveals the `H` value;
- ship a `held_out_split` and a `transfer_split` (same `Pi`/grammar, unseen instances/systems),
  plus — for prediction (iii) — a `cross_invariant_split` (systems that do *not* share `Pi`).

## 4. Scoring

### 4.1 Operational definitions

- **success** ∈ [0, 1]: `1` if `answer` passes `H` (correct up to declared equivalence, e.g. algebraic
  equivalence for A, graph-isomorphism-up-to-labels for B) **and** `gaming_flag == false`; graded
  partial credit allowed per family (§5.5, §6.5).
- **GD** (generalization difficulty): level weight, default `{L1:1, L2:2, L3:4, L4:8}`. Optional
  principled form: `GD = description_length(hidden_truth | grammar)` in bits, normalized per suite.
  Report which is used.
- **P** (priors, bits): description length of the injected prior. `Pi`-on adds `P_bits(Pi)` (the
  action functional + declared constraints); `pi_off` sets `P = 0`. This is the honest cost of the
  prior — DCI must *earn* it back through lower `E`.
- **E** (experience): `E_norm` from §3.3.
- **Cost** `C = w_P * P_hat + w_E * E_norm`, where `P_hat` normalizes `P_bits` to the suite scale and
  `w_P, w_E` are documented per suite (default `w_P = w_E = 1` after each term is scaled to [0,1]).

### 4.2 Per-task efficiency

```
efficiency = success * GD / C
```

Chollet-native: skill (success) weighted by difficulty (GD), divided by priors+experience (C).

### 4.3 Aggregate reports (per suite)

- **DCI-score** = mean `efficiency` over the suite in the `full` condition.
- **Efficiency-gain** `G = efficiency(full) / efficiency(pi_off)`, per task then averaged.
  *Prediction (i)/(ii): `G > 1`, and `G` rises with the compression of `Pi`.*
- **Transfer delta** `ΔT = efficiency(transfer_split) − efficiency(train_split)` (want `≈ 0`: no
  overfitting to instances). **Cross-invariant transfer** `ΔT_x = efficiency(full) −
  efficiency(cross_invariant_split)`. *Prediction (iii): `ΔT ≈ 0` while `ΔT_x` is large and positive.*
- **Gaming rate** = fraction of tasks with `gaming_flag == true`. A suite with a high gaming rate is
  telling you `R` and `H` are too close — fix the task, not the agent.
- **Violation AUC** (detection ladders only): ROC-AUC of the agent's violation localization vs. the
  injected ground-truth break.

### 4.4 Pass thresholds

A level is **passed** for an agent if, over its suite: `success` mean `≥ 0.8`, `gaming rate ≤ 0.05`,
and `ΔT` within `± 0.1`. `G > 1` is required to claim any DCI advantage at that level.

## 5. Family A — Law recovery from noisy dynamics

**Verifier `R`:** the MAL pipeline (2026b, arXiv:2603.16951). **Answer:** a symbolic force law /
Lagrangian as an S-expression, checked up to algebraic equivalence.

### 5.1 `R` interface (specialization)
- `proposal` = S-expression over `grammar_id` (e.g. `(* G (/ (* m1 m2) (^ r 2)))`).
- `signal` = short-horizon integrated trajectory RMSE over `T_short` at the task SNR.
- `cost` = number of integration steps (or kWh if metered).
- `valid` = parses under grammar and is dimensionally consistent.

### 5.2 Prior `Pi`
Action + Noether-conservation prior: agent extremizes `S_NW`; conservation terms available as
soft constraints. `pi_off` = minimize `signal` (raw fit) only.

### 5.3 Held-out criterion `H`
**Long-horizon conservation residual**: integrate the submitted law over `T_long ≫ T_short` (unseen
by the agent) and measure drift of the conserved quantity; pass iff residual `≤ ε_conserve`. This is
exactly where fit-only solutions fail and true laws survive.

### 5.4 Generator parameters

| Knob | Symbol | Default / range |
|------|--------|-----------------|
| Basis library | `B` | {`r^-2, r^-1, r, r^-3, const, sin, cos`} |
| Composition depth | `d` | 1 (L1) → 4 (L4) |
| Noise (signal-to-noise) | `SNR` | 1.6 down to 0.3 |
| Bodies | `n` | 1 → N-body (L3+) |
| Latent conserved quantity | `q*` | off (L1–L3) / on (L4) |
| `T_short : T_long` | — | 1 : 50 |

### 5.5 Difficulty ladder

| Level | Task | Pass criterion (beyond §4.4) |
|-------|------|------------------------------|
| **L1** | Select the true law from `B` | exact basis match + `H` |
| **L2** | Compose within grammar (basis-expansion) | equivalence to truth + `H` |
| **L3** | Coupled multi-body law | per-interaction equivalence + global `H` |
| **L4** | Recover & *name* a latent conserved quantity | `q*` matches up to affine reparam + `H` |

### 5.6 Worked micro-example (L1)
Observation: noisy 2-body orbit, SNR 1.6. Agent queries `R` with candidates from `B`; `(/ 1 (^ r 2))`
returns lowest short-horizon RMSE. Submits `(* G (/ (* m1 m2) (^ r 2)))`. `H` integrates 50× horizon:
energy drift `3e-4` < `ε_conserve`. `success = 1`, `gaming_flag = false`.

## 6. Family B — Physiological mechanism discovery

**Verifier `R`:** the in-silico fetal physiology model (this program). **Answer:** an explicit
labeled autonomic coupling graph (nodes = named signals/organs, directed edges with gains + delays),
inspectable by a physiologist against known physiology.

### 6.1 `R` interface (specialization)
- `proposal` = either a **coupling hypothesis** (graph + parameters) or an **experiment**
  (a perturbation to apply in-silico).
- `signal` = simulated outputs for the proposal: HRV indices, maternal–fetal transfer entropy,
  baro/chemoreflex responses (summary statistics, not the held-out counterfactual).
- `cost` = 1 simulated experiment per query.
- `valid` = graph respects declared node set and physiological sign constraints.

### 6.2 Prior `Pi`
NWAP over the physiological network plus known autonomic constraints (reflex signs, delay ranges).
`pi_off` = unconstrained graph search.

### 6.3 Held-out criterion `H`
**Counterfactual prediction on held-out perturbations**: the agent's submitted mechanism is used to
predict responses to a set of perturbations it never applied; ground truth = the simulator's true
configuration under those perturbations. Pass iff predictive error `≤ ε_cf`. Ground truth is fully
known (it is the simulator config), hence human-verifiable.

### 6.4 Generator parameters

| Knob | Symbol | Default / range |
|------|--------|-----------------|
| Base topology | `T0` | baroreflex + chemoreflex + maternal–fetal coupling |
| Lesion (L2) | `ℓ` | edge deletion / gain-zeroing at a hidden locus |
| Perturbation library | `Π_pert` | {hypoxia step, maternal HR change, vagal block, ...} |
| Signal noise | `σ` | physiological range |
| Held-out perturbations | `P_ho` | disjoint from any appliable in-loop set |

### 6.5 Difficulty ladder

| Level | Task | What it tests |
|-------|------|---------------|
| **L1** | Recover a known coupling graph | baseline discovery |
| **L2** | Detect **and localize** a lesioned loop | violation-as-departure-from-`Pi` (Violation AUC) |
| **L3** | Predict response to an unseen perturbation | within-scope transfer / counterfactual |
| **L4** | **Design the minimal perturbation** that disambiguates two candidate mechanisms | **reflexivity / meta-skill via experiment design** |

**L4 is the crown jewel.** If `Pi`-reflexivity is real, the `full` agent should design a disambiguating
experiment in **fewer** `R`-queries than `pi_off`. Operationalize: `disambiguation_cost =
E`-to-confident-discrimination; report `G = pi_off_cost / full_cost`. `G ≤ 1` at L4 falsifies §4's
strongest claim, cleanly.

### 6.6 External-validity note (read before over-claiming)
Using the simulator as both `R` and ground-truth means B tests *"recover the simulator's
configuration."* This is fully human-verifiable but only as physiologically valid as the simulator.
Validation against **FELICITy** real-cohort data is a separate, later step: the benchmark gives clean
ground truth; the cohort gives reality. State which you are reporting.

## 7. Reference implementation notes

Suggested layout under `benchmark/`:
```
benchmark/
  ARC_AGI_2p5_SPEC.md          # this file
  schemas/                     # JSON Schemas for the four interfaces (§3.2)
  generators/  A_dynamics.py  B_physio.py
  verifiers/   R_mal.py        R_fetal.py      # thin adapters onto existing code
  scoring/     score.py        metrics.py
  suites/      A_L1.jsonl ...  B_L4.jsonl
  results/     <agent>/<suite>.json
```
- **Reproducibility:** every instance carries a `seed`; every suite pins generator + verifier
  versions. Report `(GD-mode, w_P, w_E, ε_*)` alongside any number.
- **`R` adapters** wrap MAL and the fetal model behind the §3.2 `query` signature so agents are
  verifier-agnostic.
- **Reporting:** publish per-condition efficiency, `G`, `ΔT`, `ΔT_x`, gaming rate, and (L2/B) Violation
  AUC. Never report `full` alone — the ablations are the evidence.

## 8. Falsification map (ties tasks to the paper's claims)

| Paper claim | Where tested | Falsified if |
|-------------|--------------|--------------|
| (i) verifier+prior ⇒ higher efficiency | A-L1..L4, B-L1..L3 (`G`) | `G ≤ 1` |
| (ii) quality tracks prior compression | A across `SNR`/`d`; vary `P_bits(Pi)` | `G` flat as `Pi` compresses |
| (iii) transfer across shared-invariant domains | `transfer` vs `cross_invariant` splits | `ΔT` large *or* `ΔT_x ≈ 0` |
| §4 reflexivity (search+inference) | B-L4 experiment design | `G ≤ 1` at L4 |
| §4 violation = departure from `Pi` | B-L2 (Violation AUC) | AUC ≈ 0.5 |
| §8 graceful degradation | Family F (separate spec) | DCI advantage persists where `Pi`/`R` absent |

---

*Next specs to write: Families C–F, and the four JSON Schemas in `schemas/`.*
