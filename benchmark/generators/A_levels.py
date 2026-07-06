#!/usr/bin/env python3
"""
ARC-AGI-2.5 -- Family A, Levels 2-4 (reference generators + held-out criteria + selfchecks).

Reuses the central-force physics from A_dynamics.py (symplectic integrator, basis laws, potentials).

  L2  compose within grammar : true force is a SUM of two basis terms; recover the term set.
                               H = long-horizon energy drift of the composed potential.
  L3  coupled multi-body     : 3 bodies interacting via one pairwise basis law; recover the law.
                               H = total (N-body) energy drift.
  L4  latent conserved qty   : recover a NON-obvious conserved quantity (Laplace-Runge-Lenz for the
                               inverse-square law); angular momentum is the "obvious" one.
                               H = the quantity is conserved on held-out data AND is discriminative
                               (not conserved for the wrong law) -> a genuine discovery.

Each level ships a `selfcheck` that gates shipping: it asserts the held-out criterion actually
discriminates the truth. Run:  python A_levels.py selfcheck --level {2,3,4}
"""
from __future__ import annotations
import argparse, itertools, math
import numpy as np
import A_dynamics as A          # LAWS, integrate, energy, energy_drift, BASIS, _accel_pos

BASIS = A.BASIS


# ======================================================================================
# L2 -- composition (basis-expansion): F(r) = sum_i k_i * shape_i(r)
# ======================================================================================
def accel_comp(x, y, terms):
    """terms = list of (shape, k). Uses A.LAWS[shape].F which already carries the sign for k>0."""
    r = math.hypot(x, y) + 1e-12
    Fr = sum(k * A.LAWS[s]["F"](r, 1.0) for s, k in terms)
    return Fr * x / r, Fr * y / r


def integrate_comp(state0, terms, dt, n):
    traj = np.empty((n, 4))
    x, y, vx, vy = (float(v) for v in state0)
    ax, ay = accel_comp(x, y, terms)
    for i in range(n):
        traj[i] = (x, y, vx, vy)
        x += vx * dt + 0.5 * ax * dt * dt
        y += vy * dt + 0.5 * ay * dt * dt
        ax2, ay2 = accel_comp(x, y, terms)
        vx += 0.5 * (ax + ax2) * dt
        vy += 0.5 * (ay + ay2) * dt
        ax, ay = ax2, ay2
    return traj


def energy_inconsistency(traj, shapes):
    """How well can a force built from `shapes` conserve energy along `traj`? Energy is
    KE + sum_i k_i g_i(r); it is constant iff KE is a linear combination of the g_i (plus offset).
    So regress KE onto {g_i(r), 1} and return the normalized residual. True structure -> ~0.
    Uses velocities directly (exact on the held-out trajectory), no acceleration estimate."""
    x, y, vx, vy = traj.T
    r = np.hypot(x, y) + 1e-12
    ke = 0.5 * (vx**2 + vy**2)
    cols = [A.LAWS[s]["PE"](r, 1.0) for s in shapes] + [np.ones_like(r)]
    Xd = np.stack(cols, 1)
    coef, *_ = np.linalg.lstsq(Xd, ke, rcond=None)
    resid = ke - Xd @ coef
    return float(np.std(resid) / (np.std(ke) + 1e-9))


# candidate structures: all single terms and all unordered pairs of distinct shapes
COMPOSE_PAIRS = [("inverse_square", "hooke"), ("inverse_square", "inverse_cube"),
                 ("inverse_linear", "hooke"), ("inverse_square", "constant")]
def compose_candidates():
    singles = [(s,) for s in BASIS]
    pairs = [tuple(p) for p in itertools.combinations(BASIS, 2)]
    return singles + pairs


