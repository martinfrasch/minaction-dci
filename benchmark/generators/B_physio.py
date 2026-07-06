#!/usr/bin/env python3
"""
ARC-AGI-2.5 -- Family B (physiological mechanism discovery). Reference implementation.

A stand-in for the in-silico fetal physiology model: a stable linear autonomic system whose directed
coupling graph is the hidden ground truth. Nodes:
    0 mBP  maternal blood pressure
    1 mHR  maternal heart rate
    2 fHR  fetal heart rate
    3 fMove fetal movement / autonomic tone
Dynamics: x_t = W x_{t-1} + noise, W encoding the graph (W[i,j] != 0  <=>  edge j -> i).

Swap `TrueSystem` for an adapter onto the real in-silico model behind the same .simulate()/.perturb()
signature to run the real Family B.

Levels implemented:
    L1  recover the coupling graph                 H = counterfactual perturbation-response error
    L2  detect & localize a lesioned loop          -> Violation AUC
    L4  design the perturbation that disambiguates two candidate graphs (experiment design)

Each has a `selfcheck` gate:  python B_physio.py selfcheck --level {1,2,4}
"""
from __future__ import annotations
import argparse, itertools
import numpy as np

NODES = ["mBP", "mHR", "fHR", "fMove"]
N = len(NODES)

# True physiological edges (j -> i): (i, j, gain)
TRUE_EDGES = [
    (1, 0, -0.35),   # mBP -> mHR   baroreflex (negative)
    (0, 1,  0.28),   # mHR -> mBP   cardiac output
    (2, 1,  0.38),   # mHR -> fHR   maternal-fetal coupling
    (2, 3,  0.30),   # fMove -> fHR
    (3, 2,  0.26),   # fHR -> fMove
]
DIAG = 0.45          # autoregressive persistence on each node


def build_W(edges, diag=DIAG):
    W = np.zeros((N, N))
    for i in range(N):
        W[i, i] = diag
    for i, j, g in edges:
        W[i, j] = g
    return W


def spectral_radius(W):
    return float(np.max(np.abs(np.linalg.eigvals(W))))


class TrueSystem:
    """The hidden simulator. Provides passive observation and interventional perturbation."""
    def __init__(self, edges=TRUE_EDGES, diag=DIAG, noise=0.05, seed=0):
        self.W = build_W(edges, diag)
        self.noise = noise
        self.rng = np.random.default_rng(seed)
        assert spectral_radius(self.W) < 1.0, "unstable system"

    def simulate(self, T=2000, burn=200):
        x = np.zeros(N); out = []
        for _ in range(T + burn):
            x = self.W @ x + self.rng.normal(0, self.noise, N)
            out.append(x.copy())
        return np.array(out[burn:])

    def perturb(self, node, amp=1.0, steps=40):
        """Noise-free impulse response: clamp `node` with an impulse at t=0, watch the system relax."""
        x = np.zeros(N); x[node] += amp; traj = [x.copy()]
        for _ in range(steps):
            x = self.W @ x
            traj.append(x.copy())
        return np.array(traj)


# --------------------------------------------------------------------------------------
# Fitting: least-squares estimate of W restricted to a proposed support (set of (i,j) edges,
# diagonal always allowed). This is the in-loop verifier's model fit.
# --------------------------------------------------------------------------------------
def fit_W(X, support):
    """Regress x_t on x_{t-1}, restricting each row i to columns allowed by `support` (+ diagonal)."""
    Xt, Xtm1 = X[1:], X[:-1]
    W = np.zeros((N, N))
    allowed = {i: {i} for i in range(N)}
    for (i, j) in support:
        allowed[i].add(j)
    for i in range(N):
        cols = sorted(allowed[i])
        A = Xtm1[:, cols]
        coef, *_ = np.linalg.lstsq(A, Xt[:, i], rcond=None)
        for c, val in zip(cols, coef):
            W[i, c] = val
    return W


def one_step_error(X, W):
    """In-loop signal R: one-step prediction RMSE (gameable -> denser graphs fit better)."""
    pred = X[:-1] @ W.T
    return float(np.sqrt(np.mean((pred - X[1:]) ** 2)))


def counterfactual_error(W_fit, true_sys, amp=1.0, steps=40):
    """Held-out H: apply the SAME impulse to each node in the fitted model and the true system;
    compare the relaxation responses. A graph that misses real edges cannot reproduce how a
    perturbation propagates, even if it fit one-step dynamics well."""
    errs = []
    for p in range(N):
        true_resp = true_sys.perturb(p, amp, steps)
        x = np.zeros(N); x[p] += amp; fit_resp = [x.copy()]
        for _ in range(steps):
            x = W_fit @ x; fit_resp.append(x.copy())
        fit_resp = np.array(fit_resp)
        errs.append(np.sqrt(np.mean((fit_resp - true_resp) ** 2)))
    return float(np.mean(errs))


def true_support():
    return [(i, j) for (i, j, _) in TRUE_EDGES]


def all_offdiag_edges():
    return [(i, j) for i in range(N) for j in range(N) if i != j]


# ======================================================================================
# L1 -- recover the coupling graph
# ======================================================================================
def candidate_supports(rng):
    true = true_support()
    cands = {"true": true,
             "empty": [],
             "full": all_offdiag_edges()}
    # underspecified: drop one true edge
    drop = true[rng.integers(len(true))]
    cands["missing_edge"] = [e for e in true if e != drop]
    # overspecified: add one spurious edge
    spurious = [e for e in all_offdiag_edges() if e not in true]
    cands["extra_edge"] = true + [spurious[rng.integers(len(spurious))]]
    return cands


