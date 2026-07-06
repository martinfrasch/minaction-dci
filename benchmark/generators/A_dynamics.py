#!/usr/bin/env python3
"""
ARC-AGI-2.5 -- Family A, Level 1 (law recovery from noisy dynamics).

Runnable reference implementation of the FULL protocol for A-L1:
  - generator      : samples a hidden central-force law + noisy short-horizon observation
  - R (verifier)   : in-loop signal = short-horizon RMSE after fitting the coupling constant k
  - H (held-out)   : long-horizon ENERGY-DRIFT criterion the agent never sees (the anti-Goodhart tier)
  - baseline agent : "select the basis law with lowest R signal", then submit it

This is intentionally dependency-light (numpy + stdlib) so it runs anywhere and demonstrates
the two-tier verification and the Chollet-native efficiency score end to end.

Usage:
    python A_dynamics.py demo      --n 20 --seed 0
    python A_dynamics.py generate  --n 200 --seed 0 --out ../suites/A_L1.jsonl
    python A_dynamics.py selfcheck            # asserts H discriminates the true law

The verifier here is a local stand-in for the MAL pipeline (2026b, arXiv:2603.16951); swap
`ShortHorizonRMSE` for a MAL adapter behind the same .query() signature to use the real thing.
"""
from __future__ import annotations
import argparse, json, math, sys
from dataclasses import dataclass, field
import numpy as np

# --------------------------------------------------------------------------------------
# Basis of candidate central-force laws (the L1 "grammar": selection, no composition).
# Each law: radial force magnitude F(r; k) (negative = attractive/inward) and its potential PE(r; k).
# PE is defined so that F = -dPE/dr. Energy along a trajectory is KE + PE (unit mass).
# --------------------------------------------------------------------------------------
LAWS = {
    "inverse_square": dict(sexpr="(* (- k) (/ 1 (^ r 2)))", F=lambda r, k: -k / r**2,  PE=lambda r, k: -k / r),
    "inverse_linear": dict(sexpr="(* (- k) (/ 1 r))",       F=lambda r, k: -k / r,     PE=lambda r, k: k * np.log(r)),
    "hooke":          dict(sexpr="(* (- k) r)",             F=lambda r, k: -k * r,     PE=lambda r, k: 0.5 * k * r**2),
    "inverse_cube":   dict(sexpr="(* (- k) (/ 1 (^ r 3)))", F=lambda r, k: -k / r**3,  PE=lambda r, k: -0.5 * k / r**2),
    "constant":       dict(sexpr="(- k)",                   F=lambda r, k: -k + 0 * r, PE=lambda r, k: k * r),
}
BASIS = list(LAWS.keys())
GRAMMAR_ID = "phys_basis_v1"

# Prior description length in bits (toy value): the action+Noether prior that restricts search to
# conservative central forces. Used as P in the efficiency denominator for the `full` condition.
P_BITS_PI = 41.0


# --------------------------------------------------------------------------------------
# Physics: 2D central-force integrator (RK4), unit mass, force centre fixed at origin.
# --------------------------------------------------------------------------------------
def _accel_pos(x: float, y: float, law: str, k: float):
    r = math.hypot(x, y) + 1e-12
    Fr = LAWS[law]["F"](r, k)          # radial force (inward if negative)
    return Fr * x / r, Fr * y / r


def integrate(state0: np.ndarray, law: str, k: float, dt: float, n: int) -> np.ndarray:
    """Velocity-Verlet (symplectic) integration. Returns (n, 4) = [x, y, vx, vy].
    Symplectic => the TRUE law conserves energy with no secular drift, which is what makes the
    held-out energy criterion clean. Counts as ONE R integration."""
    traj = np.empty((n, 4))
    x, y, vx, vy = (float(v) for v in state0)
    ax, ay = _accel_pos(x, y, law, k)
    for i in range(n):
        traj[i] = (x, y, vx, vy)
        x += vx * dt + 0.5 * ax * dt * dt
        y += vy * dt + 0.5 * ay * dt * dt
        ax2, ay2 = _accel_pos(x, y, law, k)
        vx += 0.5 * (ax + ax2) * dt
        vy += 0.5 * (ay + ay2) * dt
        ax, ay = ax2, ay2
    return traj


def energy(traj: np.ndarray, law: str, k: float) -> np.ndarray:
    """Total energy KE+PE along a trajectory, using `law`'s potential (unit mass)."""
    x, y, vx, vy = traj.T
    r = np.hypot(x, y) + 1e-12
    ke = 0.5 * (vx**2 + vy**2)
    pe = LAWS[law]["PE"](r, k)
    return ke + pe


