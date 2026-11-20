"""站点页面文案：标题、网页简述与导航项集中在这里，模板只负责布局。

对外化口径：这里只写"这页做什么、怎么看"，不出现路径、文件名、内部模块名与变量。
改文案只动这个文件；新增页面时在这里加一项，顶部导航与左侧导航框会自动出现入口。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Page:
    """一个对外页面：文案、模板与两套导航文案（顶部导航 / 首页左侧导航框）。"""

    key: str
    title: str
    brief: str
    template: str
    url_name: str
    nav_label: str
    box_label: str
    box_hint: str


PAGES: Mapping[str, Page] = {
    "home": Page(
        key="home",
        title="生态系统呼吸预测",
        brief=(
            "输入经纬度，即可获得该位置的生态系统呼吸（Re）预测值、匹配置信度与匹配站点。"
            "适合生态、气象与碳循环相关的研究与业务使用。"
        ),
        template="index.html",
        url_name="home",
        nav_label="首页",
        box_label="首页",
        box_hint="返回预测",
    ),
    "training": Page(
        key="training",
        title="模型训练情况",
        brief=(
            "按站点汇总模型训练情况：训练与测试样本规模、训练集与测试集的均方误差（MSE）"
            "与决定系数（R²），以及模型类别。可用于判断各站点预测结果的可靠程度。"
        ),
        template="training.html",
        url_name="training",
        nav_label="站点",
        box_label="站点",
        box_hint="查看训练情况",
    ),
    "sources": Page(
        key="sources",
        title="数据来源注明",
        brief=(
            "说明本站预测所依据的数据来源，包括每项来源的名称、类型、用途与更新方式，"
            "便于了解数据出处与可靠性。"
        ),
        template="sources.html",
        url_name="sources",
        nav_label="数据来源",
        box_label="数据来源",
        box_hint="查看来源署名",
    ),
}

# 顶部导航与首页左侧三个导航框使用同一组页面，顺序即展示顺序
NAV_PAGES: tuple[Page, ...] = (PAGES["home"], PAGES["training"], PAGES["sources"])


def page_context(key: str) -> dict[str, Any]:
    """模板公共上下文：当前页文案与导航项，导航、页脚在各页复用。"""
    return {"page": PAGES[key], "nav_items": NAV_PAGES, "rail_items": NAV_PAGES}
