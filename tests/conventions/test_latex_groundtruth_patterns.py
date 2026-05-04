from pdf2md.conventions.latex_groundtruth import extract_groundtruth_objects, equation_body_key


def test_formula_body_key_ignores_spacing_and_braces():
    assert equation_body_key("E = m c ^ { 2 }") == equation_body_key("E=mc^{2} \\tag{1}")


def test_reference_patterns_detect_figure_table_equation_section():
    tex = r"Figure~\ref{fig:one} Table~\ref{tab:one} Eq.~(\ref{eq:one}) Section~\ref{sec:one}"
    out = extract_groundtruth_objects(tex)
    labels = {r['label'] for r in out['references']}
    assert {"fig:one", "tab:one", "eq:one", "sec:one"}.issubset(labels)


def test_cref_autoref_eqref_patterns_detected():
    tex = r"\cref{fig:a,fig:b} \autoref{fig:one} \eqref{eq:one}"
    out = extract_groundtruth_objects(tex)
    labels = [r['label'] for r in out['references']]
    assert "fig:a" in labels and "fig:b" in labels and "fig:one" in labels and "eq:one" in labels
