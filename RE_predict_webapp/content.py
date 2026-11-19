"""站点页面文案：标题、网页简述与导航项集中在这里，模板只负责布局。

改文案只动这个文件；新增页面时在这里加一项，导航条会自动出现对应入口。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Page:
    key: str
    title: str
    brief: str
    template: str
    url_name: str
    nav_label: str
    wide: bool = False


PAGES: Mapping[str, Page] = {
    "home": Page(
        key="home",
        title="生态系统呼吸预测",
        brief=(
            "输入经纬度，先判断是否落在中国陆地范围内，再按气候分区与土壤分区逐级匹配通量观测站，"
            "调用该站的随机森林模型预测生态系统呼吸 Re，并给出匹配置信度。"
        ),
        template="index.html",
        url_name="home",
        nav_label="预测",
    ),
    "stations": Page(
        key="stations",
        title="站点模型查看",
        brief=(
            "集中展示系统内置的全部通量观测站及其随机森林模型：站点编码、名称、经纬度、生态与植被类型、"
            "土壤与气候分区、模型文件状态与输入特征。可按生态类型、分区或模型状态筛选，"
            "展开站点查看特征含义与对应的气象变量来源；数据全部来自后端只读接口。"
        ),
        template="stations.html",
        url_name="stations",
        nav_label="站点模型",
        wide=True,
    ),
    "sources": Page(
        key="sources",
        title="数据来源",
        brief=(
            "说明本系统依赖的全部数据来源：站点随机森林模型、中国陆地边界、气候与土壤分区图层、"
            "Open-Meteo 实时气象特征以及站点配置。每项给出类型、路径或地址、用途与更新方式，便于核对与替换数据。"
        ),
        template="sources.html",
        url_name="sources",
        nav_label="数据来源",
        wide=True,
    ),
}

NAV_PAGES: tuple[Page, ...] = (PAGES["home"], PAGES["stations"], PAGES["sources"])


def page_context(key: str) -> dict[str, Any]:
    """模板公共上下文：当前页文案与导航项，导航、页脚在各页复用。"""
    return {"page": PAGES[key], "nav_items": NAV_PAGES}
