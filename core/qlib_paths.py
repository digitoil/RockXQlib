#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Qlib 数据目录定位。

## 为什么需要这个模块

项目里 `provider_uri` 的默认值原本写死在多处，而且**指向的路径都不存在**：

    core/config_manager.py          'D:\\\\qlib_data'                  ← 不存在
    core/base_node.py               '~/.qlib/qlib_data/cn_data'       ← 不存在
    core/qlib_core_integration.py   '~/.qlib/qlib_data/cn_data'       ← 不存在
    nodes/qlib_core_nodes.py        'D:\\\\qlib_data'                  ← 不存在
    config/node_fusion_config.yaml  "D:\\\\qlib_data"                  ← 不存在

本机真实数据只有一处：
    E:\\2025\\RockX20251003\\RockXFWV21\\qlib_data\\cn_data

后果：新建「Qlib初始化」节点后如果不动那个属性，取数就会落到一个
不存在的目录上，报错信息还未必直白（qlib 会说找不到 calendar）。

## 做法

按候选列表探测，并**校验目录真的是 qlib 数据目录**
（必须同时有 ``calendars/`` 与 ``features/`` 与 ``instruments/``），
避免把同名但无关的目录当数据源。

支持环境变量 ``QLIB_PROVIDER_URI`` 显式覆盖（换机器时不用改代码）。
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "is_qlib_data_dir",
    "find_qlib_data_path",
    "get_default_provider_uri",
    "ENV_VAR",
]

#: 环境变量名：显式指定 qlib 数据目录（优先级最高）
ENV_VAR = "QLIB_PROVIDER_URI"

#: 找不到任何数据目录时的兜底值（保持与 qlib 官方默认一致）
_FALLBACK = "~/.qlib/qlib_data/cn_data"


def is_qlib_data_dir(path: Optional[str]) -> bool:
    """判断目录是否为一个可用的 qlib 数据目录。

    qlib 的数据目录至少要有这三样：
        calendars/   交易日历
        features/    特征数据
        instruments/ 标的列表

    只判断目录存在是不够的 —— 空目录或同名无关目录会让 qlib
    在后面报出难以定位的错误。
    """
    if not path:
        return False
    try:
        p = os.path.abspath(os.path.expanduser(path))
    except Exception:
        return False
    if not os.path.isdir(p):
        return False
    return all(os.path.isdir(os.path.join(p, sub))
               for sub in ("calendars", "features", "instruments"))


def _candidate_paths() -> List[str]:
    """收集所有候选路径（按优先级排序）。"""
    cands: List[str] = []

    # 1) 环境变量显式指定
    env = os.environ.get(ENV_VAR)
    if env:
        cands.append(env)

    # 2) 相对本模块推算的项目内位置
    here = os.path.dirname(os.path.abspath(__file__))     # <RockXQlib>/core
    proj = os.path.dirname(here)                          # <RockXQlib>
    root = os.path.dirname(proj)                          # E:\2025\RockX20251003

    cands += [
        # 本项目实际布局：RockXFWV21/qlib_data/cn_data
        os.path.join(root, "RockXFWV21", "qlib_data", "cn_data"),
        os.path.join(root, "RockXFWV21", "qlib_data"),
        # 项目自带的可能位置
        os.path.join(proj, "qlib_data", "cn_data"),
        os.path.join(proj, "qlib_data"),
        os.path.join(root, "qlib_data", "cn_data"),
        os.path.join(root, "qlib_data"),
    ]

    # 3) qlib 官方默认位置
    cands += [
        os.path.expanduser("~/.qlib/qlib_data/cn_data"),
        os.path.expanduser("~/.qlib/qlib_data"),
        "D:/qlib_data",
    ]

    return cands


def find_qlib_data_path(verbose: bool = False) -> Optional[str]:
    """返回第一个真实可用的 qlib 数据目录；找不到返回 None。

    Args:
        verbose: 为 True 时打印探测过程（排查路径问题时很有用）。
    """
    for cand in _candidate_paths():
        ok = is_qlib_data_dir(cand)
        if verbose:
            print("  [%s] %s" % ("命中" if ok else "  -", cand))
        if ok:
            return os.path.abspath(os.path.expanduser(cand))
    return None


def get_default_provider_uri() -> str:
    """给节点属性用的默认 provider_uri。

    找到真实数据目录就返回它（这样新建节点开箱即用），
    否则返回 qlib 官方默认值并给出提示。
    """
    found = find_qlib_data_path()
    if found:
        return found
    logger.warning(
        "未找到可用的 qlib 数据目录（已尝试环境变量 %s 与多个常见位置）。"
        "请手动设置 provider_uri，或用 %s 指定数据目录。", ENV_VAR, ENV_VAR)
    return _FALLBACK


if __name__ == "__main__":       # 手动排查用
    print("候选路径探测:")
    p = find_qlib_data_path(verbose=True)
    print()
    print("结果:", p or "未找到")
    print("默认值:", get_default_provider_uri())
