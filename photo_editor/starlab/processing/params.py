"""Every adjustable setting in one table.

The UI builds its sliders from PARAM_SPECS, the pipeline reads DEFAULTS, and
presets override a subset of keys. Adding a new filter means adding a row here
and a step in pipeline.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParamSpec:
    key: str
    label: str
    section: str
    minimum: float = 0
    maximum: float = 100
    default: float = 0
    step: float = 1
    suffix: str = ""
    tooltip: str = ""
    choices: tuple[tuple[str, str], ...] = field(default=())  # (value, label) for combo boxes

    @property
    def is_choice(self) -> bool:
        return bool(self.choices)

    @property
    def decimals(self) -> int:
        return 0 if float(self.step).is_integer() else len(str(self.step).split(".")[1])


SECTIONS: list[tuple[str, str]] = [
    ("astro", "🌌  천체 필터"),
    ("tone", "☀️  밝기 · 톤"),
    ("color", "🎨  색상"),
    ("detail", "🔍  디테일 · 노이즈"),
]

STRETCH_CHOICES = (
    ("none", "사용 안 함"),
    ("auto", "자동 스트레치 (STF)"),
    ("asinh", "아크사인 (별 색 보존)"),
)

PARAM_SPECS: list[ParamSpec] = [
    # ── 천체 필터 (파이프라인 순서대로) ─────────────────────────────
    ParamSpec("hotpixel", "핫픽셀 제거", "astro",
              tooltip="센서의 고장 난 화소(주변보다 튀는 한 점)를 찾아 지웁니다.\n장노출 사진의 빨강·파랑 점 제거에 좋아요."),
    ParamSpec("vignette", "비네팅 보정", "astro", -100, 100,
              tooltip="렌즈 때문에 어두워진 모서리를 밝게 되살립니다.\n음수로 두면 반대로 모서리를 어둡게 합니다."),
    ParamSpec("bg_remove", "광해 · 그라디언트 제거", "astro",
              tooltip="도시 불빛이나 달빛 때문에 한쪽이 밝거나 주황색으로 뜬 하늘을\n자동으로 찾아 평평하고 어두운 밤하늘로 되돌립니다."),
    ParamSpec("bg_degree", "  └ 그라디언트 복잡도", "astro", 1, 4, 3,
              tooltip="1 = 한 방향 기울기만, 4 = 복잡한 얼룩까지 제거.\n성운이 크게 찍힌 사진은 낮게 두세요."),
    ParamSpec("bg_neutral", "배경 색 중화", "astro",
              tooltip="하늘 배경이 초록·주황·자주색으로 물든 것을 무채색 검정으로 맞춥니다."),
    ParamSpec("color_calib", "별빛 기준 색 보정", "astro",
              tooltip="사진 속 별들의 평균 색이 흰색이 되도록 화이트 밸런스를 자동으로 맞춥니다."),
    ParamSpec("stretch_mode", "스트레치 방식", "astro", default=0, choices=STRETCH_CHOICES,
              tooltip="천체 원본(선형) 데이터는 거의 검게 보입니다.\n스트레치는 희미한 성운·은하를 끌어올리는 핵심 단계예요.\n"
                      "· 자동(STF): 배경 밝기를 기준으로 자동 조절\n· 아크사인: 밝은 별의 색이 하얗게 날아가지 않게 보존"),
    ParamSpec("stretch", "  └ 스트레치 강도", "astro", default=50,
              tooltip="값이 클수록 희미한 대상이 더 밝게 드러납니다."),
    ParamSpec("scnr", "녹색 노이즈 제거 (SCNR)", "astro",
              tooltip="우주에는 초록색 천체가 거의 없습니다.\n컬러 센서 때문에 생긴 초록 기운을 제거합니다."),
    ParamSpec("ha_boost", "Hα 붉은 성운 강조", "astro",
              tooltip="수소 방출 성운(오리온·장미·북아메리카 성운 등)의 붉은 빛을 강조합니다."),
    ParamSpec("local_contrast", "성운 · 은하 디테일", "astro",
              tooltip="넓은 영역의 명암 차이를 키워 은하수의 먼지띠, 성운의 구조를 또렷하게 합니다."),
    ParamSpec("star_reduce", "별 크기 줄이기", "astro",
              tooltip="별을 작고 단단하게 줄여 성운과 은하가 돋보이게 합니다."),
    # ── 밝기 · 톤 ─────────────────────────────────────────────
    ParamSpec("exposure", "노출", "tone", -3, 3, 0, 0.05, " EV",
              tooltip="사진 전체를 카메라 노출처럼 밝게/어둡게 합니다. (+1 EV = 2배 밝게)"),
    ParamSpec("brightness", "밝기 (중간톤)", "tone", -100, 100,
              tooltip="가장 어두운 곳과 가장 밝은 곳은 그대로 두고 중간 밝기만 조절합니다."),
    ParamSpec("contrast", "대비", "tone", -100, 100,
              tooltip="밝은 곳은 더 밝게, 어두운 곳은 더 어둡게 합니다."),
    ParamSpec("highlights", "하이라이트", "tone", -100, 100,
              tooltip="밝은 영역만 조절합니다. 은하 중심부가 하얗게 날아갔다면 낮춰보세요."),
    ParamSpec("shadows", "섀도우", "tone", -100, 100,
              tooltip="어두운 영역만 조절합니다. 희미한 부분을 살리려면 올리세요."),
    ParamSpec("black_point", "블랙 포인트 (배경 어둡게)", "tone",
              tooltip="이 밝기 이하를 완전한 검정으로 만듭니다. 뿌연 하늘을 깊은 밤하늘로!"),
    # ── 색상 ─────────────────────────────────────────────────
    ParamSpec("temperature", "색온도", "color", -100, 100,
              tooltip="음수 = 차갑게(파랑), 양수 = 따뜻하게(노랑)"),
    ParamSpec("tint", "색조", "color", -100, 100,
              tooltip="음수 = 초록 쪽, 양수 = 자홍(마젠타) 쪽"),
    ParamSpec("saturation", "채도", "color", -100, 100,
              tooltip="모든 색을 진하게/옅게 합니다. -100 = 흑백"),
    ParamSpec("vibrance", "자연 채도", "color", -100, 100,
              tooltip="옅은 색 위주로 채도를 올려 별과 성운 색을 자연스럽게 살립니다."),
    # ── 디테일 · 노이즈 ───────────────────────────────────────
    ParamSpec("sharpen", "선명하게", "detail",
              tooltip="작은 디테일(달 크레이터, 행성 표면)을 또렷하게 합니다."),
    ParamSpec("denoise", "노이즈 감소", "detail",
              tooltip="어두운 하늘의 자글자글한 밝기 노이즈를 부드럽게 합니다.\n별과 경계는 보호됩니다."),
    ParamSpec("chroma_denoise", "색 노이즈 감소", "detail",
              tooltip="고감도 촬영에서 생기는 알록달록한 색 얼룩을 제거합니다."),
]

SPECS_BY_KEY: dict[str, ParamSpec] = {s.key: s for s in PARAM_SPECS}

GEOMETRY_DEFAULTS: dict = {
    "rotation": 0,  # number of 90° counter-clockwise turns
    "flip_h": False,
    "crop": None,  # (x0, y0, x1, y1) normalized to the rotated frame, or None
}


def _default_value(spec: ParamSpec):
    if spec.is_choice:
        return spec.choices[int(spec.default)][0]
    return spec.default


DEFAULTS: dict = {**GEOMETRY_DEFAULTS, **{s.key: _default_value(s) for s in PARAM_SPECS}}


def default_params() -> dict:
    return dict(DEFAULTS)


def geometry_of(params: dict) -> tuple:
    return params["rotation"] % 4, bool(params["flip_h"]), params["crop"]


def is_default(params: dict, keys=None) -> bool:
    keys = keys or [s.key for s in PARAM_SPECS]
    return all(params.get(k) == DEFAULTS[k] for k in keys)
