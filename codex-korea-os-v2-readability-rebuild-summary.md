# Korea Investment OS v2 Readability Rebuild Summary

## 목적
- 기존 데이터 수집, 점수 계산, 상호작용, 딥링크, 탭 구조는 유지했다.
- 한국 주식 의사결정 영역과 Korea Investment OS v2를 한눈에 읽히는 프리미엄 다크 퍼플 카드형 레이아웃으로 정리했다.
- 확정 매수/매도 지시나 주문 실행 표현은 추가하지 않고, 검토 후보/리스크 관리 중심 문구를 유지했다.

## 주요 변경
- `app.py`에 Korea OS 전용 CSS와 카드/배지/테이블/모바일 스타일을 추가했다.
- Korea Investment OS v2 10개 모듈을 하나의 연결형 보드로 재구성했다.
  - 의사결정 흐름
  - 신호 충돌 매트릭스
  - 포지션 리스크 예산
  - 투자 가설 트래커
  - 예측 검증·캘리브레이션
  - 유사 사례 라이브러리
  - 시나리오 스트레스 테스트
  - 촉매·이벤트 캘린더
  - 리스크 알림 규칙
  - 사후 리뷰 노트
- 팩터 히트맵, 공시·이벤트 레이더, 백테스트 지표 설명 버튼은 접이식 영역으로 이동해 큰 공백을 줄였다.
- 공시, 백테스트, 포트폴리오 큐, 밸류업 레이더에 안전 문구와 동일한 카드 밀도를 적용했다.
- `src/korea_equity/formatting.py`에 상태 한글화, 심각도/국면 표기, 음수 0 보정 포맷을 추가했다.
- `tests/test_korea_os_readability.py`를 추가해 OS v2 UI 토큰, 모듈 연결, 포맷 안정성을 회귀 테스트로 고정했다.

## 검증 결과
- `py -3.11 -m compileall app.py src tests`: 통과
- `py -3.11 -m unittest discover tests`: 79개 테스트 통과
- 로컬 Streamlit `http://127.0.0.1:8501/` 브라우저 확인:
  - Traceback/StreamlitAPIException 없음
  - `Korea Investment OS v2` 표시 확인
  - OS v2 카드 10개 표시 확인
  - 390px 모바일 폭에서 `scrollWidth == clientWidth`, 가로 overflow 없음

## 알려진 제한
- Streamlit의 접힌 사이드바는 모바일에서 화면 왼쪽 바깥에 위치하지만, 문서 가로 스크롤을 만들지는 않는다.
- 이번 작업은 UI/UX 정리 범위이며 기존 투자 알고리즘과 데이터 수집 계산식은 의도적으로 바꾸지 않았다.
