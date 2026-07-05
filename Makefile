# =====================================================================
#  Makefile for the DCI position note
#  Usage:
#     make          build main.pdf (runs pdflatex + bibtex + pdflatex x2)
#     make quick    single pdflatex pass (no bibliography refresh)
#     make clean    remove build artifacts (keeps the PDF)
#     make purge    remove build artifacts AND the PDF
# =====================================================================
MAIN = main
LATEX = pdflatex -interaction=nonstopmode -halt-on-error
BIBTEX = bibtex

.PHONY: all quick clean purge

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex preamble.tex metadata.tex references.bib $(wildcard sections/*.tex)
	$(LATEX) $(MAIN)
	-$(BIBTEX) $(MAIN)
	$(LATEX) $(MAIN)
	$(LATEX) $(MAIN)
	@echo "Built $(MAIN).pdf"

quick:
	$(LATEX) $(MAIN)

clean:
	rm -f *.aux *.log *.out *.bbl *.blg *.toc *.fls *.fdb_latexmk sections/*.aux

purge: clean
	rm -f $(MAIN).pdf