def make_instance_L2(idx, rng):
    dt, n_short = 0.02, 700
    for _ in range(200):
        shapes = COMPOSE_PAIRS[rng.integers(len(COMPOSE_PAIRS))]
        ks = [float(rng.uniform(0.6, 1.3)), float(rng.uniform(0.3, 0.9))]
        terms = list(zip(shapes, ks))
        r0 = float(rng.uniform(0.9, 1.2)); 
        # rough circular speed from total force at r0
        Fr0 = abs(sum(k * A.LAWS[s]["F"](r0, 1.0) for s, k in terms))
        v0 = math.sqrt(Fr0 * r0) * float(rng.uniform(0.7, 0.9))
        state0 = np.array([r0, 0.0, 0.0, v0])
        long_traj = integrate_comp(state0, terms, dt, 10 * n_short)
        r = np.hypot(long_traj[:, 0], long_traj[:, 1])
        if r.min() > 0.25 and r.max() < 10 and r.max() / r.min() > 1.3 and np.isfinite(r).all():
            break
    else:
        raise RuntimeError("L2: could not condition an orbit")
    clean = integrate_comp(state0, terms, dt, n_short)
    snr = float(rng.choice([1.6, 1.0]))
    sig = float(np.std(clean[:, :2]))
    obs = np.hstack([np.arange(n_short)[:, None] * dt,
                     clean[:, :2] + rng.normal(0, sig / snr, clean[:, :2].shape)])
    return dict(task_id=f"A-L2-{idx:06d}", true_terms=terms, true_shapes=set(shapes),
                state0=state0, dt=dt, obs=obs, long_traj=long_traj)


def selfcheck_L2(n=30):
    rng = np.random.default_rng(0); ok = 0
    for i in range(n):
        inst = make_instance_L2(i, rng)
        scores = {c: energy_inconsistency(inst["long_traj"], c) for c in compose_candidates()}
        best = min(scores, key=scores.get)
        ok += (set(best) == inst["true_shapes"])
    rate = ok / n
    print(f"[L2 selfcheck] H (energy-conservation regression) recovers the true term-set in {ok}/{n} ({rate:.0%}).")
    assert rate >= 0.8, "L2 H not discriminative"
    print("OK: L2 held-out criterion discriminates the composition.")


# ======================================================================================
# L3 -- coupled multi-body: N bodies, one shared pairwise law
# ======================================================================================
def nbody_accel(pos, law, k, masses):
    n = len(pos); acc = np.zeros_like(pos)
    for i in range(n):
        for j in range(n):
            if i == j: continue
            d = pos[j] - pos[i]; r = math.hypot(d[0], d[1]) + 1e-9
            Fr = -A.LAWS[law]["F"](r, k)                 # attraction magnitude toward j (F<0 -> +d)
            acc[i] += (Fr * d / r) / masses[i]
    return acc


def integrate_nbody(pos0, vel0, law, k, masses, dt, n):
    pos, vel = pos0.copy(), vel0.copy()
    traj = np.empty((n, len(pos0), 2)); vtr = np.empty_like(traj)
    acc = nbody_accel(pos, law, k, masses)
    for t in range(n):
        traj[t] = pos; vtr[t] = vel
        pos = pos + vel * dt + 0.5 * acc * dt * dt
        acc2 = nbody_accel(pos, law, k, masses)
        vel = vel + 0.5 * (acc + acc2) * dt
        acc = acc2
    return traj, vtr


def nbody_ke(vtr, masses):
    return 0.5 * np.sum(masses[None, :, None] * vtr**2, axis=(1, 2))


def nbody_pe_shape(traj, law):
    """Sum over pairs of the law's unit potential (k factored out): total PE = k * this."""
    n = traj.shape[1]
    S = np.zeros(traj.shape[0])
    for i in range(n):
        for j in range(i + 1, n):
            d = traj[:, j] - traj[:, i]; r = np.hypot(d[:, 0], d[:, 1]) + 1e-9
            S += A.LAWS[law]["PE"](r, 1.0)
    return S


