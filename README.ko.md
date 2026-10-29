<p align="center">
  <a href="./README.md"><img src="https://img.shields.io/badge/English-30363D?style=for-the-badge" alt="Read in English" /></a>
  <a href="./README.ko.md"><img src="https://img.shields.io/badge/한국어-30363D?style=for-the-badge" alt="한국어로 읽기" /></a>
</p>

# System Dashboard

Codex와 Claude Code에서 쓰는 **시스템 구조 한 장 보기 HTML**입니다.

레포를 가리키면 찾은 구성요소를 근거 파일과 함께 후보로 보여 줍니다. 어떤 관점을 그릴지는 사람이 고릅니다. 그다음 Mermaid 원본을 쓰고, 다이어그램 규칙으로 검사한 뒤, HTML 한 장을 만듭니다. 한 장에는 무엇이 바뀌는지(AS IS ▶ TO BE), 얼마나 달라지는지(행마다 실제 사례가 붙은 성능 표), 시스템이 어떻게 생겼는지(왼쪽→오른쪽 계층 아키텍처), 요청이 어떻게 흐르는지(실제 사례가 옆에 붙은 플로우차트), 어느 티켓의 작업인지가 담깁니다.

<p align="center">
  <a href="#설치"><img src="https://img.shields.io/badge/▶_설치-OPEN-111111?style=for-the-badge&labelColor=5B5B5B" alt="설치" /></a>
  &nbsp;&nbsp;
  <a href="#무엇이-나오나"><img src="https://img.shields.io/badge/▶_결과물-EXPLORE-1F6FEB?style=for-the-badge&labelColor=5B5B5B" alt="결과물 보기" /></a>
</p>

<p align="center">
  <kbd>스킬 1개</kbd>
  <kbd>결과물 HTML 한 장</kbd>
  <kbd>Codex + Claude 지원</kbd>
  <kbd>Python 3.9+, 의존성 없음</kbd>
</p>

## 처음 보는 사람이 읽히는 다이어그램

아키텍처 다이어그램은 늘 비슷하게 실패합니다. 타입만 적힌 상자("DynamoDB"), 어디에도 연결되지 않은 상자, 전부 넣으려다 아무것도 안 읽히는 마스터 다이어그램, 뜻을 합의하지 않은 화살표, 왕복 통신을 한 방향 컨베이어 벨트처럼 그린 그림입니다. 이 스킬은 그 교훈을 스크립트가 판정하는 규칙으로 바꿔, 눈대중이 아니라 매번 같은 기준으로 검사합니다.

무엇을 뺄지는 스킬이 정하지 않습니다. 근거가 달린 후보를 내고, 그릴 관점은 사람이 확정합니다. 코드에서만 뽑은 그림은 빠짐없지만 초점이 없습니다.

## 무엇이 나오나

HTML 파일 한 장이고, 아래 순서로 읽힙니다. 다크·라이트 테마는 시스템 설정을 따릅니다.

| 순서 | 영역 | 내용 |
|---|---|---|
| 1 | AS IS ▶ TO BE | 반반 분할 패널. AS IS는 지금 방식이 무엇에 의존하고 어디서 문제가 되는지, TO BE는 바뀌면 무엇이 가능해지는지를 씁니다. 숫자는 넣지 않습니다 |
| 2 | 성능 비교 표 | 지표 · AS IS · TO BE · 변화, 그리고 선택으로 예시 열. 수치는 전부 여기에 — 어느 기록에서 왔는지는 화면이 아니라 답변으로 알립니다 |
| 2a | 이관 안내 | 프로젝트(레포) 단위로 옮기는 작업일 때만. AS IS 프로젝트 ▶ TO BE 프로젝트 아래에 역할별 좌우 대응 지도 — 흰 카드 ─[포팅·합침·원천 변경…]▶ 파란 카드, 남는 것은 점선 빈 카드 |
| 3 | 탭 | 차트 이름만: 시스템 아키텍처, 플로우차트, 시퀀스 다이어그램, 배포 아키텍처 |
| 3a | 시스템 아키텍처 | 계층을 왼쪽→오른쪽 칸으로, 카드는 타입 아이콘·굵은 이름·타입 글자. 새로 넣거나 바꾸는 부분은 파란 카드. 선은 수평·수직 직선만이고, 카드 하나에서 나가는 선은 한 줄로 나가 대상마다 갈라집니다 |
| 3b | 플로우차트 | 왼쪽에 Mermaid 플로우차트, 오른쪽에 경로별 실제 사례 카드. 배지(A·B·C)로 서로 짝을 맞춥니다 |
| 4 | 작업 Jira | 티켓 번호(트래커 링크) · 타이틀 · 유형. Initiative는 강조 |

화면 제목 머리, KPI 카드, 푸터는 없습니다. 탭과 그림이 말합니다.

## 검사기가 지키는 규칙

`check_diagrams.py`가 원본을 읽고 FAIL(빌드를 막음) 또는 WARN(사람에게 보여 줌)을 냅니다.

