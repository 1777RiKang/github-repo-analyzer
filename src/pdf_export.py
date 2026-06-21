"""
PDF 报告导出模块
将 7+2 张图表 + 文字分析报告合并为一份 PDF 文件。

使用 matplotlib PdfPages，无额外依赖。
"""

import os
from datetime import datetime
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei",
    "Noto Sans CJK SC", "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False


def _add_text_page(pdf: PdfPages, text: str, title: str = "分析报告") -> None:
    """在 PDF 中添加文字页面。"""
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")
    ax.text(
        0.5, 0.98, title, fontsize=18, fontweight="bold",
        ha="center", va="top", transform=ax.transAxes,
    )
    # 分页显示文本（每页约 50 行）
    lines = text.split("\n")
    max_lines = 48
    page_lines = lines[:max_lines]
    content = "\n".join(page_lines)

    ax.text(
        0.02, 0.94, content, fontsize=7.5, family="sans-serif",
        ha="left", va="top", transform=ax.transAxes,
        linespacing=1.3,
    )
    plt.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)

    # 如果文本超出一页，递归处理剩余部分
    if len(lines) > max_lines:
        remaining = "\n".join(lines[max_lines:])
        _add_text_page(pdf, remaining, title="(续)")


def _add_title_page(pdf: PdfPages, user: str, stats: dict) -> None:
    """添加封面页。"""
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")

    ax.text(0.5, 0.75, "GitHub 仓库数据分析报告", fontsize=24, fontweight="bold",
            ha="center", va="center", transform=ax.transAxes)
    ax.text(0.5, 0.65, f"分析对象: {user}", fontsize=16,
            ha="center", va="center", transform=ax.transAxes, color="#555")
    ax.text(0.5, 0.58, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            fontsize=12, ha="center", va="center", transform=ax.transAxes, color="#888")

    # 关键指标
    if stats:
        y = 0.45
        ax.text(0.5, y, "── 关键指标 ──", fontsize=14, fontweight="bold",
                ha="center", va="center", transform=ax.transAxes)
        y -= 0.05
        for k, v in stats.items():
            ax.text(0.3, y, f"{k}:", fontsize=11, ha="left", va="center",
                    transform=ax.transAxes, color="#333")
            ax.text(0.7, y, str(v), fontsize=11, ha="left", va="center",
                    transform=ax.transAxes, fontweight="bold", color="#1f2328")
            y -= 0.035

    ax.text(0.5, 0.05, "Powered by GitHub Repo Analyzer", fontsize=9,
            ha="center", va="center", transform=ax.transAxes, color="#aaa")

    plt.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _add_chart_from_path(pdf: PdfPages, path: str) -> None:
    """从 PNG 文件读取图表并添加到 PDF。"""
    if not os.path.exists(path):
        return
    from PIL import Image
    img = Image.open(path)
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.imshow(img)
    ax.axis("off")
    ax.set_title(
        os.path.basename(path).replace(".png", "").replace("_", " ").title(),
        fontsize=12, fontweight="bold", pad=10,
    )
    plt.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _add_chart_from_path_fallback(pdf: PdfPages, path: str) -> None:
    """从 PNG 文件读取图表（无 PIL 时用 matplotlib 读取）。"""
    if not os.path.exists(path):
        return
    img = plt.imread(path)
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.imshow(img)
    ax.axis("off")
    ax.set_title(
        os.path.basename(path).replace(".png", "").replace("_", " ").title(),
        fontsize=12, fontweight="bold", pad=10,
    )
    plt.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def export_pdf(
    user: str,
    stats: dict,
    report: str,
    chart_paths: list[str],
    output_dir: str,
) -> str:
    """将分析结果导出为 PDF 报告。

    参数:
        user: GitHub 用户名
        stats: basic_stats 返回的统计字典
        report: summary_report 返回的文字报告
        chart_paths: 图表文件路径列表
        output_dir: 输出目录

    返回:
        生成的 PDF 文件路径
    """
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"report_{user}.pdf")

    # 尝试用 PIL 读取图片，fallback 到 matplotlib
    try:
        from PIL import Image  # noqa: F401
        add_chart = _add_chart_from_path
    except ImportError:
        add_chart = _add_chart_from_path_fallback

    with PdfPages(pdf_path) as pdf:
        # 1. 封面页
        _add_title_page(pdf, user, stats)

        # 2. 文字报告页
        _add_text_page(pdf, report)

        # 3. 图表页
        for path in chart_paths:
            try:
                add_chart(pdf, path)
            except Exception as e:
                print(f"    [WARN] 跳过图表 {os.path.basename(path)}: {e}")

    return pdf_path


def export_pdf_to_bytes(
    user: str,
    stats: dict,
    report: str,
    chart_paths: list[str],
) -> BytesIO:
    """导出 PDF 到内存 BytesIO（用于 Streamlit 下载按钮）。"""
    buf = BytesIO()

    try:
        from PIL import Image  # noqa: F401
        add_chart = _add_chart_from_path
    except ImportError:
        add_chart = _add_chart_from_path_fallback

    with PdfPages(buf) as pdf:
        _add_title_page(pdf, user, stats)
        _add_text_page(pdf, report)
        for path in chart_paths:
            try:
                add_chart(pdf, path)
            except Exception:
                pass

    buf.seek(0)
    return buf
