#!/usr/bin/env python3
"""dashboard.md 검사기.

references/diagram-rules.md (D1~D8 · P1~P3), references/symbols.md (F1~F4),
references/layout.md (L1 · L3 · L5 · L6 · L7) 의 표대로 판정한다.

사용:   python3 check_diagrams.py <dashboard.md> [--json]
종료:   0 = FAIL 없음 · 1 = FAIL 있음 · 2 = 파일/인자 오류

표준 라이브러리만 쓴다(Python 3.9+). build_dashboard.py 가 parse_document 를 가져다 쓴다.
Mermaid 문법 전체가 아니라 P1 에 적은 부분집합만 읽는다 — 읽지 못한 문법은 조용히 넘기지
않고 P1 FAIL 로 알린다.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── 어휘 ─────────────────────────────────────────────────────────────────────

VIEW_KINDS = {
    "context": "전체 맥락",
    "runtime": "실행 구조",
    "sequence": "시퀀스",
    "flow": "업무 흐름",
    "deploy": "배포",
}
STRUCT_KINDS = {"context", "runtime", "deploy"}
# 탭 이름 — 차트 이름만 쓴다(관점 제목은 패널 안 한 줄 요약)
TAB_NAMES = {
    "context": "시스템 아키텍처",
    "runtime": "시스템 아키텍처",
    "deploy": "배포 아키텍처",
    "sequence": "시퀀스 다이어그램",
    "flow": "플로우차트",
}
# 화면에 그림마다 붙는 "차트 종류 — 무엇을 읽나" 줄. 관점 이름(전체 맥락 등)만으로는 그림의 뜻이 안 읽힌다
CHART_TYPES = {
    "context": ("구조도", "무엇이 있고 무엇과 이어지는지"),
    "runtime": ("구조도", "실행 중에 무엇이 무엇을 호출하는지"),
    "deploy": ("구조도", "무엇이 어디에 배포돼 있는지"),
    "sequence": ("시퀀스 다이어그램", "요청과 응답이 어떤 순서로 오가는지"),
    "flow": ("흐름도(플로우차트)", "일이 어떤 순서로, 어떤 조건에서 갈리는지"),
}
LEVELS = {"context", "container", "component"}
META_KEYS = ["title", "audience", "level", "repo", "ref", "asof"]
MAX_VIEWS = 5
MAX_NODES = 12

# F1 허용 도형 — 이름은 범례에도 쓴다
SHAPE_NAMES = {
    "terminal": "시작·끝",
    "process": "처리",
    "decision": "분기",
    "io": "입출력",
    "predefined": "정해진 처리",
    "db": "저장소",
    "prep": "준비",
    "connector": "연결점",
    "doc": "문서",
}
# 구조도(context·runtime·deploy) 도형 — 순서도 기호가 아니라 C4 식 구성요소 어휘다.
# 같은 Mermaid 괄호를 쓰지만 구조도에서는 뜻이 다르다(symbols.md "구조도 도형")
STRUCT_SHAPES = {
    "terminal": "사람·행위자",       # ([ ])
    "process": "앱·서비스·도구",      # [ ]
    "predefined": "외부 시스템",       # [[ ]]
    "db": "저장소",                  # [( )]
}
# D1 대상 — 이름·타입을 가진 "무엇"인 도형
NAMED_SHAPES = {"process", "db", "predefined", "io", "doc"}

# (여는 기호, 닫는 기호, 도형) — 긴 것부터 맞춘다. 도형이 None 이면 F1 위반
BRACKETS: List[Tuple[str, str, Optional[str]]] = [
    ("(((", ")))", None),
    ("([", "])", "terminal"),
    ("[(", ")]", "db"),
    ("[[", "]]", "predefined"),
    ("[/", "/]", "io"),
    ("[/", "\\]", None),
    ("[\\", "\\]", None),
    ("[\\", "/]", None),
    ("((", "))", "connector"),
    ("{{", "}}", "prep"),
    ("{", "}", "decision"),
    ("[", "]", "process"),
    ("(", ")", None),
    (">", "]", None),
]
# @{ shape: … } 별칭 → 허용 도형
AT_SHAPES = {
    "doc": "doc", "document": "doc",
    "rect": "process", "proc": "process", "process": "process", "rectangle": "process",
    "diam": "decision", "diamond": "decision", "decision": "decision", "question": "decision",
    "cyl": "db", "cylinder": "db", "db": "db", "database": "db",
    "stadium": "terminal", "pill": "terminal", "terminal": "terminal",
    "lean-r": "io", "lean-right": "io", "in-out": "io",
    "subproc": "predefined", "subprocess": "predefined", "subroutine": "predefined",
    "fr-rect": "predefined", "framed-rectangle": "predefined",
    "hex": "prep", "hexagon": "prep", "prepare": "prep",
    "circle": "connector", "circ": "connector",
}

# D4 화살표 — 표기 → 뜻
OP_NAMES = {
    "request": "동기 요청",
    "event": "비동기 이벤트",
    "data": "데이터 흐름",
}

BROKER_RE = re.compile(
    r"kafka|rabbit|sqs|sns|service\s*bus|event\s*hubs?|pub/?sub|nats|eventbridge|\bmq\b|activemq|amqp",
    re.I,
)
TOPIC_RE = re.compile(r"topic|queue|토픽|큐|stream|subscription|exchange", re.I)

EDGE_RE = re.compile(r"\s*(<)?(-\.+->|-{2,}>|={2,}>|-{3,}|-\.+-|={3,})(?:\s*\|([^|]*)\|)?\s*")
NODE_ID_RE = re.compile(r"([A-Za-z0-9_][\w-]*)(.*)", re.S)
EDGE_ID_RE = re.compile(r"\w@(-|=)")
CLICK_RE = re.compile(r'click\s+(\S+)\s+(?:href\s+)?"([^"]+)"(?:\s+"[^"]*")?(?:\s+_\w+)?\s*$')
FC_HEADER_RE = re.compile(r"(flowchart|graph)\s+(TB|TD|LR|BT|RL)\s*;?\s*$")

SEQ_SKIP = re.compile(
    r"(autonumber|activate|deactivate|note|alt|else|opt|loop|par|and|end|rect|critical|"
    r"option|break|box|title|links?|create|destroy)\b",
    re.I,
)
SEQ_PART_RE = re.compile(r"(participant|actor)\s+(\S+?)(?:\s+as\s+(.+))?\s*$")
SEQ_MSG_RE = re.compile(r"([^\s:+-]+?)\s*(-->>|->>|--x|-x|--\)|-\)|-->|->)\s*[+-]?\s*([^\s:+-]+)\s*:(.*)$")


# ── 자료형 ───────────────────────────────────────────────────────────────────

@dataclass
class Finding:
    level: str          # FAIL | WARN
    rule: str
    where: str          # 관점 id 또는 "문서"
    line: int
    msg: str

    def text(self) -> str:
        return f"{self.level:<4} {self.rule:<3} {self.where:<12} L{self.line:<4} {self.msg}"


@dataclass
class Node:
    id: str
    label: str
    shape: Optional[str]    # SHAPE_NAMES 키, F1 위반이면 None, subgraph 면 "subgraph"
    raw: str
    line: int
    defined: bool = False
    group: str = ""                                   # 속한 subgraph(구조도의 계층) id
    classes: List[str] = field(default_factory=list)  # `class a,b added` · `a:::added`


@dataclass
class Edge:
    src: str
    dst: str
    kind: str               # request | event | data | plain
    label: str
    bidir: bool
    line: int


@dataclass
class View:
    id: str
    kind: str               # 숫자 접미사를 뗀 종류
    title: str
    line: int
    intro: str = ""
    code: str = ""
    code_line: int = 0
    diagram: str = ""       # flowchart | sequence
    direction: str = ""
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    links: Dict[str, str] = field(default_factory=dict)
    messages: List[Tuple[str, str, int]] = field(default_factory=list)
    examples: List[Tuple[int, str]] = field(default_factory=list)   # `### 예시` 목록 — (줄, 본문)
    groups: List[Tuple[str, str]] = field(default_factory=list)     # subgraph (id, 제목) — 나온 순서
    cur_group: str = ""

    @property
    def structural(self) -> bool:
        return self.kind in STRUCT_KINDS

    def named_nodes(self) -> List[Node]:
        """D1 대상 — 이름·타입을 가져야 하는 박스."""
        if self.diagram == "sequence":
            return list(self.nodes.values())
        if not self.structural:
            return []
        return [n for n in self.nodes.values() if n.shape in NAMED_SHAPES or n.shape == "terminal"]


@dataclass
class Doc:
    path: Path
    meta: Dict[str, str] = field(default_factory=dict)
    views: List[View] = field(default_factory=list)
    ab_title: str = ""
    cmp_title: str = ""
    cmp_head: List[str] = field(default_factory=list)          # 성능 표 머리 (지표 | AS IS | TO BE | 변화 …)
    cmp_rows: List[List[str]] = field(default_factory=list)
    cmp_source: str = ""                                       # `출처:` 줄
    jira_title: str = ""
    jira_items: List[Tuple[str, str, str, str]] = field(default_factory=list)   # (키, URL, 타이틀, 유형)
    asis: str = ""
    tobe: str = ""
    findings: List[Finding] = field(default_factory=list)

    def add(self, level: str, rule: str, where: str, line: int, msg: str) -> None:
        self.findings.append(Finding(level, rule, where, line, msg))

    @property
    def fails(self) -> int:
        return sum(f.level == "FAIL" for f in self.findings)

    @property
    def warns(self) -> int:
        return sum(f.level == "WARN" for f in self.findings)


# ── 문서 분해 ────────────────────────────────────────────────────────────────

def _blank_comments(text: str) -> str:
    """HTML 주석을 지우되 줄 번호는 지킨다."""
    return re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'`":
        return s[1:-1].strip()
    return s


def _split_top(s: str, sep: str) -> List[str]:
    """따옴표·괄호 밖의 sep 로만 자른다."""
    out, buf, depth, quote = [], [], 0, False
    for c in s:
        if quote:
            buf.append(c)
            quote = c != '"'
            continue
        if c == '"':
            quote = True
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth = max(depth - 1, 0)
        elif c == sep and depth == 0:
            out.append("".join(buf))
            buf = []
            continue
        buf.append(c)
    out.append("".join(buf))
    return out


def _split_chain(s: str) -> Tuple[List[str], List[re.Match]]:
    """`A -->|x| B --> C` → (['A', 'B', 'C'], [edge, edge]). 따옴표·괄호 안의 화살표는 무시."""
    parts, ops, buf = [], [], []
    i, depth, quote = 0, 0, False
    while i < len(s):
        c = s[i]
        if quote:
            buf.append(c)
            quote = c != '"'
            i += 1
            continue
        if depth == 0:
            m = EDGE_RE.match(s, i)
            if m and m.group(2):
                parts.append("".join(buf))
                ops.append(m)
                buf = []
                i = m.end()
                continue
        if c == '"':
            quote = True
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth = max(depth - 1, 0)
        buf.append(c)
        i += 1
    parts.append("".join(buf))
    return parts, ops


def _edge_kind(op: str) -> str:
    if not op.endswith(">"):
        return "plain"
    if "." in op:
        return "event"
    if op.startswith("="):
        return "data"
    return "request"


def parse_front_matter(lines: List[str], doc: Doc) -> int:
    """머리말을 읽고 본문이 시작하는 줄 번호(0 기준)를 돌려준다."""
    if not lines or lines[0].strip() != "---":
        doc.add("FAIL", "D7", "문서", 1, "머리말(---)이 없다 — title·audience·level·repo·ref·asof 를 적는다")
        return 0
    for i in range(1, len(lines)):
        raw = lines[i]
        if raw.strip() == "---":
            body_start = i + 1
            break
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        k, sep, v = raw.partition(":")
        if sep:
            v = re.sub(r"\s+#.*$", "", v)
            doc.meta[k.strip()] = _unquote(v)
    else:
        doc.add("FAIL", "D7", "문서", 1, "머리말이 닫히지 않았다(---)")
        return len(lines)

    for k in META_KEYS:
        if not doc.meta.get(k):
            doc.add("FAIL", "D7", "문서", 1, f"머리말에 `{k}` 가 없다")
    lv = doc.meta.get("level")
    if lv and lv not in LEVELS:
        doc.add("FAIL", "D7", "문서", 1, f"level `{lv}` — context · container · component 중 하나")

    return body_start


def parse_document(path: Path) -> Doc:
    doc = Doc(path=path)
    lines = _blank_comments(path.read_text(encoding="utf-8")).split("\n")
    start = parse_front_matter(lines, doc)

    # `## ` 절로 자른다 (코드 블록 안의 ## 는 건너뛴다)
    sections: List[Tuple[int, str, List[Tuple[int, str]]]] = []
    in_fence = False
    for i in range(start, len(lines)):
        ln = lines[i]
        if ln.strip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and ln.startswith("## "):
            sections.append((i + 1, ln[3:].strip(), []))
        elif sections:
            sections[-1][2].append((i + 1, ln))

    seen = set()
    for lineno, head, body in sections:
        m = re.match(r"view:\s*([\w-]+)\s*(?:\|\s*(.*))?$", head)
        if m:
            vid, title = m.group(1), (m.group(2) or "").strip()
            km = re.fullmatch(r"(context|runtime|sequence|flow|deploy)(-\d+)?", vid)
            if not km:
                doc.add("FAIL", "P2", vid, lineno, f"관점 종류 `{vid}` — {' · '.join(VIEW_KINDS)} (같은 종류 두 번은 `-2`)")
                continue
            if vid in seen:
                doc.add("FAIL", "P2", vid, lineno, "같은 관점 id 가 두 번 나온다")
                continue
            seen.add(vid)
            view = View(id=vid, kind=km.group(1), title=title, line=lineno)
            _read_view_body(view, body, doc)
            doc.views.append(view)
        elif re.match(r"jira\b", head):
            doc.jira_title = head.partition("|")[2].strip() or "작업 Jira"
            _read_jira(lineno, body, doc)
        elif re.match(r"compare\b", head):
            doc.cmp_title = head.partition("|")[2].strip() or "AS IS ▶ TO BE 성능 비교"
            _read_compare(lineno, body, doc)
        elif re.match(r"asis-tobe\b", head):
            doc.ab_title = head.partition("|")[2].strip() or "AS IS ▶ TO BE"
            _read_asis_tobe(lineno, body, doc)
        else:
            doc.add("WARN", "P2", "문서", lineno, f"알 수 없는 절 `## {head}` — 화면에 나오지 않는다")

    if not doc.views:
        doc.add("FAIL", "P2", "문서", start + 1, "관점(`## view: <종류> | <제목>`)이 하나도 없다")
    if len(doc.views) > MAX_VIEWS:
        doc.add("FAIL", "P2", "문서", doc.views[MAX_VIEWS].line,
                f"관점이 {len(doc.views)}개 — {MAX_VIEWS}개 이하로 고른다")

    for v in doc.views:
        if v.code:
            check_view(v, doc)
    return doc


def _read_view_body(view: View, body: List[Tuple[int, str]], doc: Doc) -> None:
    blocks: List[Tuple[int, List[str]]] = []
    intro: List[str] = []
    cur: Optional[List[str]] = None
    in_examples = False
    for lineno, ln in body:
        s = ln.strip()
        if cur is None and re.match(r"###\s+예시\s*$", s):
            in_examples = True
        elif cur is None and in_examples:
            item = re.match(r"[-*]\s+(\S.*)", s)
            if item:
                view.examples.append((lineno, item.group(1).strip()))
        elif cur is None and re.match(r"```\s*mermaid\s*$", s):
            cur = []
            blocks.append((lineno + 1, cur))
        elif cur is not None and s.startswith("```"):
            cur = None
        elif cur is not None:
            cur.append(ln)
        elif s and not blocks:
            intro.append(s)
    view.intro = " ".join(intro)
    if view.intro:
        doc.add("WARN", "L5", view.id, view.line,
                "관점 아래 설명 문단은 화면에 나오지 않는다 — 그림이 말하게 하고, 안내는 관점 제목 한 줄로")
    if len(blocks) != 1:
        doc.add("FAIL", "P2", view.id, view.line, f"mermaid 블록이 {len(blocks)}개 — 관점마다 정확히 1개")
    if blocks:
        view.code_line, code_lines = blocks[0]
        view.code = "\n".join(code_lines)


def _read_asis_tobe(lineno: int, body: List[Tuple[int, str]], doc: Doc) -> None:
    parts: Dict[str, List[str]] = {}
    cur = None
    for _, ln in body:
        m = re.match(r"###\s+(AS[\s-]*IS|TO[\s-]*BE)\s*$", ln.strip(), re.I)
        if m:
            cur = "asis" if m.group(1).upper().startswith("AS") else "tobe"
            parts[cur] = []
        elif cur and ln.strip():
            parts[cur].append(ln.rstrip())
    for key, name in (("asis", "AS IS"), ("tobe", "TO BE")):
        if key not in parts:
            doc.add("FAIL", "P2", "asis-tobe", lineno, f"`### {name}` 소절이 없다")
            continue
        text = "\n".join(parts[key])
        setattr(doc, key, text)
        chars = len(re.sub(r"\s", "", text))
        if len(parts[key]) > 4 or chars > 200:
            doc.add("WARN", "L1", "asis-tobe", lineno,
                    f"{name}: {len(parts[key])}줄 · {chars}자 — 4줄·200자 이내로 줄인다")
        if re.search(r"\d", text):
            doc.add("WARN", "L1", "asis-tobe", lineno,
                    f"{name} 에 숫자가 있다 — 성능 수치는 `## compare` 표로 옮기고 여기는 무엇이 달라지는지만 쓴다")


JIRA_ITEM_RE = re.compile(r"[-*]\s+\[([A-Z][A-Z0-9]+-\d+)\]\((https?://[^)\s]+)\)\s+(.+?)(?:\s+—\s+([^—]+))?$")


def _read_jira(lineno: int, body: List[Tuple[int, str]], doc: Doc) -> None:
    """`## jira` — `- [KEY-123](https://…/browse/KEY-123) 타이틀 — 유형` 목록."""
    for ln_no, ln in body:
        t = ln.strip()
        if not re.match(r"[-*]\s+", t):
            continue
        m = JIRA_ITEM_RE.fullmatch(t)
        if not m:
            doc.add("WARN", "L7", "jira", ln_no, f"`{t}` — `- [KEY-123](https://…/browse/KEY-123) 타이틀 — 유형` 형식으로")
            continue
        key, url, title, kind = m.group(1), m.group(2), m.group(3).strip(), (m.group(4) or "").strip()
        if not url.rstrip("/").endswith("/browse/" + key):
            doc.add("WARN", "L7", "jira", ln_no, f"`{key}` 링크 `{url}` 가 그 티켓 주소(…/browse/{key})가 아니다")
        doc.jira_items.append((key, url, title, kind))
    if not doc.jira_items:
        doc.add("WARN", "L7", "jira", lineno, "작업 Jira 절에 티켓이 없다")


def _read_compare(lineno: int, body: List[Tuple[int, str]], doc: Doc) -> None:
    """`## compare` — 파이프 표 하나 + `출처:` 줄."""
    rows: List[List[str]] = []
    for ln_no, ln in body:
        t = ln.strip()
        if t.startswith("|"):
            cells = [c.strip() for c in t.strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                continue
            rows.append(cells)
        elif re.match(r"출처\s*[:：]", t):
            doc.cmp_source = re.sub(r"^출처\s*[:：]\s*", "", t)
    if len(rows) < 2:
        doc.add("FAIL", "P2", "compare", lineno, "성능 표가 없다 — 머리줄 + 1줄 이상의 `| 지표 | AS IS | TO BE | 변화 |` 표")
        return
    head, data = rows[0], rows[1:]
    for r in data:
        if len(r) != len(head):
            doc.add("FAIL", "P2", "compare", lineno, f"표 열 수가 다르다 — 머리 {len(head)}칸, `{' | '.join(r)}` {len(r)}칸")
            return
    doc.cmp_head, doc.cmp_rows = head, data
    if not doc.cmp_source:
        doc.add("WARN", "L6", "compare", lineno, "성능 표 아래 `출처: <파일·날짜·조건>` 줄이 없다 — 수치는 출처와 함께")


# ── Mermaid 읽기 ─────────────────────────────────────────────────────────────

def _parse_node(expr: str, view: View, lineno: int, doc: Doc) -> Optional[str]:
    expr = expr.strip()
    cls_m = re.search(r":::([\w-]+)\s*$", expr)
    expr = re.sub(r":::[\w-]+\s*$", "", expr)
    m = NODE_ID_RE.fullmatch(expr)
    if not m:
        doc.add("FAIL", "P1", view.id, lineno,
                f"읽을 수 없는 노드 `{expr}` — 화살표 라벨은 `-->|라벨|` 형식만 쓴다")
        return None
    nid, rest = m.group(1), m.group(2).strip()
    if not rest:
        node = view.nodes.setdefault(nid, Node(nid, nid, "process", nid, lineno))
        if cls_m:
            node.classes.append(cls_m.group(1))
        return nid

    shape: Optional[str] = None
    label = ""
    if rest.startswith("@{") and rest.endswith("}"):
        inner = rest[2:-1]
        sm = re.search(r"shape\s*:\s*([\w-]+)", inner)
        lm = re.search(r'label\s*:\s*"([^"]*)"', inner)
        shape = AT_SHAPES.get(sm.group(1).lower()) if sm else "process"
        label = lm.group(1).strip() if lm else nid
    else:
        for op, cl, sh in BRACKETS:
            if rest.startswith(op) and rest.endswith(cl) and len(rest) >= len(op) + len(cl):
                shape, label = sh, _unquote(rest[len(op):len(rest) - len(cl)])
                break
        else:
            hint = " — 화살표 라벨은 `-->|라벨|` 형식만 쓴다" if rest[:1] in "-=." else ""
            doc.add("FAIL", "P1", view.id, lineno, f"읽을 수 없는 노드 모양 `{expr}`{hint}")
            return None

    prev = view.nodes.get(nid)
    view.nodes[nid] = Node(nid, label or nid, shape, rest, lineno, defined=True,
                           group=view.cur_group or (prev.group if prev else ""),
                           classes=(prev.classes if prev else []) + ([cls_m.group(1)] if cls_m else []))
    if shape is None:
        doc.add("FAIL", "F1", view.id, lineno,
                f"`{nid}{rest}` — 허용 목록 밖 도형 (references/symbols.md F1)")
    return nid


def _parse_flowchart(view: View, lines: List[str], doc: Doc) -> None:
    subgraphs = set()
    stack: List[str] = []
    pending_classes: Dict[str, List[str]] = {}
    for off, raw in enumerate(lines):
        lineno = view.code_line + off
        for stmt in _split_top(raw, ";"):
            s = stmt.strip()
            if not s or s.startswith("%%"):
                continue
            head = s.split(None, 1)[0]
            if s == "end":
                stack = stack[:-1]
                view.cur_group = stack[-1] if stack else ""
                continue
            if head == "class":
                cm = re.match(r"class\s+([\w,\s-]+?)\s+([\w-]+)\s*;?$", s)
                if cm:
                    for nid in [x.strip() for x in cm.group(1).split(",") if x.strip()]:
                        pending_classes.setdefault(nid, []).append(cm.group(2))
                continue
            if head in ("classDef", "style", "linkStyle", "direction"):
                continue
            if head == "subgraph":
                sm = re.match(r'subgraph\s+([\w-]+)(?:\s*\[\s*"?(.*?)"?\s*\])?\s*$', s)
                if sm:
                    subgraphs.add(sm.group(1))
                    view.groups.append((sm.group(1), (sm.group(2) or sm.group(1)).strip()))
                    stack.append(sm.group(1))
                    view.cur_group = sm.group(1)
                else:
                    doc.add("FAIL", "P1", view.id, lineno, f'`{s}` — `subgraph id["제목"]` 형식만 쓴다')
                continue
            if head == "click":
                cm = CLICK_RE.match(s)
                if cm:
                    view.links[cm.group(1)] = cm.group(2)
                else:
                    doc.add("FAIL", "P1", view.id, lineno, f'`{s}` — `click id "URL"` 형식만 쓴다(콜백 금지)')
                continue
            if EDGE_ID_RE.search(s):
                doc.add("FAIL", "P1", view.id, lineno, "화살표 ID 문법(`e1@-->`)은 쓰지 않는다")
                continue

            parts, ops = _split_chain(s)
            groups: List[List[str]] = []
            for p in parts:
                ids = [_parse_node(x, view, lineno, doc) for x in _split_top(p, "&")]
                groups.append([i for i in ids if i])
            for k, m in enumerate(ops):
                kind = _edge_kind(m.group(2))
                label = _unquote(m.group(3) or "")
                for a in groups[k]:
                    for b in groups[k + 1]:
                        view.edges.append(Edge(a, b, kind, label, bool(m.group(1)), lineno))

    for sg in subgraphs:
        if sg in view.nodes and not view.nodes[sg].defined:
            view.nodes[sg].shape = "subgraph"
    for nid, cls in pending_classes.items():
        if nid in view.nodes:
            view.nodes[nid].classes.extend(cls)


def _parse_sequence(view: View, lines: List[str], doc: Doc) -> None:
    for off, raw in enumerate(lines):
        lineno = view.code_line + off
        s = raw.strip()
        if not s or s.startswith("%%"):
            continue
        pm = SEQ_PART_RE.fullmatch(s)
        if pm:
            pid = pm.group(2)
            view.nodes[pid] = Node(pid, _unquote(pm.group(3) or pid), "participant", s, lineno, defined=True)
            continue
        mm = SEQ_MSG_RE.fullmatch(s)
        if mm:
            a, b = mm.group(1), mm.group(3)
            for pid in (a, b):
                view.nodes.setdefault(pid, Node(pid, pid, "participant", pid, lineno))
            view.messages.append((a, b, lineno))
            continue
        if SEQ_SKIP.match(s):
            continue
        doc.add("FAIL", "P1", view.id, lineno, f"읽을 수 없는 시퀀스 문장 `{s}`")


# ── 판정 ─────────────────────────────────────────────────────────────────────

def check_view(view: View, doc: Doc) -> None:
    lines = view.code.split("\n")
    first = next((i for i, l in enumerate(lines) if l.strip() and not l.strip().startswith("%%")), None)
    if first is None:
        doc.add("FAIL", "P2", view.id, view.code_line, "mermaid 블록이 비어 있다")
        return
    header = lines[first].strip()
    body = [""] * (first + 1) + lines[first + 1:]   # 줄 번호를 맞추려고 앞을 빈 줄로 채운다

    if re.search(r"animate", view.code, re.I):
        doc.add("FAIL", "P3", view.id, view.code_line, "애니메이션(`animate`)은 쓰지 않는다")

    fm = FC_HEADER_RE.fullmatch(header)
    if header.startswith("sequenceDiagram"):
        view.diagram = "sequence"
        if view.kind != "sequence":
            doc.add("FAIL", "P2", view.id, view.code_line + first, f"`{view.kind}` 관점에 sequenceDiagram — flowchart 를 쓴다")
        _parse_sequence(view, body, doc)
        _check_sequence(view, doc)
        return
    if not fm:
        doc.add("FAIL", "P1", view.id, view.code_line + first,
                f"`{header}` — `flowchart TB|LR` 또는 `sequenceDiagram` 만 쓴다")
        return
    view.diagram, view.direction = "flowchart", fm.group(2)
    if view.kind == "sequence":
        doc.add("FAIL", "P2", view.id, view.code_line + first, "sequence 관점은 sequenceDiagram 으로 그린다")
    if view.direction in ("BT", "RL"):
        doc.add("FAIL", "F2", view.id, view.code_line + first,
                f"방향 `{view.direction}` — 위→아래(TB) 또는 왼→오른쪽(LR)만")
    _parse_flowchart(view, body, doc)
    _check_flowchart(view, doc)


def _check_sequence(view: View, doc: Doc) -> None:
    talked = {p for a, b, _ in view.messages for p in (a, b)}
    for n in view.nodes.values():
        if not n.defined:
            doc.add("FAIL", "D1", view.id, n.line,
                    f"`{n.id}` — `participant {n.id} as 이름 · 타입` 으로 먼저 선언한다")
        elif not _has_name_type(n.label):
            doc.add("FAIL", "D1", view.id, n.line, f"`{n.label}` — 라벨은 `이름 · 타입`")
        if n.id not in talked:
            doc.add("FAIL", "D2", view.id, n.line, f"`{n.label}` — 주고받는 메시지가 없다")
    if len(view.nodes) > MAX_NODES:
        doc.add("WARN", "D3", view.id, view.line, f"참여자 {len(view.nodes)}개 — {MAX_NODES}개 이하로 나눈다")


def _has_name_type(label: str) -> bool:
    name, sep, typ = label.partition(" · ")
    return bool(sep and name.strip() and typ.strip())


def _check_flowchart(view: View, doc: Doc) -> None:
    nodes = {k: n for k, n in view.nodes.items() if n.shape != "subgraph"}
    deg_in: Dict[str, int] = {k: 0 for k in nodes}
    deg_out: Dict[str, int] = {k: 0 for k in nodes}
    for e in view.edges:
        if e.src in deg_out:
            deg_out[e.src] += 1
        if e.dst in deg_in:
            deg_in[e.dst] += 1

    # F1(구조도) — 순서도 기호(분기·입출력·준비·연결점·문서)는 구조도에 쓰지 않는다
    if view.structural:
        for k, n in nodes.items():
            if n.shape and n.shape not in STRUCT_SHAPES:
                doc.add("FAIL", "F1", view.id, n.line,
                        f"`{n.label}` — 구조도에는 {SHAPE_NAMES.get(n.shape, n.shape)} 기호를 쓰지 않는다. "
                        "사람 `([ ])` · 앱·서비스·도구 `[ ]` · 외부 시스템 `[[ ]]` · 저장소 `[( )]` 만")
        # L4 — 구조도 박스는 계층(subgraph) 안에 둔다. 화면이 계층을 띠로 그린다
        for k, n in nodes.items():
            if not n.group:
                doc.add("WARN", "L4", view.id, n.line,
                        f"`{n.label}` 이 계층 밖에 있다 — `subgraph id[\"계층 이름\"]` 안에 둔다")
    # D1
    for n in view.named_nodes():
        if not _has_name_type(n.label):
            doc.add("FAIL", "D1", view.id, n.line, f"`{n.label}` — 라벨은 `이름 · 타입` (예: Orders Table · PostgreSQL)")
    # D2
    for k, n in nodes.items():
        if deg_in[k] + deg_out[k] == 0:
            doc.add("FAIL", "D2", view.id, n.line,
                    f"`{n.label}` — 들고 나는 화살표가 없다. 역할이 드러나는 관점으로 옮기거나 뺀다")
    # D3
    if len(nodes) > MAX_NODES:
        doc.add("WARN", "D3", view.id, view.line,
                f"박스 {len(nodes)}개 — {MAX_NODES}개 이하로 관점을 쪼개거나 추상화 수준을 올린다")
    # D4 · D5
    pairs = set()
    for e in view.edges:
        if e.kind == "plain":
            doc.add("FAIL", "D4", view.id, e.line,
                    f"`{e.src}`–`{e.dst}` 머리 없는 선 — `-->` 요청 · `-.->` 이벤트 · `==>` 데이터 중 하나")
            continue
        if view.structural and not e.label:
            doc.add("WARN", "D4", view.id, e.line, f"`{e.src}` → `{e.dst}` 라벨 없음 — 무엇을 요청/발행하는지 적는다")
        if view.kind == "flow" and e.kind != "request":
            doc.add("WARN", "D4", view.id, e.line, "흐름도의 화살표는 진행 순서 `-->` 하나만 쓴다")
        if view.structural:
            if e.bidir:
                doc.add("WARN", "D5", view.id, e.line,
                        f"`{e.src}` ↔ `{e.dst}` 양방향 — 왕복이 중요하면 sequence 관점으로 그린다")
            pairs.add((e.src, e.dst))
    if view.structural:
        warned = set()
        for a, b in pairs:
            if (b, a) in pairs and frozenset((a, b)) not in warned:
                warned.add(frozenset((a, b)))
                doc.add("WARN", "D5", view.id, view.line,
                        f"`{a}` ⇄ `{b}` 양쪽 화살표 — 왕복이 중요하면 sequence 관점으로 그린다")
    # D6
    if view.structural:
        for k, n in nodes.items():
            name, _, typ = n.label.partition(" · ")
            if BROKER_RE.search(typ or name) and not TOPIC_RE.search(name) and deg_in[k] + deg_out[k] >= 3:
                doc.add("WARN", "D6", view.id, n.line,
                        f"`{n.label}` 에 연결 {deg_in[k] + deg_out[k]}개 — 브로커 대신 토픽(큐)을 박스로 그린다")
    # D8 — context 수준은 사람·외부 시스템 박스라 링크할 코드가 없으므로 비율은 보지 않는다
    if view.structural and doc.meta.get("level") != "context":
        targets = view.named_nodes()
        linked = [n for n in targets if n.id in view.links]
        if targets and len(linked) / len(targets) < 0.5:
            doc.add("WARN", "D8", view.id, view.line,
                    f"코드 링크 {len(linked)}/{len(targets)} — 박스마다 `click id \"레포 URL\"` 을 단다")
    for nid, url in view.links.items():
        if nid not in nodes:
            doc.add("WARN", "D8", view.id, view.line, f"click 대상 `{nid}` 가 이 관점에 없다")
        elif not url.startswith(("http://", "https://")):
            doc.add("WARN", "D8", view.id, view.line, f"`{nid}` 링크 `{url}` — 레포 URL(https://…)로 단다")
    # F3
    for k, n in nodes.items():
        if n.shape != "decision":
            continue
        outs = [e for e in view.edges if e.src == k]
        if len(outs) < 2:
            doc.add("FAIL", "F3", view.id, n.line, f"분기 `{n.label}` 의 출구가 {len(outs)}개 — 2개 이상")
        if any(not e.label for e in outs):
            doc.add("FAIL", "F3", view.id, n.line, f"분기 `{n.label}` 에 라벨 없는 출구 — `-->|예|` 처럼 적는다")
    # L3 — 흐름도는 끝 단말(경로)마다 실제 사례를 붙인다. 단말 라벨 `A · …` 의 배지와 예시 `**A**` 를 맞춘다
    if view.kind == "flow":
        ends = [n for k, n in nodes.items() if n.shape == "terminal" and deg_out[k] == 0 and deg_in[k] > 0]
        badges = {m.group(1) for n in ends for m in [re.match(r"(\S{1,3})\s·\s", n.label)] if m}
        ex_badges = {m.group(1).strip() for _, t in view.examples for m in [re.match(r"\*\*(.+?)\*\*", t)] if m}
        if not view.examples:
            doc.add("WARN", "L3", view.id, view.line,
                    "흐름도에 `### 예시` 가 없다 — 경로마다 실제 질문·사례 하나씩 붙이면 읽기 쉽다")
        for b in sorted(badges - ex_badges):
            doc.add("WARN", "L3", view.id, view.line, f"끝 단말 `{b}` 경로의 예시가 없다 — `- **{b}** <경로> — \"<사례>\" → <결과>`")
    # F4
    if view.kind == "flow":
        terms = [k for k, n in nodes.items() if n.shape == "terminal"]
        if not any(deg_in[k] == 0 and deg_out[k] > 0 for k in terms):
            doc.add("FAIL", "F4", view.id, view.line, "시작 단말 `([ ])` 이 없다 — 나가는 화살표만 있는 단말")
        if not any(deg_out[k] == 0 and deg_in[k] > 0 for k in terms):
            doc.add("FAIL", "F4", view.id, view.line, "끝 단말 `([ ])` 이 없다 — 들어오는 화살표만 있는 단말")


# ── 실행 ─────────────────────────────────────────────────────────────────────

def report(doc: Doc) -> str:
    out = [f.text() for f in sorted(doc.findings, key=lambda f: (f.level != "FAIL", f.line))]
    out.append(f"\n{doc.path.name}: 관점 {len(doc.views)}개 · FAIL {doc.fails} · WARN {doc.warns}")
    return "\n".join(out)


def main(argv: List[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"파일이 없다: {path}", file=sys.stderr)
        return 2
    doc = parse_document(path)
    if "--json" in argv:
        print(json.dumps({"file": str(path), "fail": doc.fails, "warn": doc.warns,
                          "findings": [f.__dict__ for f in doc.findings]}, ensure_ascii=False, indent=2))
    else:
        print(report(doc))
    return 1 if doc.fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
