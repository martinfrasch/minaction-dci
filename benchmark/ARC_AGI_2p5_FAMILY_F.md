# ARC-AGI-2.5 — Family F: Scope-Condition / Negative-Control Battery

Companion to `ARC_AGI_2p5_SPEC.md`. Family F tests **§8 of the paper** (graceful degradation) and
doubles as the **integrity test for the whole benchmark**. It is the family designed to *falsify* DCI,
not flatter it. Version 0.1.

---

## 1. Why F exists

DCI rests on two assets: a compressed vertically organizing principle `Pi` and an executable verifier
`R`. The paper claims the advantage **degrades gracefully and measurably** as either weakens, and
**vanishes** when both do. If a DCI agent still shows a large efficiency-gain `G` where `Pi`/`R` are
absent, one of two things is true — the paper's §8 is wrong, or the agent is exploiting leakage. Both
are things you must be able to detect. F makes them detectable.

F reuses the substrates of Families A and B (so results are directly comparable) and *degrades a
declared asset* under controlled knobs.

## 2. The three degradation axes

| Sub-family | Degrade | Paper prediction |
|------------|---------|------------------|
| **F1** | `Pi` weak or wrong | `G → 1` as prior-fit → 0 |
| **F2** | `R` noisy / partial | `G` declines toward `baseline`; gaming rate rises |
| **F3** | both at once | `G ≈ 1`, high gaming rate — the honest boundary |

### F1 — Weak or absent `Pi`
Two cases, and the distinction matters:
- **F1a — genuinely absent.** The hidden truth is sampled from *outside* any grammar the prior covers
  (e.g., a non-conservative or noise-driven dynamics in A; a coupling with no action-functional
  rationale in B). There is no compressible invariant to exploit. *Prediction:* `G ≈ 1`.
- **F1b — mis-specified.** `Pi` is *provided but wrong* (a scrambled invariant, an incorrect
  conservation law). This tests something sharper than efficiency: does the agent **detect that `Pi`
  does not fit** (rule-violation on the prior itself, §4) and decline/flag — or does it confidently
  emit garbage? See the *prior-rejection* metric (§4).

### F2 — Weak or approximate `R`
`R` no longer returns clean ground truth. Knobs (composable):
- **stochastic** — `signal` is corrupted by noise of controlled magnitude `η`;
- **biased** — a systematic offset that rewards a wrong region of answer space;
- **censored** — `R` returns only a coarse pass/fail, or is unavailable on a fraction `c` of queries;
- **unreliable oracle** — `R` is correct only with probability `p < 1`.
*Prediction:* the closed loop leaks — `E` stops being cheap, gaming rate rises, and `G` falls toward
`baseline` monotonically in `η` (a **degradation curve**, not a point).

### F3 — Both
`Pi` mis-specified **and** `R` noisy. *Prediction:* DCI has no special leverage and collapses toward
ordinary narrow AI or the open-world regime — `G ≈ 1`, high gaming rate. This is the boundary the
paper explicitly claims as its edge; F3 is where you confirm the edge is real.

## 3. The shuffled-invariant control (benchmark-wide integrity check)

Independently of F1–F3, every A/B suite ships a **shuffled-invariant** twin: identical task, but the
invariant `Pi` encodes is **randomly permuted** so it no longer matches the generative structure. If
the agent's `G` stays high on the shuffled twin, it was **never using `Pi`'s structure** — it is
exploiting leakage or a spurious correlate. *Requirement:* `G(shuffled) ≈ 1`. A benchmark that fails
this is measuring the wrong thing, and no A/B result should be reported without its shuffled-invariant
`G` alongside.

## 4. Scoring additions (beyond the base spec §4)

- **Degradation curve.** For F2/F3, report `G` as a function of the degradation knob (`η`, `c`, `1−p`).
  The falsifiable content of §8 is *monotone decline to ≈ 1*, so fit and report the slope and the
  knob value at which `G` crosses `1 + δ` (the "break-even degradation").
- **Prior-rejection rate** (F1b). Fraction of mis-specified-`Pi` tasks on which the agent **flags the
  mis-fit** (declines, or lowers confidence below a threshold, or explicitly reports `Pi`-violation)
  instead of submitting a confident wrong answer. *High is good* (honest use of the prior); *low is
  dangerous* (the agent will misuse a wrong prior in the wild). Report separately from success.
- **Overconfidence penalty.** On F1a/F1b/F3, a *confident wrong* answer (high `confidence`, `success=0`)
  is logged as a distinct, worse failure than a low-confidence wrong answer. DCI's safety case depends
  on degrading loudly, not silently.

## 5. Generator parameters

| Knob | Applies to | Range |
|------|-----------|-------|
| Prior-fit quality `φ` | F1 | 1.0 (perfect) → 0.0 (absent/scrambled) |
| Mis-specification type | F1b | {scrambled invariant, wrong conservation, off-scale} |
| `R` noise `η` | F2/F3 | 0 → dominates signal |
| Censor fraction `c` | F2/F3 | 0 → 1 |
| Oracle reliability `p` | F2/F3 | 1.0 → 0.5 |
| Shuffled-invariant | all A/B | permutation seed |

## 6. Difficulty / condition ladder

| Level | Condition | Pass = the *frame behaves as predicted* |
|-------|-----------|------------------------------------------|
| **F1** | absent/wrong `Pi`, clean `R` | `G ≈ 1` (F1a); high prior-rejection (F1b) |
| **F2** | good `Pi`, degraded `R` | monotone `G(η)` decline; gaming caught by `H` |
| **F3** | wrong `Pi`, degraded `R` | `G ≈ 1`, loud failure (low overconfidence penalty) |

Note the inversion: in F, a "pass" is the *theory* behaving correctly, not the agent winning. An agent
that posts high `G` on F1a/F3 has **falsified §8** (or is cheating) — which is a publishable result
either way.

## 7. Falsification map (F-specific)

| Paper claim | F test | Falsified if |
|-------------|--------|--------------|
| §8: `G → 1` as `Pi` weakens | F1a sweep over `φ` | `G` stays `> 1 + δ` at `φ = 0` |
| §8: agent detects a wrong `Pi` | F1b prior-rejection | rejection rate ≈ 0 (silent misuse) |
| §8: leaky `R` ⇒ graceful decline | F2 degradation curve | non-monotone, or `G` flat despite `η` |
| §8: both weak ⇒ collapse | F3 | `G ≫ 1` persists |
| **Benchmark integrity** | shuffled-invariant twin | `G(shuffled) > 1 + δ` (leakage) |

`δ` is the suite's declared noise floor on `G` (default `δ = 0.1`).

---

*F is the family most worth building first if the goal is credibility rather than a good headline: it
is the one that tells you whether any A/B number means what you think it means.*