def energy_drift(traj: np.ndarray, law: str, k: float) -> float:
    """Held-out discriminator: variation of the candidate law's total energy along `traj`,
    normalized by the kinetic-energy variation (which is law-independent and offset-free).
    True law -> ~0 (energy conserved); wrong law -> O(1)+ because its PE cannot cancel KE(r)."""
    x, y, vx, vy = traj.T
    ke = 0.5 * (vx**2 + vy**2)
    E = energy(traj, law, k)
    return float(np.std(E) / (np.std(ke) + 1e-9))


# --------------------------------------------------------------------------------------
# Task instance
# --------------------------------------------------------------------------------------
@dataclass
class Instance:
    task_id: str
    true_law: str
    k_true: float
    state0: np.ndarray
    dt: float
    n_short: int
    n_long: int
    snr: float
    seed: int
    obs_series: np.ndarray = field(default=None)      # noisy short-horizon [t,x,y] shown to agent
    long_traj: np.ndarray = field(default=None)       # HELD-OUT ground-truth long trajectory (H only)

    def to_task_json(self, condition="full") -> dict:
        series = [[float(t), float(x), float(y)] for t, x, y in self.obs_series]
        return {
            "task_id": self.task_id,
            "family": "A",
            "level": 1,
            "domain": "newtonian_dynamics",
            "observation": {"series": series, "snr": self.snr, "units": "SI"},
            "budget": {"unit": "integrations", "E_max": float(len(BASIS) * 14 + 2)},
            "prior": {"pi": "action_noether", "provided": (condition in ("full", "R_off", "shuffled_invariant"))},
            "answer_schema": "symbolic_law_sexpr",
            "grammar_id": GRAMMAR_ID,
            "verifier": f"rho://A/{self.task_id.split('-')[-1]}",
            "condition": condition,
            "seed": self.seed,
        }


def make_instance(idx: int, rng: np.random.Generator) -> Instance:
    """Sample a well-conditioned, eccentric bound orbit (eccentricity gives r-variation, which is
    what makes the held-out energy criterion discriminative)."""
    dt, n_short, snr = 0.02, 700, float(rng.choice([1.6, 1.0, 0.6]))   # ~2 orbits of observation
    n_long = 10 * n_short
    for _attempt in range(200):
        true_law = rng.choice(BASIS)
        k_true = float(rng.uniform(0.7, 1.4))
        r0 = float(rng.uniform(0.9, 1.3))
        v_circ = math.sqrt(abs(LAWS[true_law]["F"](r0, k_true)) * r0)
        v0 = v_circ * float(rng.uniform(0.55, 0.80))     # eccentric -> wide r-range
        state0 = np.array([r0, 0.0, 0.0, v0])
        long_traj = integrate(state0, true_law, k_true, dt, n_long)
        r = np.hypot(long_traj[:, 0], long_traj[:, 1])
        # keep only clean bound orbits with real r-variation and no near-collision / escape
        if r.min() > 0.20 and r.max() < 12.0 and (r.max() / r.min()) > 1.4 and np.isfinite(r).all():
            break
    else:
        raise RuntimeError("could not sample a well-conditioned orbit")

    inst = Instance(
        task_id=f"A-L1-{idx:06d}", true_law=true_law, k_true=k_true, state0=state0,
        dt=dt, n_short=n_short, n_long=n_long, snr=snr, seed=int(rng.integers(0, 2**31 - 1)),
    )
    clean_short = integrate(state0, true_law, k_true, dt, n_short)
    sig = float(np.std(clean_short[:, :2]))
    noise = rng.normal(0.0, sig / snr, size=clean_short[:, :2].shape)
    t = np.arange(n_short)[:, None] * dt
    inst.obs_series = np.hstack([t, clean_short[:, :2] + noise])
    inst.long_traj = long_traj      # held out
    return inst


