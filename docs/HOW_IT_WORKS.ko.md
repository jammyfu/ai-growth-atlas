[English](HOW_IT_WORKS.md) | [简体中文](HOW_IT_WORKS.zh-Hans.md) | [繁體中文](HOW_IT_WORKS.zh-Hant.md) | [日本語](HOW_IT_WORKS.ja.md) | **한국어**

# GitHub Risers 작동 방식

[← 랭킹으로 돌아가기](../README.ko.md)

총 스타 순 목록에서는 오래된 대형 프로젝트가 계속 상위를 차지하고, 지금 뜨는 프로젝트는 묻힙니다. GitHub Risers는 하루 평균 늘어난 스타 수(최근 7·30·365일)로 순위를 매기고 카테고리별로 보여 주며, AI가 메인 랭킹입니다. 각 카테고리는 최근 7일 안에 만들어진 저장소의 신규 랭킹, 주·월·연 증가 랭킹, 마지막으로 총 스타 순입니다. 모든 수치는 GitHub API에서 가져옵니다. 분류 규칙: [docs/CATEGORIES.md](CATEGORIES.md).

하루 두 번 갱신: 베이징 시간 0시(UTC+8)와 로스앤젤레스 시간 0시(America/Los_Angeles, 서머타임 반영). 갱신할 때마다 시간대별로 따로 보관합니다.

README에는 랭킹마다 상위 10개를 싣습니다. 각 랭킹의 상위 20개 전체(70개 수록 프로젝트 기준)는 latest/ 파일에 있습니다.

아래가 최신 순위입니다. 업데이트할 때마다 시간대별로도 저장합니다: [순위 기록](../rankings/README.ko.md) · [latest/rankings.ko.md](../latest/rankings.ko.md).

각 카테고리의 모든 랭킹 1위를 아래 실제 데이터로 스크립트가 자동 생성합니다. '없음'은 이번 실행에서 해당 랭킹에 항목이 없다는 뜻입니다.

## 카테고리

| | |
|---|---|
| AI ★ 메인 | LLM, 에이전트, MCP, 코딩 어시스턴트, 생성형 AI |
| 개발자 도구 | CLI, 에디터, 패키지 관리자, 린터, 빌드 도구 |
| 보안 | 취약점 스캐너, SAST, 공급망·런타임 보안 |
| Web / 프론트엔드 | 프론트엔드 프레임워크, UI 키트, CSS, 브라우저 도구 |
| 인프라 | 컨테이너, Kubernetes, 클라우드, 네트워킹, 관측성 |
| 디자인 / 크리에이티브 | 디자인 시스템, 드로잉, 애니메이션, 크리에이티브 도구 |
| 데이터 | 데이터베이스, 분석, ETL, 데이터 엔지니어링 |

## 7일 이내 신규 인기 저장소 (최근 7일 내 생성)

이 카테고리에서 최근 7일 안에 만들어진 저장소를 GitHub 검색 API(topic 기준: 저장소 자신이 해당 카테고리의 topic을 가져야 함)로 찾아 생성 이후 하루 평균 스타 순으로 줄 세웁니다. 이 카테고리의 다른 랭킹(또는 수록 프로젝트)에 이미 있거나, 앞선 카테고리(AI 우선)에 이미 올라간 저장소는 빼 둡니다. 설명은 저장소 자신의 GitHub 설명; 번역 라이브러리는 [data/translation_library.json](../data/translation_library.json). 규칙: [docs/NEW_ARRIVALS.md](NEW_ARRIVALS.md).

## 숫자는 어떻게 얻나

- 총 스타: `GET /repos/{owner}/{repo}`의 `stargazers_count`.
- 증가 스타: `GET /repos/{owner}/{repo}/stargazers/history` (GitHub가 제공하는 사용자 정보 없는 주간/일간 스타 수). 오늘 이전 N일(UTC, 오늘 제외)의 합이며 스타/일 = 증가 수 ÷ N.
- GitHub는 주/일 구간 경계가 UTC와 일치한다고 보장하지 않으며, 나중에 취소된 스타는 집계되지 않으므로 기간 끝에서 약간의 오차가 있을 수 있습니다.
- 스타 추이 그래프는 `star-history.com`의 SVG 이미지를 URL로 참조합니다. 이 저장소에는 분석·추적 스크립트가 전혀 없습니다.
- 원본 숫자는 [`data/stats.json`](../data/stats.json), 일별 스냅샷은 [`data/stars.json`](../data/stars.json)에 누적됩니다.

## 기여하기

`data/projects.json`에 항목을 추가하고(`category`와 다섯 언어 `desc`), `python tools/update_stars.py`를 실행하세요. 카테고리: [docs/CATEGORIES.md](CATEGORIES.md). 매일 갱신: [docs/DAILY_UPDATE.md](DAILY_UPDATE.md).