- **타입만이 아니라 이름도.** 라벨은 `이름 · 타입`, 예: `Orders Table · PostgreSQL`.
- **연결 없는 상자 금지.** 역할이 드러나는 관점으로 옮기거나 뺍니다.
- **화살표 하나에 뜻 하나.** `-->` 동기 요청, `-.->` 비동기 이벤트, `==>` 데이터 흐름. 머리 없는 선은 FAIL.
- **왕복은 시퀀스 다이어그램으로,** 메시지 브로커는 허브 하나가 아니라 토픽 단위로.
- **도형 어휘가 두 벌.** 플로우차트는 표준 순서도 기호(단말·처리·분기·입출력·정해진 처리·저장소), 아키텍처는 사람·앱/서비스·외부 시스템·저장소. 아키텍처에 순서도 기호를 쓰면 FAIL.
- **플로우차트의 모든 경로에 실제 사례.** 끝 단말에 배지를 달고, 배지마다 로그·테스트·실험·티켓에서 가져온 사례가 있어야 합니다.
- **화면에는 뜻, 출처는 답변으로.** 파일 경로·`파일:줄`·커밋 해시·수용 기준 번호가 화면 글에 있으면 경고합니다. 화면에서 근거로 이어지는 링크는 작업 Jira 절 하나이고, 모든 Jira 키는 자기 `/browse/<KEY>` 주소로 링크.
- **개발 용어는 직역하지 않습니다.** 덮기·점 읽기·발산 같은 직역어 대신 오버레이·포인트 읽기·불일치처럼 현업에서 쓰는 표기로 — 직역어는 읽는 사람이 코드와 이어 읽지 못합니다.
- **구조도는 TO BE 한 장.** 대체될 기존 구성요소를 새 구조와 섞으면 경고하고, 칸이 많아 화면을 넘으면 미리 알립니다.
- **이관 지도는 역할 단위 10쌍 이하,** 이동 방식은 정해진 낱말(포팅·바뀜·합침·원천 변경·새로·유지·폐기)로.

## 설치

### Codex

```bash
codex plugin marketplace add dev-geon/system-dashboard
codex plugin add system-dashboard@system-dashboard
```

설치한 뒤 새 Codex 작업을 시작해야 스킬이 잡힙니다.

### Claude Code

```text
/plugin marketplace add dev-geon/system-dashboard
/plugin install system-dashboard@system-dashboard
```

따로 설정할 것은 없습니다. 스크립트는 Python 표준 라이브러리만 씁니다. 화면은 Mermaid와 Pretendard를 CDN에서 불러오고, 오프라인이면 Mermaid 원본을 보여 주며 그 사실을 화면에 적습니다.

## 사용법

"이 레포 아키텍처 그려줘", "AS IS / TO BE 구조 화면 만들어줘", "이 흐름 플로우차트로 정리해줘" 같은 요청이면 "대시보드"라는 말이 없어도 켜집니다. 진행률·KPI 대시보드는 대상이 아닙니다.

```text
신규 입사 개발자용으로 이 레포 아키텍처를 한 장 대시보드로 그려줘.
주문 API에서 메일 발송을 워커로 떼어 내는 중이야. AS IS / TO BE와
load-test/report-2026-10.json 의 p95 수치, 품절 사례가 들어간 주문 흐름도 넣어줘.
Initiative는 https://example.atlassian.net 의 SHOP-100.
```

순서: 읽을 사람·저장 폴더 확인(개발 레포 밖) → 레포에서 근거 달린 구성요소 후보 → 관점·사례 확정 → `dashboard.md` 작성 → `check_diagrams.py` FAIL 0까지 → `build_dashboard.py` → 화면을 열어 모든 탭 확인.

## 레포 구조

<details>
<summary>플러그인 파일 보기</summary>

```text
.agents/plugins/marketplace.json       # Codex Git 마켓 항목
.codex-plugin/plugin.json              # Codex 플러그인 매니페스트
.claude-plugin/plugin.json             # Claude Code 플러그인 매니페스트
.claude-plugin/marketplace.json        # Claude Code 마켓 항목
skills/system-dashboard/
├── SKILL.md                           # 스킬: 절차, 표기 요약, 하지 않는 것
├── agents/openai.yaml                 # Codex 스킬 메타데이터
├── references/diagram-rules.md        # D1~D9(D8 폐기), P1~P3: 라벨·고아 상자·화살표·왕복·브로커·TO BE 한 장
├── references/symbols.md              # F1~F4 순서도 기호, 아키텍처 도형, 관점 종류
├── references/layout.md               # 화면 배치·토큰·L1~L7 (AS IS/TO BE, 사례, 표, Jira)
├── assets/dashboard.template.html     # 화면 틀: 테마 토큰, 탭, 아키텍처 렌더러
├── assets/dashboard.example.md        # 모든 절이 들어간 시작용 원본
├── scripts/check_diagrams.py          # 검사기: 줄 번호와 FAIL/WARN, FAIL 이면 종료 코드 1
└── scripts/build_dashboard.py         # 빌더: 검사를 다시 돌리고 HTML 을 쓴다
```

</details>

## 출처

- 규칙 D1~D8은 Billy Pilger(Ilograph)의 "More common mistakes to avoid when creating system architecture diagrams"와 HN 토론을 정리한 위키독스 글(박재홍)을 바탕으로 합니다.
- 순서도 기호는 Boardmix가 정리한 ISO 5807 기본 기호를 따릅니다.

## 라이선스

MIT