def nbody_inconsistency(traj, vtr, law, masses):
    """Energy KE + k*S(law) is constant iff KE is an affine function of S(law). Return the normalized
    residual of regressing KE on {S(law), 1} -> ~0 for the true pairwise law. No k refit needed."""
    ke = nbody_ke(vtr, masses)
    S = nbody_pe_shape(traj, law)
    Xd = np.stack([S, np.ones_like(S)], 1)
    coef, *_ = np.linalg.lstsq(Xd, ke, rcond=None)
    resid = ke - Xd @ coef
    return float(np.std(resid) / (np.std(ke) + 1e-9))


def make_instance_L3(idx, rng):
    dt = 0.01
    masses = np.array([3.0, 1.0, 1.0])
    for _ in range(300):
        true_law = rng.choice(BASIS); k = float(rng.uniform(0.8, 1.3))
        pos0 = np.array([[0.0, 0.0], [1.2, 0.0], [-1.0, 0.3]])
        # give the two light bodies roughly circular speeds around the heavy one
        v1 = math.sqrt(abs(A.LAWS[true_law]["F"](1.2, k)) * 3.0 / 1.2) * rng.uniform(0.7, 0.9)
        v2 = math.sqrt(abs(A.LAWS[true_law]["F"](1.05, k)) * 3.0 / 1.05) * rng.uniform(0.7, 0.9)
        vel0 = np.array([[0.0, 0.0], [0.0, v1], [0.0, -v2]])
        vel0[0] = -(masses[1] * vel0[1] + masses[2] * vel0[2]) / masses[0]   # zero total momentum
        n_short = 800
        traj, vtr = integrate_nbody(pos0, vel0, true_law, k, masses, dt, 6 * n_short)
        seps = np.sqrt(((traj[:, :, None, :] - traj[:, None, :, :]) ** 2).sum(-1))
        offdiag = seps[:, ~np.eye(3, dtype=bool)]
        if offdiag.min() > 0.25 and offdiag.max() < 12 and np.isfinite(traj).all():
            break
    else:
        raise RuntimeError("L3: could not condition a 3-body system")
    short = traj[:n_short]
    snr = 2.0; sig = float(np.std(short))
    obs = short + rng.normal(0, sig / snr, short.shape)
    return dict(task_id=f"A-L3-{idx:06d}", true_law=true_law, k=k, masses=masses,
                pos0=pos0, vel0=vel0, dt=dt, obs=obs,
                long_traj=traj, long_vtr=vtr)


def selfcheck_L3(n=20):
    rng = np.random.default_rng(0); ok = 0
    for i in range(n):
        inst = make_instance_L3(i, rng)
        scores = {law: nbody_inconsistency(inst["long_traj"], inst["long_vtr"], law, inst["masses"])
                  for law in BASIS}
        best = min(scores, key=scores.get)
        ok += (best == inst["true_law"])
    rate = ok / n
    print(f"[L3 selfcheck] H (N-body energy conservation) recovers the pairwise law in {ok}/{n} ({rate:.0%}).")
    assert rate >= 0.8, "L3 H not discriminative"
    print("OK: L3 held-out criterion discriminates the pairwise law.")


# ======================================================================================
# L4 -- latent conserved quantity (Laplace-Runge-Lenz for inverse-square)
# ======================================================================================
def quantity(traj, name, k=1.0):
    x, y, vx, vy = traj.T
    Lz = x * vy - y * vx                                  # angular momentum (obvious for any central force)
    if name == "angular_momentum":
        return Lz
    if name == "lrl_x":                                   # Laplace-Runge-Lenz x (latent; inverse-square only)
        r = np.hypot(x, y) + 1e-12
        return vy * Lz - k * x / r
    if name == "lrl_y":
        r = np.hypot(x, y) + 1e-12
        return -vx * Lz - k * y / r
    if name == "lrl_mag":                                # |LRL|: conserved for inverse-square, and
        r = np.hypot(x, y) + 1e-12                       # invariant to the slow numerical precession
        ax = vy * Lz - k * x / r
        ay = -vx * Lz - k * y / r
        return np.hypot(ax, ay)
    if name == "momentum_x":
        return vx
    if name == "momentum_y":
        return vy
    raise ValueError(name)


