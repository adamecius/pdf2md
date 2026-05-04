from __future__ import annotations
import re

EQ_ENV_RE = re.compile(r"\\begin\{(equation\*?|align\*?|aligned|gather\*?|multline\*?|eqnarray|split)\}(.*?)\\end\{\1\}", re.S)


def text_key(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (t or "").lower())


def equation_body_key(text: str) -> str:
    t = re.sub(r"\\tag\{[^}]+\}", "", text)
    t = re.sub(r"\(\s*\d+(?:\.\d+)*\s*\)\s*$", "", t)
    t = re.sub(r"\\(?:quad|qquad|,|\s)+", "", t).replace('{', '').replace('}', '')
    t = re.sub(r"\^(?:\{([^}]*)\}|(\w))", lambda m: m.group(1) or m.group(2) or "", t)
    return re.sub(r"[^A-Za-z0-9=+\-]", "", t).lower()


def extract_groundtruth_objects(tex: str, doc_id: str = "doc") -> dict:
    out = {"objects": [], "equations": [], "figures": [], "tables": [], "footnotes": [], "references": []}
    for m in EQ_ENV_RE.finditer(tex):
        body = m.group(2); lbl = re.search(r"\\label\{([^}]+)\}", body); tag = re.search(r"\\tag\{\s*(\d+(?:\.\d+)*)\s*\}", body)
        o = {"gt_id": f"{doc_id}:equation:{lbl.group(1) if lbl else 'unlabeled'}", "doc_id": doc_id, "object_type": "equation", "label": lbl.group(1) if lbl else None, "numeric_label": tag.group(1) if tag else None, "body_key": equation_body_key(body), "canonical_key": equation_body_key(body), "source_text": body, "source_environment": "equation", "required": True}
        out["equations"].append(o); out["objects"].append(o)
    for m in re.finditer(r"\\begin\{figure\}(?:\[[^\]]*\])?(.*?)\\end\{figure\}", tex, re.S):
        b = m.group(1); cap = re.search(r"\\caption(?:\[[^\]]+\])?\{([^}]+)\}", b); lbl = re.search(r"\\label\{([^}]+)\}", b)
        o = {"gt_id": f"{doc_id}:figure:{lbl.group(1) if lbl else 'unlabeled'}", "doc_id": doc_id, "object_type": "figure", "label": lbl.group(1) if lbl else None, "caption": cap.group(1) if cap else None, "caption_key": text_key(cap.group(1) if cap else ''), "placeholder_text": "FIG" if "fbox{FIG}" in b else None, "canonical_key": text_key(cap.group(1) if cap else ''), "source_text": b, "source_environment": "figure", "required": True}
        out["figures"].append(o); out["objects"].append(o)
    for m in re.finditer(r"\\begin\{(table|longtable)\}(?:\[[^\]]*\])?(?:\{[^}]*\})?(.*?)\\end\{\1\}", tex, re.S):
        env,b = m.group(1),m.group(2); cap = re.search(r"\\caption(?:\[[^\]]+\])?\{([^}]+)\}", b); lbl = re.search(r"\\label\{([^}]+)\}", b); cells = re.findall(r"[A-Za-z0-9]+", b)
        o = {"gt_id": f"{doc_id}:table:{lbl.group(1) if lbl else 'unlabeled'}", "doc_id": doc_id, "object_type": "table", "label": lbl.group(1) if lbl else None, "caption": cap.group(1) if cap else None, "caption_key": text_key(cap.group(1) if cap else ''), "cell_texts": cells[:20], "cell_text_key": text_key(''.join(cells[:20])), "canonical_key": text_key((cap.group(1) if cap else '') + ''.join(cells[:4])), "source_text": b, "source_environment": env, "required": True}
        out["tables"].append(o); out["objects"].append(o)
    idx = 1
    for m in re.finditer(r"\\footnote\{([^}]+)\}|\\footnotetext\{([^}]+)\}|\\footnotemark", tex):
        if m.group(0) == "\\footnotemark":
            o = {"gt_id": f"{doc_id}:footnote:{idx}", "doc_id": doc_id, "object_type": "footnote", "text": None, "text_key": "", "expected_marker": str(idx), "canonical_key": "", "source_text": "footnotemark", "required": False}
        else:
            t = m.group(1) or m.group(2)
            o = {"gt_id": f"{doc_id}:footnote:{idx}", "doc_id": doc_id, "object_type": "footnote", "text": t, "text_key": text_key(t), "expected_marker": str(idx), "canonical_key": text_key(t), "source_text": t, "required": True}
        idx += 1
        out["footnotes"].append(o); out["objects"].append(o)
    for m in re.finditer(r"\\(?:ref|autoref|cref|Cref|eqref)\{([^}]+)\}", tex):
        for lab in m.group(1).split(','):
            l = lab.strip(); kind = 'figure' if l.startswith('fig:') else ('table' if l.startswith('tab:') else ('equation' if l.startswith('eq:') else 'section'))
            forms = ['Figure 1', 'Fig. 1'] if kind == 'figure' else (['Table 1'] if kind == 'table' else (['Eq. (1)', 'Equation 1'] if kind == 'equation' else ['Section 1']))
            o = {"gt_id": f"{doc_id}:reference:{l}", "doc_id": doc_id, "object_type": "reference", "label": l, "reference_kind": kind, "expected_rendered_forms": forms, "canonical_key": text_key(forms[0]), "source_text": m.group(0), "required": True}
            out["references"].append(o); out["objects"].append(o)
    return out
