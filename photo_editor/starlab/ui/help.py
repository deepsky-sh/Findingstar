"""Beginner guide and shortcut reference (Korean)."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

GUIDE_HTML = """
<h2>🔭 천체 사진 보정, 이 순서로 해보세요</h2>
<p style='color:#9da3c7'>천체 사진은 일반 사진과 달리 <b>어둡고, 하늘이 물들어 있고, 노이즈가 많습니다.</b>
오른쪽 <b>🌌 천체 필터</b>는 위에서 아래로 이 문제를 순서대로 해결하도록 배치되어 있어요.</p>
<ol>
<li><b>핫픽셀 제거</b> — 장노출 사진에 박힌 빨강·파랑 점을 지웁니다. (20~40)</li>
<li><b>광해 · 그라디언트 제거</b> — 도시 불빛·달빛으로 한쪽이 밝거나 주황색인 하늘을 평평하게.
    성운이 화면을 가득 채우면 <i>복잡도</i>를 1~2로 낮추세요.</li>
<li><b>배경 색 중화 / 별빛 기준 색 보정</b> — 하늘은 무채색 검정, 별은 자연스러운 흰색으로.</li>
<li><b>스트레치</b> — 망원경·스태킹 원본처럼 <b>새까맣게 보이는 사진</b>에 필수!
    희미한 성운과 은하를 끌어올립니다. 일반 카메라 JPG는 보통 필요 없어요.</li>
<li><b>녹색 노이즈 제거 (SCNR)</b> — 우주에 없는 초록 기운 제거.</li>
<li><b>Hα 성운 강조 · 성운 디테일 · 별 크기 줄이기</b> — 대상을 돋보이게 하는 마무리.</li>
<li><b>🔍 디테일 · 노이즈</b> — 색 노이즈 감소 → 노이즈 감소 → 선명하게 순으로 가볍게.</li>
</ol>
<h3>💡 알아두면 좋은 것</h3>
<ul>
<li>왼쪽 <b>원클릭 필터</b>로 출발한 뒤 슬라이더로 다듬으면 가장 빠릅니다.</li>
<li>슬라이더 이름을 <b>더블클릭</b>하면 기본값으로 돌아갑니다. 바뀐 항목은 분홍색으로 표시돼요.</li>
<li><b>◧ 비교</b>를 켜면 원본과 보정본을 나란히 볼 수 있고, <b>👁 원본</b> 버튼을 누르고 있으면 원본이 보입니다.</li>
<li>화면을 <b>100% 이상 확대</b>하면 원본 해상도로 다시 계산해 보여줍니다. 노이즈·별 모양 확인에 좋아요.</li>
<li>편집은 <b>비파괴</b> 방식이라 원본 파일은 절대 바뀌지 않습니다. 저장은 언제나 새 파일로!</li>
<li>여러 장을 찍었다면 <b>🗂 스태킹</b>으로 합쳐서 노이즈를 크게 줄인 뒤 보정하세요.</li>
<li>히스토그램 아래 <b>⚠ 검게 뭉개짐</b> 경고가 크면 블랙 포인트나 대비를 낮추세요.</li>
</ul>
"""

SHORTCUTS_HTML = """
<h2>⌨️ 단축키</h2>
<table cellspacing='0' cellpadding='6'>
<tr><td><b>Ctrl + O</b></td><td>사진 열기</td></tr>
<tr><td><b>Ctrl + S</b></td><td>보정한 사진 저장</td></tr>
<tr><td><b>Ctrl + Z</b></td><td>실행 취소</td></tr>
<tr><td><b>Ctrl + Shift + Z</b> / <b>Ctrl + Y</b></td><td>다시 실행</td></tr>
<tr><td><b>\\</b> (누르고 있기)</td><td>원본 보기</td></tr>
<tr><td><b>C</b></td><td>원본/보정 나란히 비교</td></tr>
<tr><td><b>R</b></td><td>자르기 (Enter 적용 · Esc 취소)</td></tr>
<tr><td><b>Ctrl + 0</b></td><td>화면에 맞추기</td></tr>
<tr><td><b>Ctrl + 1</b></td><td>100% (원본 크기)</td></tr>
<tr><td><b>Ctrl + + / Ctrl + −</b></td><td>확대 / 축소 (마우스 휠도 가능)</td></tr>
<tr><td><b>Ctrl + [ / Ctrl + ]</b></td><td>왼쪽 / 오른쪽으로 90° 회전</td></tr>
<tr><td><b>F1</b></td><td>보정 가이드</td></tr>
<tr><td>사진 <b>더블클릭</b></td><td>화면 맞춤 ↔ 100% 전환</td></tr>
<tr><td>사진 <b>드래그</b></td><td>화면 이동</td></tr>
</table>
"""


def show_html(parent, title: str, html: str) -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.resize(620, 620)
    lay = QVBoxLayout(dlg)
    view = QTextBrowser()
    view.setOpenExternalLinks(True)
    view.setHtml(html)
    lay.addWidget(view)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dlg.reject)
    buttons.button(QDialogButtonBox.StandardButton.Close).setText("닫기")
    lay.addWidget(buttons)
    dlg.exec()
