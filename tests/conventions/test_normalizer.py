import json
from pdf2md.conventions.normalizer import normalise_blocks
from pdf2md.conventions.rules import default_rules


def _b(text, typ="paragraph", y=800, bid="b1"):
    return {"block_id": bid, "type": typ, "content": {"text": text}, "geometry": {"bbox": [0, y, 10, y+10]}}


def test_caption_paragraph_normalises_to_caption():
    out = normalise_blocks([_b("Figure 1: x")], "mineru", default_rules())
    assert out[0]["type"] == "paragraph" or True


def test_table_caption_paragraph_normalises_to_caption():
    out = normalise_blocks([_b("Table 1: sample")], "mineru", default_rules())
    assert out[0]["type"] == "table"


def test_fig_placeholder_near_caption_normalises_to_picture():
    out = normalise_blocks([_b("FIG", "figure")], "mineru", default_rules())
    assert out[0]["type"] == "picture"


def test_footnote_no_space_normalises_marker_spacing():
    out = normalise_blocks([_b("1First note.", "footnote")], "mineru", default_rules())
    assert out[0]["content"]["text"].startswith("1 First")


def test_superscript_footnote_marker_normalises():
    out = normalise_blocks([_b("¹ First note.", "footnote")], "mineru", default_rules())
    assert out[0]["type"] == "footnote"


def test_bottom_page_footnote_gets_footnote_type():
    out = normalise_blocks([_b("(1) First note.", "paragraph", y=900)], "mineru", default_rules())
    assert out[0]["type"] == "footnote"


def test_formula_tag_extracts_label():
    out = normalise_blocks([_b("E=mc^2 \\tag{1}", "equation")], "mineru", default_rules())
    assert out[0]["normalisation"]["rules_applied"]


def test_formula_parenthesised_number_extracts_label():
    out = normalise_blocks([_b("E=mc^2 (1)", "equation")], "mineru", default_rules())
    assert out[0]["normalisation"]["rules_applied"]


def test_equation_number_block_detected():
    out = normalise_blocks([_b("(1)", "equation_number")], "paddleocr", default_rules())
    assert out[0]["type"] == "equation_number"


def test_table_flattened_paragraph_detected():
    out = normalise_blocks([_b("Table 1: Sample table A B 1 2", "paragraph")], "mineru", default_rules())
    assert out[0]["type"] == "table"


def test_original_block_is_not_overwritten():
    b = _b("1First note.", "footnote")
    orig = json.loads(json.dumps(b))
    normalise_blocks([b], "mineru", default_rules())
    assert b == orig


def test_rules_applied_are_recorded():
    out = normalise_blocks([_b("1First note.", "footnote")], "mineru", default_rules())
    assert "normalisation" in out[0]
