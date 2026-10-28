#!/usr/bin/env python3
"""dashboard.md → dashboard.html 빌더.

사용:   python3 build_dashboard.py <dashboard.md> [-o <출력.html>] [--force]
        출력 경로를 안 주면 같은 폴더에 같은 이름의 .html 을 만든다.
종료:   0 = 빌드함 · 1 = 검사 FAIL 로 멈춤(--force 면 그래도 빌드) · 2 = 파일/인자 오류

빌드 전에 check_diagrams.py 와 같은 검사를 돌린다. 화면 틀은 assets/dashboard.template.html,
AS IS ▶ TO BE 가 있으면 첫 화면(히어로)에 둔다(references/layout.md). 표준 라이브러리만 쓴다.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_diagrams import (  # noqa: E402
    OP_NAMES, SHAPE_NAMES, STRUCT_SHAPES, TAB_NAMES, Doc, View, parse_document, report,
    utf8_stdio,
)

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "dashboard.template.html"

ARROW_SVG = {
    "request": '<line x1="1" y1="5" x2="27" y2="5" stroke="currentColor" stroke-width="1.5"/>',
    "event": '<line x1="1" y1="5" x2="27" y2="5" stroke="currentColor" stroke-width="1.5" stroke-dasharray="4 3"/>',
    "data": '<line x1="1" y1="5" x2="27" y2="5" stroke="currentColor" stroke-width="3.5"/>',
}

esc = html.escape


def inline(text: str) -> str:
    """본문 한 줄 — 이스케이프 뒤 `코드` 와 **굵게** 만 푼다."""
    s = esc(text)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)


def blocks(text: str) -> str:
    """AS IS / TO BE 본문 — 이어진 줄은 한 문단, `- ` 줄은 목록."""
    out: List[str] = []
    para: List[str] = []
    items: List[str] = []

    def flush() -> None:
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
            items.clear()

    for ln in text.split("\n"):
        s = ln.strip()
        m = re.match(r"[-*]\s+(.*)", s)
        if m:
            if para:
                flush()
            items.append(m.group(1))
        elif s:
            if items:
                flush()
            para.append(s)
        else:
            flush()
    flush()
    return "".join(out)


# ── 조각 ─────────────────────────────────────────────────────────────────────

def tabs(doc: Doc) -> str:
    """탭은 차트 이름만(시스템 아키텍처 · 플로우차트 …). 같은 종류가 둘이면 번호를 붙인다."""
    names = [TAB_NAMES[v.kind] for v in doc.views]
    seen: dict = {}
    out = []
    for v, name in zip(doc.views, names):
        seen[name] = seen.get(name, 0) + 1
        label = name if names.count(name) == 1 else f"{name} {seen[name]}"
        out.append(f'<button role="tab" id="tab-{esc(v.id)}" aria-controls="panel-{esc(v.id)}" '
                   f'aria-selected="false" tabindex="-1">{esc(label)}</button>')
    return "".join(out)


# 구조도 카드의 타입 아이콘(24×24, currentColor). 아이콘이 타입을, 굵은 글자가 이름을 말한다
ICONS = {
    "terminal": '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"/>',
    "process": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M7 6.5h.01M10 6.5h.01"/>',
    "predefined": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.2 3 14.8 0 18M12 3c-3 3.2-3 14.8 0 18"/>',
    "db": '<ellipse cx="12" cy="5.5" rx="8" ry="2.8"/><path d="M4 5.5v13c0 1.6 3.6 2.8 8 2.8s8-1.2 8-2.8v-13M4 12c0 1.6 3.6 2.8 8 2.8s8-1.2 8-2.8"/>',
}


def _icon(shape: str) -> str:
    return ('<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS.get(shape, ICONS["process"])}</svg>')


def arch(view: View) -> str:
    """구조도 → 계층 띠 + 카드. 화살표는 화면에서 카드 위치를 재서 그린다(템플릿 drawArch)."""
    titles = dict(view.groups)
    nodes = [n for n in view.nodes.values() if n.shape in STRUCT_SHAPES]
    tiers = [(t, [n for n in nodes if n.group == g]) for g, t in view.groups]
    tiers = [(t, ms) for t, ms in tiers if ms]
    loose = [n for n in nodes if n.group not in titles]
    if loose:
        tiers.append(("기타", loose))
    bands = []
    for ti, (title, members) in enumerate(tiers):
        cards = []
        for n in members:
            name, sep, typ = n.label.partition(" · ")
            cls = f"card shape-{n.shape}" + (" added" if "added" in n.classes else "")
            # 카드는 링크하지 않는다(0.2.0) — 원본의 `click` 줄은 읽기만 하고 화면에 쓰지 않는다
            cards.append(f'<div class="{cls}" data-id="{esc(n.id)}" data-tier="{ti}">{_icon(n.shape)}'
                         f'<span class="nm">{esc(name)}</span>'
                         + (f'<span class="ty">{esc(typ)}</span>' if sep else "")
                         + f'<span class="kd">{STRUCT_SHAPES[n.shape]}</span></div>')
        bands.append(f'<div class="tier"><div class="tier-name">{esc(title)}</div>'
                     f'<div class="tier-cards">{"".join(cards)}</div></div>')
    edges = [{"s": e.src, "t": e.dst, "k": e.kind, "l": e.label} for e in view.edges]
    return (f'<figure class="dia arch" data-edges="{esc(json.dumps(edges, ensure_ascii=False))}">'
            f'<div class="arch-canvas">{"".join(bands)}<svg class="arch-wires" aria-hidden="true"></svg>'
            '<div class="arch-labels"></div></div></figure>')


def legend(view: View) -> str:
    items: List[str] = []
    if view.structural:
        used = {n.shape for n in view.nodes.values()}
        for key, name in STRUCT_SHAPES.items():
            if key in used:
                items.append(f'<span class="it"><span class="lg-card shape-{key}">{_icon(key)}</span>{name}</span>')
        if any("added" in n.classes for n in view.nodes.values()):
            items.append('<span class="it"><span class="lg-card added"></span>새로 넣거나 바꾸는 부분</span>')
        for key, name in OP_NAMES.items():
            if key in {e.kind for e in view.edges}:
                items.append(
                    f'<span class="it"><svg class="ar" viewBox="0 0 34 10" aria-hidden="true">{ARROW_SVG[key]}'
                    f'<path d="M26 1 L33 5 L26 9 Z" fill="currentColor"/></svg>{name} (부르는 쪽 → 받는 쪽)</span>'
                )
    elif view.diagram == "sequence":
        items = [
            f'<span class="it"><svg class="ar" viewBox="0 0 34 10" aria-hidden="true">{ARROW_SVG["request"]}'
            '<path d="M26 1 L33 5 L26 9 Z" fill="currentColor"/></svg>요청</span>',
            f'<span class="it"><svg class="ar" viewBox="0 0 34 10" aria-hidden="true">{ARROW_SVG["event"]}'
            '<path d="M26 1 L33 5 L26 9 Z" fill="currentColor"/></svg>응답</span>',
            '<span class="it"><svg class="ar" viewBox="0 0 34 10" aria-hidden="true">'
            f'{ARROW_SVG["request"]}<path d="M26 1 L33 5 L26 9" fill="none" stroke="currentColor" '
            'stroke-width="1.5"/></svg>비동기</span>',
        ]
    else:
        used = {n.shape for n in view.nodes.values()}
        for key, name in SHAPE_NAMES.items():
            if key in used:
                items.append(f'<span class="it"><span class="sh {key}" aria-hidden="true"></span>{name}</span>')
        kinds = {e.kind for e in view.edges}
        for key, name in OP_NAMES.items():
            if key in kinds:
                items.append(
                    f'<span class="it"><svg class="ar" viewBox="0 0 34 10" aria-hidden="true">{ARROW_SVG[key]}'
                    f'<path d="M26 1 L33 5 L26 9 Z" fill="currentColor"/></svg>{name}</span>'
                )
    return f'<div class="legend" aria-label="범례">{"".join(items)}</div>' if items else ""


CASE_RE = re.compile(r'\*\*(.+?)\*\*\s*(.*?)\s+—\s+"(.+?)"\s*→\s*(.+)$')


def cases(view: View) -> str:
    """`### 예시` → 경로별 사례 카드. `- **A** 경로 — "질문" → 결과` 형식이면 나눠 그리고, 아니면 한 줄로."""
    if not view.examples:
        return ""
    cards = []
    for _, text in view.examples:
        m = CASE_RE.match(text)
        if m:
            badge, path, q, result = m.groups()
            cards.append(f'<li class="case"><p class="path"><span class="badge">{esc(badge)}</span>{inline(path)}</p>'
                         f'<p class="q">“{inline(q)}”</p><p class="r">{inline(result)}</p></li>')
        else:
            cards.append(f'<li class="case"><p class="r">{inline(text)}</p></li>')
    return ('<div class="cases"><h3>예시 — 실제로 이렇게 흘러간다</h3><ul class="case-list">'
            + "".join(cards) + "</ul></div>")


def panels(doc: Doc) -> str:
    out = []
    total = len(doc.views)
    for i, v in enumerate(doc.views, 1):
        # 구조도는 계층 띠 + 카드로 직접 그리고, 흐름도·시퀀스는 Mermaid 로 그린다
        figure = arch(v) if v.structural else (
            f'<figure class="dia"><pre class="mermaid">{esc(v.code.strip())}</pre>\n'
            '        <p class="dia-note" hidden>다이어그램 라이브러리(mermaid.js)를 불러오지 못해 소스를 그대로 보여 줍니다. '
            '인터넷 연결을 확인하세요.</p></figure>')
        # 흐름도에 예시가 있으면 그림은 왼쪽, 경로별 예시는 오른쪽에 나란히 둔다
        ex = cases(v)
        # 패널에 제목 글자는 두지 않는다 — 탭(차트 이름)과 그림이 말한다. 관점 제목은 보조기술용 설명으로만
        aria = f' aria-description="{esc(v.title)}"' if v.title else ""
        body = f'<div class="flow-split">{figure}{ex}</div>' if ex and v.kind == "flow" else figure + ex
        out.append(f"""    <div class="panel" role="tabpanel" id="panel-{esc(v.id)}" aria-labelledby="tab-{esc(v.id)}"{aria} tabindex="0">
      {body}
      {legend(v)}
    </div>""")
    return "\n".join(out)


def asis_tobe(doc: Doc) -> str:
    if not (doc.asis or doc.tobe):
        return ""
    return f"""  <section class="ab-wrap" aria-label="{esc(doc.ab_title)}">
    <div class="ab">
      <section class="as"><h2>AS IS</h2><div class="body">{blocks(doc.asis)}</div></section>
      <section class="to"><h2>TO BE</h2><div class="body">{blocks(doc.tobe)}</div></section>
    </div>
  </section>"""


def compare(doc: Doc) -> str:
    """`## compare` 성능 표 — TO BE 열은 파란 강조, 변화 열은 칩."""
    if not doc.cmp_rows:
        return ""
    head = doc.cmp_head
    kinds = ["tobe" if re.search(r"to\s*-?\s*be", h, re.I) else "asis" if re.search(r"as\s*-?\s*is", h, re.I)
             else "delta" if re.search(r"변화|차이|증감|delta", h, re.I) else "" for h in head]
    th = "".join(f'<th class="{k}">{inline(h)}</th>' for h, k in zip(head, kinds))
    trs = []
    for row in doc.cmp_rows:
        tds = []
        for i, (cell, k) in enumerate(zip(row, kinds)):
            if i == 0:
                tds.append(f'<th scope="row">{inline(cell)}</th>')
            elif k == "delta":
                tds.append(f'<td class="delta"><span class="chip">{inline(cell)}</span></td>')
            else:
                tds.append(f'<td class="{k}">{inline(cell)}</td>')
        trs.append("<tr>" + "".join(tds) + "</tr>")
    src = f'<p class="perf-src">출처: {inline(doc.cmp_source)}</p>' if doc.cmp_source else ""
    return (f'  <section class="perf" aria-label="{esc(doc.cmp_title)}"><h2>{esc(doc.cmp_title)}</h2>'
            f'<div class="tbl"><table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table></div>{src}</section>')


MOVE_KEEP = {"유지", "폐기"}


def move(doc: Doc) -> str:
    """`## move` 이관 안내 — 좌우 대응 지도. 왼쪽 AS IS 카드 ─[이동 방식]▶ 오른쪽 TO BE 카드, 옮기지 않으면 점선 빈 카드."""
    if not doc.move_rows:
        return ""
    head = ('<div class="mv-row mv-head">'
            f'<p class="mv-side as"><span class="tag">AS IS</span>{inline(doc.move_from)}</p><span></span>'
            f'<p class="mv-side to"><span class="tag">TO BE</span>{inline(doc.move_to)}</p></div>')
    rows = []
    for r in doc.move_rows:
        keep = r["kind"] in MOVE_KEEP
        to_cls = "mv-card to" + (" keep" if keep else "")
        to_body = (f'<span class="mv-loc">{inline(r["tobe"])}</span>' if r["tobe"] else "") + \
                  (f'<span class="mv-note">{inline(r["note"])}</span>' if r["note"] else "")
        rows.append('<li class="mv-row">'
                    f'<div class="mv-card as"><span class="mv-item">{inline(r["item"])}</span>'
                    f'<span class="mv-loc">{inline(r["asis"])}</span></div>'
                    f'<div class="mv-link{" keep" if keep else ""}"><span class="mv-kind">{inline(r["kind"])}</span></div>'
                    f'<div class="{to_cls}">{to_body}</div></li>')
    note = f'<p class="perf-src">참고: {inline(doc.move_note)}</p>' if doc.move_note else ""
    return (f'  <section class="move" aria-label="{esc(doc.move_title)}"><h2>{esc(doc.move_title)}</h2>'
            f'{head}<ol class="mv-list">{"".join(rows)}</ol>{note}</section>')


def jira(doc: Doc) -> str:
    """`## jira` — 작업 티켓 목록. 번호는 실제 Jira 링크, Initiative 는 파란 칩."""
    if not doc.jira_items:
        return ""
    rows = []
    for key, url, title, kind in doc.jira_items:
        kd = (f'<span class="kd{" initiative" if kind.lower() == "initiative" else ""}">{esc(kind)}</span>'
              if kind else "<span></span>")
        rows.append(f'<li><a class="key" href="{esc(url)}" target="_blank" rel="noopener">{esc(key)}</a>'
                    f'<span class="tt">{inline(title)}</span>{kd}</li>')
    return f'  <section class="jira" aria-label="{esc(doc.jira_title)}"><h2>{esc(doc.jira_title)}</h2><ul>{"".join(rows)}</ul></section>'


def render(doc: Doc) -> str:
    slots = {
        "TITLE": esc(doc.meta.get("title", doc.path.stem)),
        "TABS": tabs(doc),
        "PANELS": panels(doc),
        "ASISTOBE": asis_tobe(doc),
        "COMPARE": compare(doc),
        "MOVE": move(doc),
        "JIRA": jira(doc),
    }
    page = TEMPLATE.read_text(encoding="utf-8")
    for k, v in slots.items():
        page = page.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{[A-Z]+\}\}", page)
    if left:
        raise SystemExit(f"템플릿 자리 {left} 를 채우지 못했다")
    return page


def main(argv: List[str]) -> int:
    utf8_stdio()
    force = "--force" in argv
    args = [a for a in argv if a != "--force"]
    out: Optional[Path] = None
    if "-o" in args:
        k = args.index("-o")
        if k + 1 >= len(args):
            print(__doc__.strip(), file=sys.stderr)
            return 2
        out = Path(args[k + 1])
        del args[k:k + 2]
    if len(args) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    src = Path(args[0])
    if not src.is_file():
        print(f"파일이 없다: {src}", file=sys.stderr)
        return 2

    doc = parse_document(src)
    print(report(doc))
    if doc.fails and not force:
        print("\nFAIL 이 있어 빌드하지 않았다 — dashboard.md 를 고친 뒤 다시 돌린다 (무시하려면 --force)")
        return 1

    out = out or src.with_suffix(".html")
    out.write_text(render(doc), encoding="utf-8")
    print(f"\n빌드함 → {out.resolve().as_uri()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
