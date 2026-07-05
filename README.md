# Domain-Complete Intelligence — position note (LaTeX source)

Two-column, arXiv-style position note proposing **Domain-Complete Intelligence (DCI)**
as the missing rung between fluid reasoning (ARC-AGI Level 2) and universal agentic AGI,
grounded in the minAction.net / Network-Weighted Action Principle (NWAP) program.

## Submitting to arXiv

Target category: **cs.AI** (cross-list cs.LG). See **`ARXIV.md`** for the exact
metadata to paste into the submission form (title, authors, plain-text abstract,
comments, ACM classes) and upload instructions. A ready-to-upload, source-only
tarball with the pre-built bibliography is provided separately as
`minaction-dci-arxiv.tar.gz` (it compiles standalone from the shipped `main.bbl`).

## Build

Requires a TeX Live installation with `pdflatex` and `bibtex` (both standard).

```bash
make          # full build: pdflatex → bibtex → pdflatex ×2 → main.pdf
make quick    # single pass, for fast text-only preview
make clean    # remove build artifacts, keep the PDF
```

Or, if you prefer `latexmk`:

```bash
latexmk -pdf main.tex
```

The output is `main.pdf`.

## File layout

| File | What it is | Edit it if you want to… |
|------|------------|--------------------------|
| `main.tex` | Driver only (no prose) | change which sections are included / build order |
| `preamble.tex` | Shared style, packages, semantic macros | change formatting once, globally |
| `metadata.tex` | Title, authors, affiliations | add yourself as an author |
| `sections/00-abstract.tex` … `08-claim.tex` | The prose, one file per section | contribute content |
| `references.bib` | BibTeX bibliography | add / fix a reference |
| `Makefile` | Build recipes | — |
| `CONTRIBUTING.md` | House rules for edits | read before your first PR |

## Notation macros (defined in `preamble.tex`)

Use these instead of raw symbols so notation stays consistent across contributors:

- `\DCI` → DCI  ·  `\NWAP` → NWAP
- `\Dom` → 𝒟 (the domain)  ·  `\Rule` → ℛ (executable verifier / rule substrate)
- `\Prin` → Π (vertically organizing principle)
- `\Snw` → S_NW (network-weighted action)  ·  `\etap` → η²_p  ·  `\dQ` → ΔQ
- `\arxivid{2603.16951}` → hyperlinked `arXiv:2603.16951`

## Citation keys (in `references.bib`)

`frasch2026a` (physiology, *J Physiol*), `frasch2026b` (physics / MAL, arXiv:2603.16951),
`frasch2026c` (NAS / Emin–Imax, arXiv:2604.24805), `frasch2026d` (biology, arXiv:2605.05254),
`chollet2019`, `cholletarc2026` (ARC Prize 2025), `arcprize2026` (ARC-AGI-3 report),
`morris2024`, `cartwright1999`, `laughlin2000`, `anderson1972`,
`jumper2021`, `trinh2024`, `romera2024`, `ha2018`.

## Figure

`sections/04-cross-generality.tex` contains **Figure 1** (the object/meta reflexivity
loop), a TikZ diagram — no external image files, it compiles from source. Edit the TikZ
there if you want to adjust the schematic.

## Status

Draft for internal review. Figures and quantitative claims have been checked against
the source papers; see `CONTRIBUTING.md` for the standard every numeric claim must meet.