# --------------------------------------------------------------------------------------
# R -- in-loop verifier: fit k for a candidate law, return short-horizon RMSE vs the OBSERVED data.
# Returns (signal, cost_in_integrations). Never exposes the H value.
# --------------------------------------------------------------------------------------
def R_query(inst: Instance, law: str, k_lo: float = 0.3, k_hi: float = 2.0, n_grid: int = 14,
            r_noise: float = 0.0, rng: np.random.Generator | None = None):
    """In-loop verifier: fit k over [k_lo, k_hi] on an n_grid grid, return (best_short_horizon_RMSE,
    integrations_used). A Pi-informed agent may pass a narrower [k_lo,k_hi] and smaller n_grid --
    fewer integrations for the same law-selection accuracy. Never exposes the held-out H value."""
    obs_xy = inst.obs_series[:, 1:3]
    ks = np.linspace(k_lo, k_hi, n_grid)
    best_rmse, integrations = np.inf, 0
    for k in ks:
        pred = integrate(inst.state0, law, float(k), inst.dt, inst.n_short)[:, :2]
        integrations += 1
        best_rmse = min(best_rmse, float(np.sqrt(np.mean((pred - obs_xy) ** 2))))
    if r_noise and rng is not None:          # F2/F3: degrade the verifier
        best_rmse *= float(np.exp(rng.normal(0.0, r_noise)))
    return best_rmse, integrations


def _fit_k(inst: Instance, law: str) -> float:
    obs_xy = inst.obs_series[:, 1:3]
    ks = np.linspace(0.3, 2.0, 41)
    errs = [np.mean((integrate(inst.state0, law, float(k), inst.dt, inst.n_short)[:, :2] - obs_xy) ** 2) for k in ks]
    return float(ks[int(np.argmin(errs))])


# --------------------------------------------------------------------------------------
# H -- held-out criterion: long-horizon ENERGY DRIFT of the submitted law along the TRUE long
# trajectory (which the agent never queried). True law -> ~0 drift; wrong law -> large drift.
# --------------------------------------------------------------------------------------
EPS_CONSERVE = 0.05     # pass threshold on normalized energy drift


def H_score(inst: Instance, submitted_law: str, r_signal_passed: bool,
            condition: str, e_used: int, confidence: float = 1.0) -> dict:
    k_fit = _fit_k(inst, submitted_law)
    drift = energy_drift(inst.long_traj, submitted_law, k_fit)     # normalized, offset-free
    passed_H = drift <= EPS_CONSERVE
    correct = (submitted_law == inst.true_law)
    success = 1.0 if (correct and passed_H) else 0.0
    gaming = bool(r_signal_passed and not passed_H)          # passed in-loop, failed held-out

    GD = 1.0                                                 # L1 weight
    P_bits = P_BITS_PI if condition in ("full", "R_off") else 0.0
    # P/E commensuration (declared suite parameter, see SPEC 4.1): the compressed prior costs a small
    # number of EXPERIENCE-EQUIVALENTS, reflecting its short description length relative to the
    # experience it replaces. Cost is measured in integration-equivalents (same unit as E_used).
    P_EQUIV = 5.0 if condition in ("full", "R_off") else 0.0
    E_max = float(len(BASIS) * 14 + 2)
    E_norm = min(1.0, e_used / E_max)
    cost = P_EQUIV + e_used
    efficiency = (success * GD / cost) if cost > 0 else 0.0
    return {
        "task_id": inst.task_id, "condition": condition, "success": success,
        "gaming_flag": gaming, "held_out_value": drift, "GD": GD, "P_bits": P_bits,
        "E_used": float(e_used), "E_norm": E_norm, "efficiency": efficiency,
        "overconfident_wrong": bool(success == 0.0 and confidence >= 0.7),
        "notes": f"true={inst.true_law} submitted={submitted_law} k_fit={k_fit:.3f}",
    }


# --------------------------------------------------------------------------------------
# Agents.
#   exhaustive   : fit k over a broad range with a fine grid for every law (no prior; pi_off policy)
#   prior_guided : Pi supplies the physical k-scale, so fit k over a narrow range with a coarse grid
#                  -> far fewer integrations for the same law-selection accuracy (the DCI signal).
# --------------------------------------------------------------------------------------
def exhaustive_agent(inst: Instance, r_noise: float, rng):
    """No prior: fit k over a BROAD range with a fine grid for every law (expensive), pick lowest RMSE."""
    signals, e_used = {}, 0
    for law in BASIS:
        sig, cost = R_query(inst, law, k_lo=0.3, k_hi=2.0, n_grid=14, r_noise=r_noise, rng=rng)
        signals[law] = sig
        e_used += cost
    submitted = min(signals, key=signals.get)
    r_passed = signals[submitted] <= float(np.median(list(signals.values())))
    return submitted, r_passed, e_used