def selfcheck_L1(n=20):
    """H (counterfactual error) must rank the TRUE graph at or below every UNDER-specified graph:
    missing a real edge should be detectable via the perturbation response."""
    rng = np.random.default_rng(0)
    true_lt_missing = 0
    sr = spectral_radius(build_W(TRUE_EDGES))
    for s in range(n):
        sys = TrueSystem(seed=s)
        X = sys.simulate()
        cands = candidate_supports(np.random.default_rng(100 + s))
        H = {name: counterfactual_error(fit_W(X, sup), sys) for name, sup in cands.items()}
        true_lt_missing += (H["true"] < H["missing_edge"])
    rate = true_lt_missing / n
    print(f"[B-L1 selfcheck] spectral radius {sr:.2f} (stable). "
          f"H ranks true graph below the edge-missing graph in {true_lt_missing}/{n} ({rate:.0%}).")
    assert rate >= 0.8, "B-L1 H not discriminative"
    print("OK: B-L1 counterfactual criterion detects a missing causal edge.")


# ======================================================================================
# L2 -- lesion localization (Violation AUC)
# ======================================================================================
def auc(labels, scores):
    """ROC-AUC via rank statistic (higher score => more likely positive)."""
    labels = np.asarray(labels); scores = np.asarray(scores)
    pos, neg = scores[labels == 1], scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(scores); ranks = np.empty_like(order, float); ranks[order] = np.arange(len(scores))
    return float((ranks[labels == 1].sum() - len(pos) * (len(pos) - 1) / 2) / (len(pos) * len(neg)))


def selfcheck_L2(n=30):
    """Lesion one true edge; the fitted coefficient for the lesioned edge should be ~0 (violation).
    Ranking edges by -|coef| should put the lesioned edge on top -> Violation AUC near 1."""
    rng = np.random.default_rng(0)
    aucs = []
    te = true_support()
    for s in range(n):
        e_star = te[rng.integers(len(te))]
        les_edges = [(i, j, g) for (i, j, g) in TRUE_EDGES if (i, j) != e_star]
        sys = TrueSystem(edges=les_edges, seed=s)
        X = sys.simulate()
        W = fit_W(X, te)                                  # fit the intact reference support Pi
        labels = [1 if e == e_star else 0 for e in te]
        scores = [-abs(W[i, j]) for (i, j) in te]         # low |coef| => violated edge
        aucs.append(auc(labels, scores))
    mean_auc = float(np.nanmean(aucs))
    print(f"[B-L2 selfcheck] lesion-localization Violation AUC = {mean_auc:.3f} over {n} lesions.")
    assert mean_auc >= 0.9, "B-L2 lesion not localizable"
    print("OK: B-L2 localizes the lesioned loop (violation = departure from Pi).")


# ======================================================================================
# L4 -- experiment design (the reflexivity crown jewel)
# ======================================================================================
def make_ambiguous_pair(rng):
    """Two candidate graphs that differ by one edge. A well-chosen perturbation separates them;
    a poorly chosen one does not."""
    base = [(i, j, g) for (i, j, g) in TRUE_EDGES]
    # candidate A = true; candidate B = true with the coupling edge mHR->fHR rerouted fMove->fHR only
    A = base
    B = [(i, j, g) for (i, j, g) in base if (i, j) != (2, 1)]        # drop mHR->fHR
    return build_W(A), build_W(B)


def response_divergence(WA, WB, node, steps=40):
    """How differently do the two candidate graphs respond to a perturbation at `node`?"""
    def resp(W):
        x = np.zeros(N); x[node] += 1.0; tr = [x.copy()]
        for _ in range(steps):
            x = W @ x; tr.append(x.copy())
        return np.array(tr)
    return float(np.sqrt(np.mean((resp(WA) - resp(WB)) ** 2)))


def selfcheck_L4(n=20):
    """Prior-guided experiment design (pick the node that maximizes predicted divergence between the
    two candidate models) must disambiguate in FEWER experiments than random node choice."""
    rng = np.random.default_rng(0)
    prior_cost, rand_cost = [], []
    for s in range(n):
        WA, WB = make_ambiguous_pair(rng)
        div = {p: response_divergence(WA, WB, p) for p in range(N)}
        # prior-guided: choose argmax divergence -> 1 experiment if it separates
        best_p = max(div, key=div.get)
        prior_cost.append(1 if div[best_p] > 1e-3 else N)
        # random: expected number of tries until a separating node is hit
        sep_nodes = [p for p in range(N) if div[p] > 1e-3]
        rand_cost.append(N / max(1, len(sep_nodes)))
    pc, rc = float(np.mean(prior_cost)), float(np.mean(rand_cost))
    G = rc / pc
    print(f"[B-L4 selfcheck] experiment-design cost: prior-guided {pc:.2f}  random {rc:.2f}  "
          f"efficiency-gain G = {G:.2f}")
    assert G > 1.0, "B-L4 experiment design shows no advantage"
    print("OK: B-L4 prior-guided experiment design disambiguates with less experience (reflexivity).")


def main():
    p = argparse.ArgumentParser(description="ARC-AGI-2.5 Family B (physiological mechanism discovery).")
    sub = p.add_subparsers(required=True)
    s = sub.add_parser("selfcheck"); s.add_argument("--level", type=int, required=True, choices=[1, 2, 4])
    def _run(a):
        {1: selfcheck_L1, 2: selfcheck_L2, 4: selfcheck_L4}[a.level]()
    s.set_defaults(func=_run)
    a = p.parse_args(); a.func(a)


if __name__ == "__main__":
    main()
