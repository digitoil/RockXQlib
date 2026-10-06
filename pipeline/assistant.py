# -*- coding: utf-8 -*-
"""交互式 LLM 建模助手（与界面无关的核心，可单测）。

一轮对话 = 用户一句话 + **画布当前状态** + （可选）上一次运行结果 -> 助手回复
+ 可选的「修改后的完整工作流」。

设计要点
--------
1. **以画布为准**：每轮都把画布当前工作流发给 LLM，所以用户手动拖拽/改参数后
   继续聊，助手看到的是最新状态；助手是在「改」而不只是「生成」。
2. **提案而非执行**：助手只能产出提案（Proposal）。落到画布、运行都要用户确认；
   LLM 即使要求运行（``run: true``）也只是一个建议标记。
3. **校验-修复循环**：提案里的工作流必须通过结构校验 + 语义检查（前视泄漏等）。
   不通过则把错误喂回去让它改，仍不行就只给文字回复并如实说明，不落半成品。
4. **运行结果回灌**：运行后用 ``summarize_run`` 压成短文本，下一轮（或点「诊断」）
   交给 LLM 分析失败原因 / 解读指标。指标只用真实结果，不让模型编数字。
5. LLM 以 ``chat(messages) -> str`` 注入，不绑厂商。
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .llm import Chat, extract_json
from .runner import prepare
from .specs import extract_specs

MAX_HISTORY_TURNS = 8     # 只保留最近 N 轮对话，防止上下文无限增长
MAX_REPAIRS = 2           # 提案校验失败后最多让 LLM 修正几次

SYSTEM = """你是 qlib 量化建模助手，用户在图形画布上拖拽搭建工作流，你通过对话帮 ta 建模、调参、排错。

每次回复**只输出一个 JSON 对象**（不要 Markdown 围栏、不要多余文字）：
{{"reply": "给用户看的中文回复", "workflow": <完整工作流或 null>, "run": false}}

规则：
- 只是回答问题/解释时，workflow 填 null。
- 要修改画布时，workflow 填**修改后的完整工作流**（不是增量）：{{"nodes":[{{"id","type","props"}}],"links":[{{"from":"n1.端口","to":"n2.端口"}}]}}。
  已有节点必须沿用原 id；新增节点用未占用的 id（如 n7）。props 只写需要的键，键必须来自节点说明书。
- 日期 YYYY-MM-DD；训练/验证/测试区间必须依次递增且不重叠（否则前视泄漏）。
- model_params 等写成 JSON 对象。
- 用户明确要求运行、且工作流已就绪时 run 才填 true；这只是建议，用户会再确认。
- 不要编造回测结果或指标；只能引用下面「上次运行结果」里真实出现的数字。
- 看不懂需求或缺关键信息时，在 reply 里问一个具体问题，workflow 填 null。