def prior_guided_agent(inst: Instance, r_noise: float, rng, k_lo: float = 0.7, k_hi: float = 1.4):
    """Pi supplies the physical parameter scale, so the agent fits k over a NARROW range with a coarse
    grid -- far fewer integrations for the SAME law-selection accuracy (it still tests every law). This
    is 'the prior lowers experience E' without sacrificing accuracy: the prior constrains the parameter
    search, not the hypothesis class. The held-out H still guards against gaming under a noisy R.
    The [k_lo,k_hi] window IS the invariant; the shuffled-invariant control passes a wrong window."""
    signals, e_used = {}, 0
    for law in BASIS:
        sig, cost = R_query(inst, law, k_lo=k_lo, k_hi=k_hi, n_grid=4, r_noise=r_noise, rng=rng)
        signals[law] = sig
        e_used += cost
    submitted = min(signals, key=signals.get)
    r_passed = signals[submitted] <= float(np.median(list(signals.values())))
    return submitted, r_passed, e_used


def run_agent(inst, condition, r_noise, rng):
    if condition in ("pi_off", "baseline"):
        return exhaustive_agent(inst, r_noise, rng)
    return prior_guided_agent(inst, r_noise, rng)     # full / R_off / shuffled_invariant use the prior


# --------------------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------------------
def cmd_demo(args):
    rng = np.random.default_rng(args.seed)
    reports = []
    for i in range(args.n):
        inst = make_instance(i, rng)
        submitted, r_passed, e_used = run_agent(inst, args.condition, args.r_noise, rng)
        rep = H_score(inst, submitted, r_passed, args.condition, e_used)
        reports.append(rep)
    succ = np.mean([r["success"] for r in reports])
    gaming = np.mean([r["gaming_flag"] for r in reports])
    eff = np.mean([r["efficiency"] for r in reports])
    drift = np.mean([r["held_out_value"] for r in reports])
    e_mean = np.mean([r["E_used"] for r in reports])
    print(f"[A-L1 demo]  n={args.n}  condition={args.condition}  R_noise={args.r_noise}")
    print(f"  success rate      : {succ:.3f}")
    print(f"  gaming rate       : {gaming:.3f}")
    print(f"  mean E (integr.)  : {e_mean:.1f}")
    print(f"  mean efficiency   : {eff:.3f}")
    print(f"  mean energy drift : {drift:.4f}   (H pass threshold = {EPS_CONSERVE})")


def cmd_integrity(args):
    """Shuffled-invariant integrity check. Runs the prior-guided agent with the CORRECT parameter
    window and with a SCRAMBLED (wrong) window, both against the exhaustive baseline. A valid
    benchmark shows the advantage vanish under the scrambled invariant (G ~ 1); if it persists, the
    'advantage' was leakage, not the prior."""
    def eff(condition, k_lo=None, k_hi=None):
        rng = np.random.default_rng(args.seed)
        reps = []
        for i in range(args.n):
            inst = make_instance(i, rng)
            if condition == "pi_off":
                sub, rp, e = exhaustive_agent(inst, args.r_noise, rng)
                cond = "pi_off"
            else:
                sub, rp, e = prior_guided_agent(inst, args.r_noise, rng, k_lo=k_lo, k_hi=k_hi)
                cond = "full"
            reps.append(H_score(inst, sub, rp, cond, e))
        return float(np.mean([r["efficiency"] for r in reps])), float(np.mean([r["success"] for r in reps]))
    e_true, s_true = eff("full", 0.7, 1.4)          # correct invariant (true k ~ U[0.7,1.4])
    e_shuf, s_shuf = eff("full", 0.30, 0.55)         # scrambled invariant: wrong k-window
    e_pi, s_pi = eff("pi_off")
    G_true, G_shuf = e_true / e_pi, e_shuf / e_pi
    delta = 0.10
    print(f"[A-L1 integrity]  n={args.n}")
    print(f"  correct invariant  : success {s_true:.3f}  G = {G_true:.2f}")
    print(f"  shuffled invariant : success {s_shuf:.3f}  G = {G_shuf:.2f}   (must be <= {1+delta:.2f})")
    print(f"  baseline (exhaustive): success {s_pi:.3f}")
    verdict = "PASS: advantage collapses under the scrambled prior (no leakage)." if G_shuf <= 1 + delta \
        else "FAIL: advantage persists with a wrong prior -> leakage; fix the task."
    print(f"  --> {verdict}")


