from pdf2md.conventions.latex_groundtruth import extract_groundtruth_objects, equation_body_key


def test_formula_body_key_ignores_spacing_and_braces():
    assert equation_body_key("E = m c ^ { 2 }") == equation_body_key("E=mc^{2} \\tag{1}")


def test_formula_variants_share_body_key():
    vals = [equation_body_key(v) for v in ["E = m c ^ { 2 }\\tag{1}", "E=mc^{2} \\quad (1)", "E   =  mc 2 (1)"]]
    assert len(set(vals)) == 1


def test_reference_patterns_detect_figure_table_equation_section():
    tex = r"Figure~\ref{fig:one} Table~\ref{tab:one} Eq.~(\ref{eq:one}) Section~\ref{sec:one}"
    labels = {r['label'] for r in extract_groundtruth_objects(tex)['references']}
    assert {"fig:one", "tab:one", "eq:one", "sec:one"}.issubset(labels)


def test_cref_autoref_eqref_patterns_detected():
    out = extract_groundtruth_objects(r"\cref{fig:a,fig:b} \autoref{fig:one} \eqref{eq:one}")
    labels = [r['label'] for r in out['references']]
    assert all(x in labels for x in ["fig:a", "fig:b", "fig:one", "eq:one"])


def test_figure_with_optional_position_detected():
    out = extract_groundtruth_objects(r"\begin{figure}[h]\caption{Cap}\label{fig:one}\end{figure}")
    assert out["figures"][0]["label"] == "fig:one"


def test_table_with_optional_position_detected():
    out = extract_groundtruth_objects(r"\begin{table}[htbp]\caption{Cap}\label{tab:one}\end{table}")
    assert out["tables"][0]["label"] == "tab:one"


def test_longtable_detected():
    out = extract_groundtruth_objects(r"\begin{longtable}{cc}\caption{Cap}\label{tab:lt}\end{longtable}")
    assert any(t.get("source_environment") == "longtable" for t in out["tables"])


def test_caption_optional_short_form_detected():
    out = extract_groundtruth_objects(r"\begin{figure}\caption[short]{long}\label{fig:s}\end{figure}")
    assert out["figures"][0]["caption"] == "long"


def test_footnotemark_and_footnotetext_detected():
    out = extract_groundtruth_objects(r"x\footnotemark y\footnotetext{First note.}")
    assert len(out["footnotes"]) == 2

def test_table_with_optional_position_has_gt_object():
    tex=r"""\begin{table}[h]\caption{Sample table}\label{tab:one}\begin{tabular}{cc}A & B \\ 1 & 2\end{tabular}\end{table}"""
    out=extract_groundtruth_objects(tex)
    t=out['tables'][0]
    assert t['object_type']=='table' and 'tab:one' in t['gt_id'] and t['caption_key']=='sampletable'
    assert 'ab12' in t['cell_text_key'] or set(['A','B','1','2']).issubset(set(t['cell_texts']))


def test_source_environment_is_correct():
    tex=r"""\begin{equation}x\end{equation}\begin{figure}\caption{c}\end{figure}\begin{table}\caption{t}\end{table}\begin{longtable}{cc}A&B\end{longtable}"""
    out=extract_groundtruth_objects(tex)
    assert out['equations'][0]['source_environment']=='equation'
    assert out['figures'][0]['source_environment']=='figure'
    assert any(t['source_environment']=='table' for t in out['tables'])
    assert any(t['source_environment']=='longtable' for t in out['tables'])
