from __future__ import annotations
import re

EQ_ENV_RE = re.compile(r"\\begin\{(equation\*?|align\*?|aligned|gather\*?|multline\*?|eqnarray|split)\}(.*?)\\end\{\1\}", re.S)
DISPLAY_RE = re.compile(r"\\\[(.*?)\\\]|\$\$(.*?)\$\$", re.S)
FIG_RE = re.compile(r"\\begin\{figure\}(?:\[[^\]]*\])?(.*?)\\end\{figure\}", re.S)
TAB_RE = re.compile(r"\\begin\{table\}(?:\[[^\]]*\])?(.*?)\\end\{table\}", re.S)
LONGTAB_RE = re.compile(r"\\begin\{longtable\}\{[^}]*\}(.*?)\\end\{longtable\}", re.S)

def text_key(t:str)->str:return re.sub(r"[^a-z0-9]+","",(t or "").lower())

def equation_body_key(text: str) -> str:
    t = re.sub(r"\\tag\{[^}]+\}", "", text)
    t = re.sub(r"\(\s*\d+(?:\.\d+)*\s*\)\s*$", "", t)
    t = re.sub(r"\\(?:quad|qquad|,|\s)+", "", t).replace('{','').replace('}','')
    t = re.sub(r"\^(?:\{([^}]*)\}|(\w))", lambda m: m.group(1) or m.group(2) or "", t)
    return re.sub(r"[^A-Za-z0-9=+\-]", "", t).lower()

def extract_groundtruth_objects(tex: str) -> dict:
    out={"equations":[],"references":[],"labels":[],"footnotes":[],"headings":[],"figures":[],"tables":[],"bibliography_like":[]}
    out['labels']=[{'label':x} for x in re.findall(r"\\label\{([^}]+)\}",tex)]
    for m in re.finditer(r"\\(?:title|section\*?|subsection\*?|paragraph)\{([^}]+)\}", tex): out['headings'].append({'text':m.group(1)})
    for m in EQ_ENV_RE.finditer(tex):
        body=m.group(2); tag=re.search(r"\\tag\{\s*(\d+(?:\.\d+)*)\s*\}",body); paren=re.search(r"\(\s*(\d+(?:\.\d+)*)\s*\)\s*$",body.strip()); lbl=re.search(r"\\label\{([^}]+)\}",body)
        out['equations'].append({'object_type':'equation','label':lbl.group(1) if lbl else None,'numeric_label':(tag or paren).group(1) if (tag or paren) else None,'body_key':equation_body_key(body),'source_environment':m.group(1),'source_text':body})
    for m in DISPLAY_RE.finditer(tex):
        body=m.group(1) or m.group(2) or ''
        out['equations'].append({'object_type':'equation','label':None,'numeric_label':None,'body_key':equation_body_key(body),'source_environment':'display','source_text':body})
    for m in FIG_RE.finditer(tex):
        b=m.group(1); cap=re.search(r"\\caption(?:\[[^\]]+\])?\{([^}]+)\}",b); lbl=re.search(r"\\label\{([^}]+)\}",b); ph=re.search(r"\\fbox\{([^}]+)\}",b)
        out['figures'].append({'object_type':'figure','label':lbl.group(1) if lbl else None,'caption':cap.group(1) if cap else None,'caption_key':text_key(cap.group(1) if cap else ''),'placeholder_text':ph.group(1) if ph else ('FIG' if 'includegraphics' in b else None),'source_text':b})
    for m in TAB_RE.finditer(tex):
        b=m.group(1); cap=re.search(r"\\caption(?:\[[^\]]+\])?\{([^}]+)\}",b); lbl=re.search(r"\\label\{([^}]+)\}",b); cells=re.findall(r"[A-Za-z0-9]+", re.sub(r"\\[a-zA-Z]+|[&\\]"," ",b))
        out['tables'].append({'object_type':'table','label':lbl.group(1) if lbl else None,'caption':cap.group(1) if cap else None,'caption_key':text_key(cap.group(1) if cap else ''),'cell_texts':cells[:20],'cell_text_key':text_key(''.join(cells[:20])),'source_environment':'table','source_text':b})
    for m in LONGTAB_RE.finditer(tex):
        b=m.group(1); cells=re.findall(r"[A-Za-z0-9]+", re.sub(r"\\[a-zA-Z]+|[&\\]"," ",b))
        out['tables'].append({'object_type':'table','label':None,'caption':None,'caption_key':'','cell_texts':cells[:20],'cell_text_key':text_key(''.join(cells[:20])),'source_environment':'longtable','source_text':b})
    for m in re.finditer(r"\\footnote\{([^}]+)\}|\\footnotetext\{([^}]+)\}|\\footnotemark", tex):
        if m.group(0)=='\\footnotemark': out['footnotes'].append({'object_type':'footnote','text':None,'text_key':'','marker_only':True})
        else:
            t=m.group(1) or m.group(2)
            out['footnotes'].append({'object_type':'footnote','text':t,'text_key':text_key(t),'marker_only':False})
    for m in re.finditer(r"\\(?:ref|autoref|cref|Cref|eqref)\{([^}]+)\}",tex):
        for label in m.group(1).split(','):
            l=label.strip(); kind='figure' if l.startswith('fig:') else ('table' if l.startswith('tab:') else ('equation' if l.startswith('eq:') else ('section' if l.startswith('sec:') else 'unknown')))
            hint='(1)' if m.group(0).startswith('\\eqref') else (('Figure 1' if kind=='figure' else ('Table 1' if kind=='table' else ('Section 1' if kind=='section' else '1'))))
            out['references'].append({'object_type':'reference','label':l,'reference_kind':kind,'source':m.group(0),'rendered_text_hint':hint})
    return out
