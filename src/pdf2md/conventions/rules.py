from __future__ import annotations
import re
from .schemas import Rule


def default_rules() -> list[Rule]:
    return [
        Rule("caption.figure_or_table_prefix", "*", "caption", r"^\s*(Figure|Fig\.|Table)\s+\d+(\.\d+)?\b", normalised_type="caption"),
        Rule("figure.placeholder_fig_near_caption", "*", "figure", r"^\s*FIG\s*$", normalised_type="picture", requires_near_caption_regex=r"^\s*(Figure|Fig\.)\s+\d+"),
        Rule("footnote.leading_digit_without_space", "*", "footnote", r"^\s*(\d+)([A-Za-z].*)", normalised_type="footnote", normalised_text_rewrite=r"\1 \2", y_norm_min=700),
        Rule("footnote.superscript_marker", "*", "footnote", r"^\s*[¹²³⁴⁵⁶⁷⁸⁹]\s*", normalised_type="footnote"),
        Rule("equation.parenthesised_label", "*", "equation", r"\(\s*(\d+(\.\d+)*)\s*\)\s*$", extract_equation_label=True),
        Rule("equation.latex_tag_label", "*", "equation", r"\\tag\{\s*(\d+(\.\d+)*)\s*\}", extract_equation_label=True),
        Rule("equation.number_split_block", "paddleocr", "equation_number", r"^\s*\(\s*\d+(\.\d+)*\s*\)\s*$", normalised_type="equation_number", merge_with_nearby_formula=True),
        Rule("footnote.bottom_page_paragraph", "*", "paragraph", r"^\s*(\(?\d+\)?|[¹²³⁴⁵⁶⁷⁸⁹])\s*[A-Za-z].*", normalised_type="footnote", y_norm_min=760),
        Rule("table.flattened_paragraph", "*", "paragraph", r"^\s*Table\s+\d+\s*:\s*.+", normalised_type="table"),
    ]


def rule_matches(rule: Rule, backend: str, object_type: str, text: str, y_norm: float | None = None) -> re.Match[str] | None:
    if rule.backend not in {"*", backend}:
        return None
    if rule.object_type not in {"*", object_type}:
        return None
    if rule.y_norm_min is not None and (y_norm is None or y_norm < rule.y_norm_min):
        return None
    return re.search(rule.text_regex, text or "")
