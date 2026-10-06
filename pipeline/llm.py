# -*- coding: utf-8 -*-
"""需求描述 -> 流水线（总结文档「下一步」第 2、3 步）。

三条原则（来自系统总结）：
1. 不做孤岛：产物是标准流水线定义，与手写的走同一条编译/校验/执行路径
2. 必须校验：LLM 输出不可信，不通过校验就把错误喂回去让它修，最多 N 轮
3. 可回滚：只写成「草稿」文件供预览，用户确认（accept）后才进入 pipelines/

LLM 以 ``chat(messages) -> str`` 注入，因此本模块不绑定任何厂商，也便于测试。
自带一个 OpenAI 兼容客户端（Ollama / GPUStack / vLLM / OpenAI 都支持该协议）。
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.workflow_schema import describe_schema

from .runner import PROJECT_ROOT, prepare
from .specs import extract_specs

Chat = Callable[[List[Dict[str, str]]], str]

SYSTEM_PROMPT = """你是 qlib 量化流水线工程师。把用户需求翻译成流水线定义 JSON。
只输出一个 JSON 对象，不要解释。格式：
{{"name": "...", "params": {{...可选...}}, "steps": [{{"type": "init"}}, {{"type": "data", "props": {{...}}}}, ...]}}
规则：
- steps 按数据流顺序排列，同名端口会被自动连线；type 可写短名（如 model）或全名
- props 的键必须来自下面的节点说明书，不得自造；日期用 YYYY-MM-DD
- model_params / strategy_kwargs 等参数写成 JSON 对象
- 典型链路：init -> data -> dataset -> model -> strategy -> backtest
- 不要编造数据或结果，只描述流水线本身

{schema}
"""


def extract_json(text: str) -> Dict[str, Any]:
    """从 LLM 回复里取出 JSON（容忍 ```json 围栏与前后废话）。"""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    cand = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    try:
        obj = json.loads(cand)
    except ValueError as e:
        raise ValueError("回复里没有合法 JSON: %s" % e)
    if not isinstance(obj, dict):
        raise ValueError("JSON 顶层必须是对象")
    return obj


def generate_pipeline(request: str, chat: Chat, *, max_rounds: int = 3,
                      specs: Optional[Dict[str, Dict[str, Any]]] = None
                      ) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """返回 ``(pipeline_doc 或 None, 过程日志)``。通过校验才返回 doc。"""
    specs = specs or extract_specs()
    messages = [{"role": "system",
                 "content": SYSTEM_PROMPT.format(schema=describe_schema(specs))},
                {"role": "user", "content": request}]
    trail: List[str] = []
    for rnd in range(1, max_rounds + 1):
        reply = chat(messages)
        try:
            doc = extract_json(reply)
        except ValueError as e:
            problems = [str(e)]
        else:
            _wf, errs, _warn = prepare(doc, None, specs)
            problems = errs
            if not problems:
                trail.append("第 %d 轮：校验通过" % rnd)
                return doc, trail
        trail.append("第 %d 轮：%d 个问题：%s" % (rnd, len(problems), "；".join(problems[:5])))
        messages += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": "输出未通过校验，请修正后重新输出完整 JSON：\n- "
                      + "\n- ".join(problems[:10])}]
    return None, trail


def save_draft(doc: Dict[str, Any], drafts_dir: Optional[Path] = None) -> Path:
    d = Path(drafts_dir or PROJECT_ROOT / "pipelines" / "drafts")
    d.mkdir(parents=True, exist_ok=True)
    p = d / ("%s.json" % re.sub(r"[^\w\-]+", "_", doc.get("name") or "draft"))
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def accept_draft(draft: Path, dest_dir: Optional[Path] = None) -> Path:
    """用户确认后，草稿转正（移到 pipelines/）。"""
    dest = Path(dest_dir or PROJECT_ROOT / "pipelines") / Path(draft).name
    dest.parent.mkdir(parents=True, exist_ok=True)
    Path(draft).replace(dest)
    return dest


def openai_compatible_chat(base_url: str, model: str, api_key: str = "",
                           timeout: float = 300.0) -> Chat:
    """OpenAI 协议客户端（Ollama: http://localhost:11434/v1）。"""
    url = base_url.rstrip("/") + "/chat/completions"

    def chat(messages: List[Dict[str, str]]) -> str:
        body = json.dumps({"model": model, "messages": messages, "temperature": 0}).encode()
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            **({"Authorization": "Bearer " + api_key} if api_key else {})})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    return chat