CONSERVED_CANDIDATES = ["angular_momentum", "lrl_x", "lrl_y", "momentum_x", "momentum_y"]


def conservation_score(traj, name, k=1.0):
    """Normalized variation: ~0 if conserved. Scale by the quantity's own RMS magnitude."""
    q = quantity(traj, name, k)
    return float(np.std(q) / (np.sqrt(np.mean(q**2)) + 1e-9))


def make_instance_L4(idx, rng):
    """Half the instances are inverse-square (LRL conserved = the latent discovery), half are a
    different central law (LRL NOT conserved) -- so 'LRL is conserved' is a real, falsifiable find."""
    dt, n_short = 0.02, 700
    is_kepler = bool(rng.integers(2))
    law = "inverse_square" if is_kepler else rng.choice(["inverse_linear", "hooke"])
    for _ in range(600):
        k = float(rng.uniform(0.8, 1.3)); r0 = float(rng.uniform(0.9, 1.2))
        v0 = math.sqrt(abs(A.LAWS[law]["F"](r0, k)) * r0) * float(rng.uniform(0.55, 0.82))
        state0 = np.array([r0, 0.0, 0.0, v0])
        long_traj = A.integrate(state0, law, k, dt, 10 * n_short)
        r = np.hypot(long_traj[:, 0], long_traj[:, 1])
        if r.min() > 0.15 and r.max() < 15 and r.max() / r.min() > 1.25 and np.isfinite(r).all():
            break
    else:
        raise RuntimeError("L4: could not condition an orbit")
    clean = A.integrate(state0, law, k, dt, n_short)
    obs = np.hstack([np.arange(n_short)[:, None] * dt, clean[:, :2] + rng.normal(0, 0.01, clean[:, :2].shape)])
    return dict(task_id=f"A-L4-{idx:06d}", law=law, k=k, is_kepler=is_kepler,
                state0=state0, dt=dt, obs=obs, long_traj=long_traj)


def selfcheck_L4(n=40):
    """The latent LRL vector must read as conserved for inverse-square and NOT for other laws.
    We score the LRL magnitude, which is invariant to the slow numerical precession of the orbit."""
    rng = np.random.default_rng(0)
    kepler_lrl, other_lrl = [], []
    for i in range(n):
        inst = make_instance_L4(i, rng)
        lrl = conservation_score(inst["long_traj"], "lrl_mag", inst["k"])
        (kepler_lrl if inst["is_kepler"] else other_lrl).append(lrl)
    kep, oth = np.array(kepler_lrl), np.array(other_lrl)
    print(f"[L4 selfcheck] |LRL| conservation score:  inverse-square median {np.median(kep):.4f}  "
          f"vs other-law median {np.median(oth):.4f}")
    thr = 0.05
    sep = (np.mean(kep < thr) + np.mean(oth > thr)) / 2
    print(f"  separation at thr={thr}: {sep:.0%}  (|LRL| conserved for Kepler, not for others)")
    assert np.median(kep) < thr < np.median(oth), "L4: LRL not discriminative between Kepler and others"
    print("OK: L4 latent quantity (LRL) is a genuine, discriminative discovery.")


def main():
    p = argparse.ArgumentParser(description="ARC-AGI-2.5 Family A, Levels 2-4.")
    sub = p.add_subparsers(required=True)
    s = sub.add_parser("selfcheck"); s.add_argument("--level", type=int, required=True, choices=[2, 3, 4])
    def _run(a):
        {2: selfcheck_L2, 3: selfcheck_L3, 4: selfcheck_L4}[a.level]()
    s.set_defaults(func=_run)
    a = p.parse_args(); a.func(a)


if __name__ == "__main__":
    main()
