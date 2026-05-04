from __future__ import annotations
import re

EQ_ENV_RE = re.compile(r"\\begin\{(equation\*?|align\*?|aligned|gather\*?|multline\*?|eqnarray|split)\}(.*?)\\end\{\1\}", re.S)
DISPLAY_RE = re.compile(r"\\\[(.*?)\\\]|\$\$(.*?)\$\$", re.S)
REF_CMD_RE = re.compile(r"\\(?:ref|autoref|cref|Cref|eqref)\{([^}]+)\}")
TEXT_REF_RE = re.compile(r"\b(?:Figure|Fig\.|Table|Eq\.?|Equation|Section|Sec\.|Chapter)\s*~?\(?\\ref\{([^}]+)\}\)?")
FIG_RE = re.compile(r"\\begin\{figure\}(?:\[[^\]]*\])?(.*?)\\end\{figure\}", re.S)
TAB_RE = re.compile(r"\\begin\{table\}(?:\[[^\]]*\])?(.*?)\\end\{table\}", re.S)
LONGTAB_RE = re.compile(r"\\begin\{longtable\}\{[^}]*\}(.*?)\\end\{longtable\}", re.S)


def equation_body_key(text: str) -> str:
    t = re.sub(r"\\tag\{[^}]+\}", "", text)
    t = re.sub(r"\(\s*\d+(?:\.\d+)*\s*\)\s*$", "", t)
    t = re.sub(r"\\(?:quad|qquad|,|\s)+", "", t)
    t = t.replace("{", "").replace("}", "")
    t = re.sub(r"\^(?:\{([^}]*)\}|(\w))", lambda m: m.group(1) or m.group(2) or "", t)
    return re.sub(r"[^A-Za-z0-9=+\-]", "", t).lower()


def _extract_caption_label(body: str) -> tuple[str | None, str | None]:
    cap = re.search(r"\\caption(?:\[[^\]]+\])?\{([^}]+)\}", body)
    lbl = re.search(r"\\label\{([^}]+)\}", body)
    return (cap.group(1) if cap else None, lbl.group(1) if lbl else None)


def extract_groundtruth_objects(tex: str) -> dict:
    out = {"equations": [], "references": [], "labels": [], "footnotes": [], "headings": [], "figures": [], "tables": [], "bibliography_like": []}
    out["labels"] = [{"label": v} for v in re.findall(r"\\label\{([^}]+)\}", tex)]
    for m in re.finditer(r"\\(?:title|section\*?|subsection\*?|paragraph)\{([^}]+)\}", tex):
        out["headings"].append({"text": m.group(1)})
    for m in EQ_ENV_RE.finditer(tex):
        body = m.group(2)
        tag = re.search(r"\\tag\{\s*(\d+(?:\.\d+)*)\s*\}", body)
        paren = re.search(r"\(\s*(\d+(?:\.\d+)*)\s*\)\s*$", body.strip())
        lbl = re.search(r"\\label\{([^}]+)\}", body)
        out["equations"].append({"object_type": "equation", "label": lbl.group(1) if lbl else None, "numeric_label": (tag or paren).group(1) if (tag or paren) else None, "body_key": equation_body_key(body), "source_environment": m.group(1)})
    for m in DISPLAY_RE.finditer(tex):
        body = m.group(1) or m.group(2) or ""
        out["equations"].append({"object_type": "equation", "label": None, "numeric_label": None, "body_key": equation_body_key(body), "source_environment": "display"})
    for m in REF_CMD_RE.finditer(tex):
        for v in m.group(1).split(","):
            out["references"].append({"label": v.strip(), "source": m.group(0)})
    for m in TEXT_REF_RE.finditer(tex):
        out["references"].append({"label": m.group(1), "source": m.group(0)})
    for m in re.finditer(r"\\footnote\{([^}]+)\}|\\footnotetext\{([^}]+)\}|\\footnotemark", tex):
        if m.group(0) == "\\footnotemark":
            out["footnotes"].append({"text": None, "marker_only": True})
        else:
            out["footnotes"].append({"text": m.group(1) or m.group(2), "marker_only": False})
    for m in FIG_RE.finditer(tex):
        cap, lbl = _extract_caption_label(m.group(1))
        out["figures"].append({"caption": cap, "label": lbl})
    for m in TAB_RE.finditer(tex):
        cap, lbl = _extract_caption_label(m.group(1))
        out["tables"].append({"caption": cap, "label": lbl, "source_environment": "table"})
    for m in LONGTAB_RE.finditer(tex):
        cap, lbl = _extract_caption_label(m.group(1))
        out["tables"].append({"caption": cap, "label": lbl, "source_environment": "longtable"})
    for m in re.finditer(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]|\\(?:cite|citep|citet|citealp)\{([^}]+)\}", tex):
        out["bibliography_like"].append({"source": m.group(0)})
    return out
