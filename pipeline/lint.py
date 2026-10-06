# -*- coding: utf-8 -*-
"""语义检查：结构合法但参数不合理的流水线（结构校验抓不到的那类）。

只做**确定错误**与**高概率错误**，不做风格建议：
- 错误：JSON 文本属性解析失败、日期格式非法、区间起止颠倒、训练/验证/测试区间重叠
- 警告：回测区间超出测试区间、基准与股票池看起来不匹配
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Dict, List, Tuple

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# 属性 -> 必须是 JSON 对象文本
_JSON_PROPS = {"model_params", "strategy_params", "strategy_kwargs",
               "handler_kwargs", "strategy_config"}
_BENCH = {"csi300": "SH000300", "csi500": "SH000905", "csi100": "SH000903"}


def _d(s: Any):
    if not isinstance(s, str) or not _DATE.match(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def lint_workflow(wf: Dict[str, Any], specs: Dict[str, Dict[str, Any]] = None
                  ) -> Tuple[List[str], List[str]]:
    """返回 ``(errors, warnings)``。

    流水线里没写的属性会用节点默认值，所以检查前先把 ``specs`` 的默认值合并进来，
    否则「只改了 train_end」这类写法会因为缺另一端而漏检。
    """
    if specs:
        wf = {**wf, "nodes": [
            {**n, "props": {**(specs.get(n["type"], {}).get("defaults") or {}),
                            **(n.get("props") or {})}} for n in wf.get("nodes", [])]}
    errors: List[str] = []
    warns: List[str] = []
    nodes = wf.get("nodes", [])

    for n in nodes:
        nid, props = n["id"], n.get("props") or {}
        for k, v in props.items():
            if k in _JSON_PROPS and isinstance(v, str) and v.strip():
                try:
                    if not isinstance(json.loads(v), dict):
                        errors.append("%s.%s 必须是 JSON 对象" % (nid, k))
                except ValueError as e:
                    errors.append("%s.%s 不是合法 JSON: %s" % (nid, k, e))
            if (k.endswith("_start") or k.endswith("_end") or k in ("start_time", "end_time")) \
                    and isinstance(v, str) and v and _d(v) is None:
                errors.append("%s.%s 日期格式应为 YYYY-MM-DD: %r" % (nid, k, v))

        # 成对的起止
        for a, b in (("start_time", "end_time"), ("train_start", "train_end"),
                     ("valid_start", "valid_end"), ("test_start", "test_end")):
            da, db = _d(props.get(a)), _d(props.get(b))
            if da and db and da > db:
                errors.append("%s: %s(%s) 晚于 %s(%s)" % (nid, a, props[a], b, props[b]))

        if n["type"] == "qlib.core.dataset":
            segs = [(s, _d(props.get(s + "_start")), _d(props.get(s + "_end")))
                    for s in ("train", "valid", "test")]
            for (s1, a1, b1), (s2, a2, b2) in zip(segs, segs[1:]):
                if b1 and a2 and b1 >= a2:
                    errors.append("%s: %s 区间与 %s 区间重叠或顺序颠倒（会造成前视泄漏）"
                                  % (nid, s1, s2))

    ds = next((n for n in nodes if n["type"] == "qlib.core.dataset"), None)
    bt = next((n for n in nodes if n["type"] == "qlib.core.backtest"), None)
    if ds and bt:
        t0, t1 = _d(ds["props"].get("test_start")), _d(ds["props"].get("test_end"))
        b0, b1 = _d(bt["props"].get("start_time")), _d(bt["props"].get("end_time"))
        if t0 and b0 and b0 < t0:
            warns.append("[警告] 回测开始(%s)早于测试集开始(%s)：区间内没有样本外预测"
                         % (bt["props"]["start_time"], ds["props"]["test_start"]))
        if t1 and b1 and b1 > t1:
            warns.append("[警告] 回测结束(%s)晚于测试集结束(%s)：超出部分没有预测信号"
                         % (bt["props"]["end_time"], ds["props"]["test_end"]))
        uni = str(ds["props"].get("instruments", "")).lower()
        bench = bt["props"].get("benchmark")
        if uni in _BENCH and bench and bench != _BENCH[uni]:
            warns.append("[警告] 股票池 %s 通常对应基准 %s，当前基准是 %s"
                         % (uni, _BENCH[uni], bench))
    return errors, warns