def cmd_compare(args):
    """Run the two ablations on the SAME instances and report the DCI efficiency-gain G."""
    def run(condition):
        rng = np.random.default_rng(args.seed)     # same seed -> same instances across conditions
        reps = []
        for i in range(args.n):
            inst = make_instance(i, rng)
            sub, rp, e = run_agent(inst, condition, args.r_noise, rng)
            reps.append(H_score(inst, sub, rp, condition, e))
        return reps
    full, pioff = run("full"), run("pi_off")
    ef_full = np.mean([r["efficiency"] for r in full])
    ef_pioff = np.mean([r["efficiency"] for r in pioff])
    e_full = np.mean([r["E_used"] for r in full])
    e_pioff = np.mean([r["E_used"] for r in pioff])
    G = ef_full / ef_pioff if ef_pioff > 0 else float("inf")
    print(f"[A-L1 compare]  n={args.n}  R_noise={args.r_noise}")
    print(f"  full  (prior-guided): success {np.mean([r['success'] for r in full]):.3f}  "
          f"E {e_full:.1f}  efficiency {ef_full:.3f}")
    print(f"  pi_off (exhaustive) : success {np.mean([r['success'] for r in pioff]):.3f}  "
          f"E {e_pioff:.1f}  efficiency {ef_pioff:.3f}")
    print(f"  --> efficiency-gain  G = {G:.2f}   (DCI advantage iff G > 1; here it comes from lower E)")


def cmd_generate(args):
    rng = np.random.default_rng(args.seed)
    out = args.out
    with open(out, "w") as f:
        for i in range(args.n):
            inst = make_instance(i, rng)
            f.write(json.dumps(inst.to_task_json(condition=args.condition)) + "\n")
    print(f"wrote {args.n} A-L1 instances -> {out}")


def cmd_selfcheck(args):
    """Assert the held-out H actually discriminates the true law from the rest, and report the
    separation between true-law drift and best wrong-law drift (used to set EPS_CONSERVE)."""
    rng = np.random.default_rng(0)
    n_ok, true_drifts, wrong_best = 0, [], []
    for i in range(40):
        inst = make_instance(i, rng)
        drifts = {}
        for law in BASIS:
            k = _fit_k(inst, law)
            drifts[law] = energy_drift(inst.long_traj, law, k)
        best = min(drifts, key=drifts.get)
        n_ok += (best == inst.true_law)
        true_drifts.append(drifts[inst.true_law])
        wrong_best.append(min(v for l, v in drifts.items() if l != inst.true_law))
    rate = n_ok / 40
    td, wb = np.array(true_drifts), np.array(wrong_best)
    print(f"[selfcheck] H picks the true law by lowest energy drift in {n_ok}/40 cases ({rate:.0%}).")
    print(f"  true-law drift     : median {np.median(td):.4f}   p90 {np.percentile(td, 90):.4f}")
    print(f"  best wrong-law drift: median {np.median(wb):.4f}   p10 {np.percentile(wb, 10):.4f}")
    print(f"  suggested EPS_CONSERVE in ({np.percentile(td, 90):.3f}, {np.percentile(wb, 10):.3f})  (current {EPS_CONSERVE})")
    assert rate >= 0.8, "H is not discriminative enough -- fix the criterion before shipping."
    print("OK: held-out criterion H is discriminative.")


def main():
    p = argparse.ArgumentParser(description="ARC-AGI-2.5 Family A / Level 1 reference implementation.")
    sub = p.add_subparsers(required=True)
    d = sub.add_parser("demo"); d.add_argument("--n", type=int, default=20); d.add_argument("--seed", type=int, default=0)
    d.add_argument("--condition", default="full", choices=["full", "pi_off", "R_off", "baseline", "shuffled_invariant"])
    d.add_argument("--r_noise", type=float, default=0.0, help="F2/F3: lognormal noise on the R signal.")
    d.set_defaults(func=cmd_demo)
    g = sub.add_parser("generate"); g.add_argument("--n", type=int, default=200); g.add_argument("--seed", type=int, default=0)
    g.add_argument("--out", default="A_L1.jsonl"); g.add_argument("--condition", default="full")
    g.set_defaults(func=cmd_generate)
    c = sub.add_parser("compare"); c.add_argument("--n", type=int, default=40); c.add_argument("--seed", type=int, default=0)
    c.add_argument("--r_noise", type=float, default=0.0)
    c.set_defaults(func=cmd_compare)
    it = sub.add_parser("integrity"); it.add_argument("--n", type=int, default=80); it.add_argument("--seed", type=int, default=0)
    it.add_argument("--r_noise", type=float, default=0.0)
    it.set_defaults(func=cmd_integrity)
    s = sub.add_parser("selfcheck"); s.set_defaults(func=cmd_selfcheck)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