节点说明书（类型 / 输入端口 / 输出端口 / 属性及默认值）：
{schema}
"""


def schema_text(specs: Dict[str, Dict[str, Any]]) -> str:
    lines = []
    for t in sorted(specs):
        s = specs[t]
        props = ", ".join("%s(默认 %s)" % (k, json.dumps(s.get("defaults", {}).get(k),
                                                         ensure_ascii=False))
                          for k in s.get("props", []))
        lines.append("- %s「%s」 in=%s out=%s\n    属性: %s" % (
            t, s.get("name", ""), s.get("inputs") or "-", s.get("outputs") or "-", props))
    return "\n".join(lines)


def slim_workflow(wf: Dict[str, Any]) -> Dict[str, Any]:
    """给 LLM 看的精简版：去掉位置/名称等与建模无关的 UI 字段。"""
    return {"nodes": [{"id": n["id"], "type": n["type"], "props": n.get("props") or {}}
                      for n in wf.get("nodes", [])],
            "links": list(wf.get("links", []))}


def summarize_run(summary: Optional[Dict[str, Any]], max_err: int = 400) -> str:
    """把运行汇总压成短文本：状态、逐节点结果、失败原因、真实指标。"""
    if not summary:
        return "（还没有运行过）"
    out = ["状态: %s，成功 %s/%s 个节点，耗时 %.1fs" % (
        summary.get("status"), summary.get("ok_count"), summary.get("total"),
        summary.get("elapsed") or 0)]
    for r in summary.get("records") or []:
        mark = "OK " if r.get("ok") else "FAIL"
        d = (r.get("detail") or "").strip().replace("\n", " ")[:max_err]
        out.append("  [%s] %s%s" % (mark, r.get("node"), "：" + d if d else ""))
    m = summary.get("metrics")
    if m:
        nums = {k: v for k, v in m.items() if isinstance(v, (int, float))
                and not isinstance(v, bool)}
        out.append("指标: " + json.dumps(nums, ensure_ascii=False))
    else:
        out.append("指标: 无（没有产出回测指标）")
    return "\n".join(out)


def _effective(wf: Dict[str, Any], specs: Optional[Dict[str, Dict[str, Any]]]):
    """节点属性 = 默认值 + 显式值。没写的属性等于默认值，比较时不能当成「变化」。"""
    out = {}
    for n in wf.get("nodes", []):
        d = dict((specs or {}).get(n["type"], {}).get("defaults") or {})
        d.update(n.get("props") or {})
        out[n["id"]] = {**n, "props": d}
    return out


def diff_workflows(old: Dict[str, Any], new: Dict[str, Any],
                   specs: Optional[Dict[str, Dict[str, Any]]] = None) -> List[str]:
    """人能一眼看懂的变更清单（用于「应用到画布」前的预览）。"""
    on = _effective(old, specs)
    nn = _effective(new, specs)
    lines = []
    for i in nn:
        if i not in on:
            lines.append("+ 新增节点 %s（%s）" % (i, nn[i]["type"]))
    for i in on:
        if i not in nn:
            lines.append("- 删除节点 %s（%s）" % (i, on[i]["type"]))
    for i in nn:
        if i in on:
            if on[i]["type"] != nn[i]["type"]:
                lines.append("~ %s 类型 %s → %s" % (i, on[i]["type"], nn[i]["type"]))
            op, np_ = on[i].get("props") or {}, nn[i].get("props") or {}
            for k in list(dict.fromkeys(list(op) + list(np_))):
                if op.get(k) != np_.get(k):
                    lines.append("~ %s.%s: %s → %s" % (i, k, op.get(k, "（默认）"),
                                                       np_.get(k, "（默认）")))
    ol = {(l["from"], l["to"]) for l in old.get("links", [])}
    nl = {(l["from"], l["to"]) for l in new.get("links", [])}
    for a, b in sorted(nl - ol):
        lines.append("+ 连线 %s → %s" % (a, b))
    for a, b in sorted(ol - nl):
        lines.append("- 连线 %s → %s" % (a, b))
    return lines


@dataclass
class Proposal:
    reply: str
    workflow: Optional[Dict[str, Any]] = None       # 已编译、已校验、可直接落画布
    changes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    run_suggested: bool = False
    problems: List[str] = field(default_factory=list)  # 提案没能通过校验时的原因


class Assistant:
    """一个对话会话。保存历史；每轮传入最新画布与运行结果。"""

    def __init__(self, chat: Chat, specs: Optional[Dict[str, Dict[str, Any]]] = None):
        self.chat = chat
        self.specs = specs or extract_specs()
        self.history: List[Dict[str, str]] = []

    def reset(self) -> None:
        self.history.clear()

    # ---- 内部 ----
    def _messages(self, user_text: str, canvas: Dict[str, Any],
                  last_run: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
        ctx = ("【画布当前工作流】\n%s\n\n【上次运行结果】\n%s\n\n【用户】\n%s" % (
            json.dumps(slim_workflow(canvas), ensure_ascii=False) if canvas.get("nodes")
            else "（画布是空的）",
            summarize_run(last_run), user_text))
        hist = self.history[-2 * MAX_HISTORY_TURNS:]
        return ([{"role": "system", "content": SYSTEM.format(schema=schema_text(self.specs))}]
                + hist + [{"role": "user", "content": ctx}])

    @staticmethod
    def _parse(reply_text: str) -> Tuple[str, Any, bool]:
        """解析回复。不是 JSON 就当作纯文字回答（容错，不丢用户可读内容）。"""
        try:
            obj = extract_json(reply_text)
        except ValueError:
            return reply_text.strip(), None, False
        return (str(obj.get("reply") or "").strip(), obj.get("workflow"),
                bool(obj.get("run")))

    def _compile(self, wf_doc: Any, canvas: Dict[str, Any]):
        if not isinstance(wf_doc, dict):
            return None, ["workflow 必须是对象"], []
        wf, errs, warns = prepare(copy.deepcopy(wf_doc), None, self.specs)
        if errs:
            return None, errs, warns
        # 保留画布上已有节点的位置与名称，避免每次提案都把图重新排版
        old = {n["id"]: n for n in canvas.get("nodes", [])}
        for n in wf["nodes"]:
            if n["id"] in old:
                n["pos"] = old[n["id"]].get("pos") or n["pos"]
                n["name"] = old[n["id"]].get("name") or n["name"]
        wf.pop("params", None)
        return wf, [], warns

    # ---- 对外 ----
    def turn(self, user_text: str, canvas: Optional[Dict[str, Any]] = None,
             last_run: Optional[Dict[str, Any]] = None) -> Proposal:
        canvas = canvas or {"nodes": [], "links": []}
        msgs = self._messages(user_text, canvas, last_run)
        reply_text = self.chat(msgs)
        reply, wf_doc, run = self._parse(reply_text)

        prop = Proposal(reply=reply, run_suggested=run)
        if wf_doc is not None:
            for attempt in range(MAX_REPAIRS + 1):
                wf, errs, warns = self._compile(wf_doc, canvas)
                if not errs:
                    prop.workflow, prop.warnings = wf, warns
                    prop.changes = diff_workflows(canvas, wf, self.specs)
                    break
                prop.problems = errs
                if attempt == MAX_REPAIRS:
                    break
                msgs = msgs + [
                    {"role": "assistant", "content": reply_text},
                    {"role": "user", "content": "你提出的工作流未通过校验，请修正后按同样格式重新输出：\n- "
                     + "\n- ".join(errs[:10])}]
                reply_text = self.chat(msgs)
                reply, wf_doc, run = self._parse(reply_text)
                prop.reply, prop.run_suggested = reply or prop.reply, run
                if wf_doc is None:   # 它放弃了修改，只回了文字
                    prop.problems = []
                    break
            if prop.workflow is None and prop.problems:
                prop.reply = (prop.reply + "\n\n").lstrip() + \
                    "（我提出的修改没能通过校验，所以没有改动画布：%s）" % "；".join(prop.problems[:3])
            if prop.workflow is None:
                prop.run_suggested = False
            elif not prop.changes:
                prop.workflow = None   # 与画布完全一致，没有可应用的修改

        # 历史里存「用户原话」与助手文字，不存庞大的画布快照（每轮会重新给最新的）
        self.history += [{"role": "user", "content": user_text},
                         {"role": "assistant", "content": prop.reply}]
        return prop

    def diagnose(self, canvas: Dict[str, Any], last_run: Optional[Dict[str, Any]]) -> Proposal:
        """针对上一次运行：失败就分析原因并给出修改；成功就如实解读指标。"""
        if not last_run:
            return Proposal(reply="还没有运行结果可分析，请先运行一次。")
        ok = last_run.get("status") == "success"
        ask = ("请解读上次运行的指标（只引用真实数字，样本外表现不好时直说，不要美化），"
               "并指出一个最值得尝试的改进。" if ok else
               "上次运行失败了。请根据失败节点的错误信息分析最可能的原因；"
               "如果能通过修改画布解决，就给出修改后的完整工作流，否则说明需要用户做什么"
               "（如数据目录、依赖缺失）。")
        return self.turn(ask, canvas, last_run)
