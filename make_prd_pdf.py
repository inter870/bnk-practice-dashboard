from pathlib import Path
import textwrap

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


BASE_DIR = Path(__file__).resolve().parent
INPUT_MD = BASE_DIR / "PRD.md"
OUTPUT_PDF = BASE_DIR / "PRD.pdf"


def pick_font() -> str:
    available = {font.name for font in fm.fontManager.ttflist}
    for candidate in ["Malgun Gothic", "Noto Sans KR", "AppleGothic", "NanumGothic"]:
        if candidate in available:
            return candidate
    return "DejaVu Sans"


def wrap_markdown_line(line: str, width: int = 92) -> list[str]:
    if not line:
        return [""]
    if line.startswith("#"):
        return [line]

    prefix = ""
    body = line
    if line.startswith("- "):
        prefix = "- "
        body = line[2:]
    elif line.startswith("* "):
        prefix = "* "
        body = line[2:]
    elif line.startswith("  - "):
        prefix = "  - "
        body = line[4:]
    elif line.startswith("  * "):
        prefix = "  * "
        body = line[4:]
    elif line[:2].isdigit() and line[2:4] == ". ":
        prefix = line[:4]
        body = line[4:]

    wrapped = textwrap.wrap(
        body,
        width=max(20, width - len(prefix)),
        break_long_words=False,
        break_on_hyphens=False,
    )
    if not wrapped:
        return [prefix.rstrip()]
    return [prefix + wrapped[0]] + [(" " * len(prefix)) + part for part in wrapped[1:]]


def render_pdf() -> None:
    md_text = INPUT_MD.read_text(encoding="utf-8")
    source_lines = [line.rstrip() for line in md_text.splitlines()]

    font_name = pick_font()
    plt.rcParams["font.family"] = font_name
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["ps.fonttype"] = 42

    page_width = 8.27
    page_height = 11.69
    margin_left = 0.55
    margin_top = 0.55
    margin_bottom = 0.55
    line_height = 0.19
    lines_per_page = int((page_height - margin_top - margin_bottom) / line_height)
    font_size = 10.2

    expanded_lines: list[str] = []
    for raw_line in source_lines:
        expanded_lines.extend(wrap_markdown_line(raw_line))

    pages = [
        expanded_lines[i : i + lines_per_page]
        for i in range(0, len(expanded_lines), lines_per_page)
    ]

    with PdfPages(OUTPUT_PDF) as pdf:
        for page_idx, page in enumerate(pages):
            fig = plt.figure(figsize=(page_width, page_height))
            ax = fig.add_axes([0, 0, 1, 1])
            ax.axis("off")
            y_start = 1 - margin_top / page_height

            if page_idx == 0:
                fig.text(
                    margin_left / page_width,
                    0.965,
                    "PRD - Streamlit 금융 대시보드",
                    ha="left",
                    va="top",
                    fontsize=18,
                    fontweight="bold",
                )
                fig.text(
                    margin_left / page_width,
                    0.935,
                    "Generated from PRD.md",
                    ha="left",
                    va="top",
                    fontsize=10,
                    color="#475569",
                )

            for idx, line in enumerate(page):
                display = line
                style = {"fontsize": font_size, "fontfamily": font_name}

                if line.startswith("# "):
                    display = line[2:]
                    style.update({"fontsize": 16, "fontweight": "bold"})
                elif line.startswith("## "):
                    display = line[3:]
                    style.update({"fontsize": 13, "fontweight": "bold"})
                elif line.startswith("### "):
                    display = line[4:]
                    style.update({"fontsize": 11.5, "fontweight": "bold"})
                elif line.startswith("- "):
                    display = "• " + line[2:]
                elif line.startswith("* "):
                    display = "• " + line[2:]

                fig.text(
                    margin_left / page_width,
                    y_start - idx * line_height / page_height,
                    display,
                    ha="left",
                    va="top",
                    **style,
                )

            pdf.savefig(fig)
            plt.close(fig)

    print(f"Saved {OUTPUT_PDF} using font {font_name} ({len(pages)} pages)")


if __name__ == "__main__":
    render_pdf()
