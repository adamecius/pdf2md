from pdf2md.conventions.latex_groundtruth import extract_groundtruth_objects


def test_table_with_optional_position_is_detected():
    tex=r"\begin{table}[h]\caption{Sample table}\label{tab:one}\begin{tabular}{cc}A & B \\1 & 2\end{tabular}\end{table}"
    gt=extract_groundtruth_objects(tex,doc_id="d")
    tables=gt["tables"]
    assert len(tables)==1
    assert tables[0]["object_type"]=="table"
    assert tables[0]["label"]=="tab:one"


def test_source_environment_is_correct():
    tex=r"\begin{equation}E=mc^2\end{equation}\begin{figure}[h]\fbox{FIG}\caption{Boxed figure}\end{figure}\begin{table}[h]\caption{Sample table}\begin{tabular}{cc}A & B\end{tabular}\end{table}\begin{longtable}{cc}A & B\end{longtable}"
    gt=extract_groundtruth_objects(tex,"d")
    assert gt["equations"][0]["source_environment"]=="equation"
    assert gt["figures"][0]["source_environment"]=="figure"
    assert gt["tables"][0]["source_environment"]=="table"
    assert gt["tables"][1]["source_environment"]=="longtable"
