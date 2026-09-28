"""One-click looks. Each preset replaces all adjustments (rotation and crop are kept)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .params import GEOMETRY_DEFAULTS, default_params


@dataclass(frozen=True)
class Preset:
    key: str
    name: str
    description: str
    values: dict = field(default_factory=dict)


PRESETS: list[Preset] = [
    Preset("original", "원본", "모든 보정을 끈 원래 사진"),
    Preset(
        "auto_astro", "✨ 자동 천체 보정",
        "망원경·장노출 원본을 한 번에: 광해 제거 → 색 중화 → 스트레치 → 노이즈 정리",
        dict(hotpixel=30, bg_remove=100, bg_degree=3, bg_neutral=100, color_calib=60,
             stretch_mode="auto", stretch=50, scnr=70, local_contrast=20,
             chroma_denoise=50, denoise=25, saturation=25),
    ),
    Preset(
        "milky_way", "🌌 은하수",
        "카메라로 찍은 은하수: 먼지띠 대비와 색을 살리고 하늘을 깔끔하게",
        dict(bg_remove=80, bg_degree=2, bg_neutral=80, scnr=30, brightness=20, contrast=20,
             highlights=-15, shadows=20, local_contrast=45, vibrance=35, saturation=15,
             chroma_denoise=40, denoise=20),
    ),
    Preset(
        "emission", "🔴 발광 성운 (Hα)",
        "오리온·장미 성운처럼 붉은 수소 성운을 선명하게, 별은 작게",
        dict(hotpixel=30, bg_remove=100, bg_degree=3, bg_neutral=100, stretch_mode="auto",
             stretch=55, scnr=80, ha_boost=60, local_contrast=35, star_reduce=45,
             saturation=35, chroma_denoise=50, denoise=30),
    ),
    Preset(
        "galaxy", "🌀 은하 · 딥스카이",
        "안드로메다 같은 은하: 별 색을 보존하는 아크사인 스트레치",
        dict(hotpixel=30, bg_remove=100, bg_degree=3, bg_neutral=100, color_calib=80,
             stretch_mode="asinh", stretch=50, scnr=60, local_contrast=30, star_reduce=25,
             vibrance=30, chroma_denoise=40, denoise=25, sharpen=15),
    ),
    Preset(
        "light_pollution", "🌆 도심 광해 제거",
        "주황색으로 뜬 도시 하늘과 한쪽이 밝은 그라디언트를 제거",
        dict(bg_remove=100, bg_degree=4, bg_neutral=100, color_calib=50, scnr=40,
             black_point=5, brightness=10, contrast=10, vibrance=20, chroma_denoise=40),
    ),
    Preset(
        "moon", "🌙 달 · 행성",
        "크레이터와 행성 표면 디테일을 또렷하게",
        dict(sharpen=70, local_contrast=25, contrast=20, highlights=-20, black_point=5,
             saturation=-60, chroma_denoise=40, denoise=10),
    ),
    Preset(
        "star_trails", "💫 별 궤적",
        "별 궤적 사진의 하늘을 어둡게 하고 별 색을 살림",
        dict(hotpixel=40, bg_remove=40, bg_neutral=80, contrast=20, black_point=10,
             vibrance=40, saturation=15, chroma_denoise=30),
    ),
    Preset(
        "vivid_night", "🌠 선명한 밤하늘",
        "일반 야경·별 사진을 시원하고 선명하게",
        dict(bg_remove=60, bg_neutral=60, temperature=-10, brightness=10, contrast=30,
             black_point=6, local_contrast=30,
             vibrance=50, saturation=20, chroma_denoise=30),
    ),
    Preset(
        "mono", "🖤 흑백 (모노)",
        "흑백 천체 사진: 구조와 명암에 집중",
        dict(bg_remove=60, brightness=15, contrast=25, local_contrast=30, saturation=-100,
             denoise=20),
    ),
]

PRESETS_BY_KEY = {p.key: p for p in PRESETS}


def apply_preset(preset: Preset, current: dict) -> dict:
    params = default_params()
    for k in GEOMETRY_DEFAULTS:
        params[k] = current.get(k, params[k])
    params.update(preset.values)
    return params
