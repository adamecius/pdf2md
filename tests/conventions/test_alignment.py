from pdf2md.conventions.latex_groundtruth import extract_groundtruth_objects
from pdf2md.conventions.alignment import align_groundtruth_to_backend


def _fixture():
    tex=r"""\section{All}\begin{figure}[h]\fbox{FIG}\caption{Boxed figure}\label{fig:one}\end{figure}
\begin{table}[h]\caption{Sample table}\label{tab:one}\begin{tabular}{cc}A & B \\ 1 & 2\end{tabular}\end{table}
\begin{equation}E=mc^2\tag{1}\label{eq:one}\end{equation}
See Figure~\ref{fig:one}, Table~\ref{tab:one}, Eq.~(\ref{eq:one}), Section~\ref{sec:one}. A\footnote{First note.}"""
    return extract_groundtruth_objects(tex)


def test_alignment_equation_formula_plus_number_block():
    gt=_fixture(); blocks=[{'block_id':'b1','type':'formula','content':{'text':'E=mc^2'}},{'block_id':'b2','type':'paragraph','content':{'text':'(1)'}}]
    als=align_groundtruth_to_backend(gt,blocks,backend='paddleocr',doc_id='d')
    assert any(a['object_type']=='equation' and len(a['matched_blocks'])>=2 for a in als)


def test_alignment_figure_fig_placeholder_and_caption():
    gt=_fixture(); blocks=[{'block_id':'b1','type':'paragraph','content':{'text':'FIG'}},{'block_id':'b2','type':'caption','content':{'text':'Figure 1 Boxed figure'}}]
    als=align_groundtruth_to_backend(gt,blocks,backend='pymupdf',doc_id='d')
    assert any(a['object_type']=='figure' for a in als)


def test_alignment_table_flattened_caption_cells():
    gt=_fixture(); blocks=[{'block_id':'b1','type':'paragraph','content':{'text':'Table 1: Sample table A B 1 2'}}]
    als=align_groundtruth_to_backend(gt,blocks,backend='mineru',doc_id='d')
    assert any(a['object_type']=='table' for a in als)


def test_alignment_footnote_no_space_marker():
    gt=_fixture(); blocks=[{'block_id':'b1','type':'unknown','content':{'text':'1First note.'}}]
    als=align_groundtruth_to_backend(gt,blocks,backend='mineru',doc_id='d')
    assert any(a['object_type']=='footnote' for a in als)
