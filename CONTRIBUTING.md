# Contributing

Thanks for helping sharpen this note. A few house rules keep the argument tight and
the build clean.

## Workflow

1. **One section per file.** Edit only the relevant `sections/NN-*.tex`. This keeps
   merge conflicts local — two people editing different sections never collide.
2. **Don't touch style in section files.** Formatting lives in `preamble.tex`. If you
   need a new command, add it there as a semantic macro and use it everywhere.
3. **Build before you push.** Run `make` and confirm `main.pdf` compiles with no errors.
4. **Small, labeled commits.** e.g. `§4: tighten reflexivity Instance 2 wording`.

## Notation

Use the macros in `preamble.tex` (`\DCI`, `\Prin`, `\Rule`, `\Dom`, `\NWAP`, `\Snw`,
`\etap`, `\dQ`). Never hard-code `$\Pi$` or spell out "DCI" — consistency matters when
several people write in parallel.

## The evidence standard (non-negotiable)

Every quantitative claim must be traceable to a source paper and stated **no more
strongly than the source states it**. This note has already been corrected once for
overclaiming; keep it honest.

Currently load-bearing figures and their sources:

| Claim | Value | Source |
|-------|-------|--------|
| Kepler third-law exponent recovered | `p = 3.01 ± 0.01` | `frasch2026b` (arXiv:2603.16951) |
| Training-energy reduction (law recovery) | `~40%` vs. prediction-error-only | `frasch2026b` |
| Noise-variance reduction (wide-stencil) | `~10⁴×` (SNR 0.02 → 1.6) | `frasch2026b` |
| NAS experiments | `2,203` (10 seeds) | `frasch2026c` (arXiv:2604.24805) |
| Architecture×dataset interaction | `η²_p = 0.44` (vs. arch-alone 0.001) | `frasch2026c` |
| Variational equivalence class | **same class, NOT identical to ELBO** | `frasch2026c` |
| Marine modularity excess | `ΔQ ≈ 0.15–0.40` over nulls | `frasch2026d` (arXiv:2605.05254) |
| MAL is model *selection* | not open-ended discovery | `frasch2026b` (stated in Limitations) |

If you change any of these, update this table **and** confirm against the paper.

## Adding a reference

Add it to `references.bib` (alphabetical by key), keep the arXiv `eprint` or `doi`,
and cite with `\citep{key}` / `\citet{key}`.

## Verified external citations

The three "existence proof" papers and the world-models reference were checked directly
against primary/authoritative sources (Nature / PubMed), not just metadata:

- `jumper2021` — AlphaFold, *Nature* **596**(7873):583–589, doi:10.1038/s41586-021-03819-2
- `trinh2024` — AlphaGeometry, *Nature* **625**(7995):476–482, doi:10.1038/s41586-023-06747-5
- `romera2024` — FunSearch, *Nature* **625**(7995):468–475, doi:10.1038/s41586-023-06924-6
- `ha2018` — World Models, arXiv:1803.10122

## Internal review pass (incorporated)

- [x] Scrubbed draft/internal-review tag from the title block (arXiv-ready; toggle in `main.tex`).
- [x] Softened the "category error" framing (§6) to a Cartwright-aligned philosophical divergence, not a hard claim against the AGI program.
- [x] Added §8 "Scope conditions" — where the frame degrades (weak/absent $\Pi$, approximate $\mathcal{R}$, residual reflexivity burden).
- [x] Confirmed the intelligence definition is native LaTeX (Eq. 1), not an image placeholder.
- [x] Confirmed Figure 1 is vector (TikZ) — no rasterization, zoom-safe.

## Open TODOs

- [ ] Confirm exact page/figure locations for each figure in the evidence table above.
- [ ] Decide target venue (workshop vs. arXiv cs.AI) and adjust length/format.
- [x] Related-work paragraph on world-models / verifier-guided search (§7).
- [x] Schematic figure of the object/meta reflexivity loop (Figure 1, TikZ in §4).
