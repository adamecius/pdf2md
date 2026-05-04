from __future__ import annotations
import re

ENV_RE = re.compile(r"\\begin\{(equation\*?|align\*?|aligned|gather\*?|multline\*?|eqnarray|split)\}(.*?)\\end\{\1\}", re.S)
DISPLAY_RE = re.compile(r"\\\[(.*?)\\\]|\$\$(.*?)\$\$", re.S)
CMD_REFS = re.compile(r"\\(?:ref|autoref|cref|Cref|eqref)\{([^}]+)\}")
TEXT_REFS = re.compile(r"\b(?:Figure|Fig\.|Table|Eq\.?|Equation|Section|Sec\.|Chapter)\s*~?\(?\\?ref\{([^}]+)\}\)?")
BIB_RE = re.compile(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]|\\(?:cite|citep|citet|citealp)\{([^}]+)\}")


def equation_body_key(text: str) -> str:
    t = re.sub(r"\\tag\{[^}]+\}", "", text)
    t = re.sub(r"\\(?:quad|,|\s)+", "", t)
    t = t.replace("{", "").replace("}", "")
    t = re.sub(r"\^\{?2\}?", "2", t)
    t = re.sub(r"[^A-Za-z0-9=+-]", "", t).lower()
    return t


def extract_groundtruth_objects(tex: str) -> dict:
    out = {"equations": [], "references": [], "labels": [], "footnotes": [], "headings": [], "figures": [], "tables": [], "bibliography_like": []}
    for m in re.finditer(r"\\(?:title|section\*?|subsection\*?|paragraph)\{([^}]+)\}", tex):
        out["headings"].append({"text": m.group(1)})
    out["labels"] = [{"label": x} for x in re.findall(r"\\label\{([^}]+)\}", tex)]
    for m in ENV_RE.finditer(tex):
        body = m.group(2)
        lbl = re.search(r"\\label\{([^}]+)\}", body)
        tag = re.search(r"\\tag\{\s*(\d+(?:\.\d+)*)\s*\}", body)
        pnum = re.search(r"\(\s*(\d+(?:\.\d+)*)\s*\)\s*$", body.strip())
        out["equations"].append({"object_type": "equation", "label": lbl.group(1) if lbl else None, "numeric_label": (tag or pnum).group(1) if (tag or pnum) else None, "body_key": equation_body_key(body), "source_environment": m.group(1)})
    for m in DISPLAY_RE.finditer(tex):
        body = m.group(1) or m.group(2) or ""
        out["equations"].append({"object_type": "equation", "label": None, "numeric_label": None, "body_key": equation_body_key(body), "source_environment": "display"})
    for m in CMD_REFS.finditer(tex):
        for ref in [x.strip() for x in m.group(1).split(",")]:
            out["references"].append({"label": ref, "source": m.group(0)})
    for m in TEXT_REFS.finditer(tex):
        out["references"].append({"label": m.group(1), "source": m.group(0)})
    for m in re.finditer(r"\\footnote\{([^}]+)\}|\\footnotetext\{([^}]+)\}", tex):
        out["footnotes"].append({"text": m.group(1) or m.group(2)})
    for m in re.finditer(r"\\begin\{figure\}(.*?)\\end\{figure\}", tex, re.S):
        body = m.group(1)
        cap = re.search(r"\\caption(?:\[[^\]]+\])?\{([^}]+)\}", body)
        lbl = re.search(r"\\label\{([^}]+)\}", body)
        out["figures"].append({"caption": cap.group(1) if cap else None, "label": lbl.group(1) if lbl else None})
    for m in re.finditer(r"\\begin\{(?:table|longtable)\}(.*?)\\end\{(?:table|longtable)\}", tex, re.S):
        body = m.group(1)
        cap = re.search(r"\\caption(?:\[[^\]]+\])?\{([^}]+)\}", body)
        lbl = re.search(r"\\label\{([^}]+)\}", body)
        out["tables"].append({"caption": cap.group(1) if cap else None, "label": lbl.group(1) if lbl else None})
    for m in BIB_RE.finditer(tex):
        out["bibliography_like"].append({"source": m.group(0)})
    return out
