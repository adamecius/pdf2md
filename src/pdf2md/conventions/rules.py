from __future__ import annotations
import re
from .schemas import Rule


def default_rules() -> list[Rule]:
    return [
        Rule("caption.figure_or_table_prefix", "*", "*", r"^\s*(Figure|Fig\.|Table)\s+\d+(\.\d+)?\s*[:.]?", normalised_type="caption"),
        Rule("figure.placeholder_fig_near_caption", "*", "*", r"^\s*FIG\s*$", normalised_type="picture", requires_near_caption_regex=r"^\s*(Figure|Fig\.)\s+\d+"),
        Rule("footnote.leading_digit_without_space", "*", "*", r"^\s*(\d+)([A-Za-z].*)", normalised_type="footnote", normalised_text_rewrite=r"\1 \2", y_norm_min=700),
        Rule("footnote.superscript_marker", "*", "*", r"^\s*([¹²³⁴⁵⁶⁷⁸⁹])\s*([A-Za-z].*)", normalised_type="footnote", normalised_text_rewrite=r"1 \2"),
        Rule("footnote.caret_marker", "*", "*", r"^\s*\^(\d+)\s*([A-Za-z].*)", normalised_type="footnote", normalised_text_rewrite=r"\1 \2"),
        Rule("footnote.parenthesised_marker", "*", "*", r"^\s*\((\d+)\)\s*([A-Za-z].*)", normalised_type="footnote", normalised_text_rewrite=r"\1 \2"),
        Rule("equation.parenthesised_label", "*", "*", r"\(\s*(\d+(\.\d+)*)\s*\)\s*$", extract_equation_label=True),
        Rule("equation.latex_tag_label", "*", "*", r"\\tag\{\s*(\d+(\.\d+)*)\s*\}", extract_equation_label=True),
        Rule("equation.number_split_block", "paddleocr", "*", r"^\s*\(\s*\d+(\.\d+)*\s*\)\s*$", normalised_type="equation_number", merge_with_nearby_formula=True),
        Rule("table.flattened_paragraph", "*", "*", r"^\s*Table\s+\d+\s*:\s*.+", normalised_type="table"),
        Rule("deepseek.geometryless_exact_text_merge_hint", "deepseek", "*", r".+", geometry_required=False, merge_when_text_exact=True),
    ]


def rule_matches(rule: Rule, backend: str, object_type: str, text: str, y_norm: float | None = None) -> re.Match[str] | None:
    if rule.backend not in {"*", backend}:
        return None
    if rule.object_type not in {"*", object_type}:
        return None
    if rule.y_norm_min is not None and (y_norm is None or y_norm < rule.y_norm_min):
        return None
    return re.search(rule.text_regex, text or "")
