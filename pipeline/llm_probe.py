# -*- coding: utf-8 -*-
r"""LLM 端点探测与诊断。

## 为什么需要这个模块

AI 建模助手（``gui/assistant_dock.py`` / ``pipeline/llm.py``）要求用户填
「接口地址 + 模型名」。但填错时的报错只有一句
``请先填写模型名（Ollama 需先启动服务并拉取模型）``，
既不说**当前连不连得上**，也不说**有哪些模型可用**，更不说**该怎么办**。

实际排查中遇到的典型情况（本机真实发生）：

- Ollama 装了模型仓库（几十 GB）却**没装/没启动服务** → 连接被拒
- GPUStack 之类的网关**可达但没有部署任何模型** → ``{"data": []}``
- 端点其实通了，只是模型名写错 → 服务端返回 404，看不出是哪一步错

这三种情况的处理方式完全不同，但用户看到的报错是一样的。
本模块把「探测」独立出来，输出**结论 + 可操作建议**。

## 设计

- 只依赖标准库（``urllib``），不引入 requests/openai 等
- 网络函数全部接受 ``timeout``，且**异常不外抛**（返回结构化的失败原因）
- 解析逻辑（``_parse_openai_models`` / ``_parse_ollama_tags`` /
  ``local_ollama_models``）是纯函数，便于单测，不触网
"""
from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "ProbeResult",
    "probe",
    "candidates",
    "diagnose",
    "format_report",
    "local_ollama_models",
    "find_ollama_exe",
    "DEFAULT_BASE_URL",
]

# Ollama 的 OpenAI 兼容端点（``/v1`` 是协议前缀，原生 API 在根上）
DEFAULT_BASE_URL = "http://localhost:11434/v1"

# 本机可能存放 Ollama 模型仓库的位置（按顺序探测）。
# ``OLLAMA_MODELS`` / ``ROCKX_OLLAMA_MODELS`` 环境变量优先。
_MODEL_DIR_HINTS = (
    r"D:\AIModels",
    r"C:\AIModels",
    os.path.join(os.path.expanduser("~"), ".ollama", "models"),
)

# ollama 可执行文件的常见安装位置
_EXE_HINTS = (
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
    os.path.join(os.environ.get("ProgramFiles", ""), "Ollama", "ollama.exe"),
    os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Ollama", "ollama.exe"),
)


@dataclass
class ProbeResult:
    """一次端点探测的结果。"""

    base_url: str
    ok: bool = False                      # 是否可用（连通 + 至少一个模型）
    reachable: bool = False               # 端口/服务是否可达
    protocol: str = ""                    # 'openai' | 'ollama' | ''
    models: List[str] = field(default_factory=list)
    error: str = ""                       # 失败原因（简短）
    hints: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "base_url": self.base_url, "ok": self.ok, "reachable": self.reachable,
            "protocol": self.protocol, "models": list(self.models),
            "error": self.error, "hints": list(self.hints),
        }


# ---------------------------------------------------------------- 纯解析函数

def _parse_openai_models(obj: Any) -> List[str]:
    """解析 OpenAI 协议 ``GET /models`` 的响应。

    形如 ``{"object": "list", "data": [{"id": "qwen3.5:9b"}, ...]}``。
    容错：``data`` 缺失/非列表时返回空列表，不抛异常。
    """
    if not isinstance(obj, dict):
        return []
    data = obj.get("data")
    if not isinstance(data, list):
        return []
    out: List[str] = []
    for item in data:
        if isinstance(item, dict):
            mid = item.get("id") or item.get("name")
            if isinstance(mid, str) and mid.strip():
                out.append(mid.strip())
    return out


def _parse_ollama_tags(obj: Any) -> List[str]:
    """解析 Ollama 原生 ``GET /api/tags`` 的响应。

    形如 ``{"models": [{"name": "deepseek-r1:8b", ...}, ...]}``。
    """
    if not isinstance(obj, dict):
        return []
    models = obj.get("models")
    if not isinstance(models, list):
        return []
    out: List[str] = []
    for item in models:
        if isinstance(item, dict):
            name = item.get("name") or item.get("model")
            if isinstance(name, str) and name.strip():
                out.append(name.strip())
    return out


def local_ollama_models(models_dir: Optional[str] = None) -> List[str]:
    r"""列出**本机模型仓库**里已有的模型（无需服务在跑）。

    Ollama 的仓库布局是::

        <models_dir>/manifests/registry.ollama.ai/<namespace>/<name>/<tag>

    其中 ``namespace`` 为 ``library`` 时对应官方模型，模型名就是 ``<name>``；
    否则是 ``<namespace>/<name>``。返回形如 ``["deepseek-r1:8b", "qwen3.5:9b"]``。

    ⚠️ **``<tag>`` 是文件，不是目录**（里面是模型的 manifest JSON）。
    最初按目录处理，导致明明有 9 个模型却一个也列不出来 ——
    所以这里对 tag 层接受文件或目录两种形态。

    找不到目录或结构不符时返回空列表（不抛异常）—— 调用方据此判断
    「本机没有现成模型可复用」。
    """
    root = _resolve_models_dir(models_dir)
    if root is None:
        return []
    reg = root / "manifests" / "registry.ollama.ai"
    if not reg.is_dir():
        return []
    out: List[str] = []
    try:
        for ns in sorted(reg.iterdir()):
            if not ns.is_dir() or ns.name.startswith("."):
                continue
            for name in sorted(ns.iterdir()):
                if not name.is_dir() or name.name.startswith("."):
                    continue
                for tag in sorted(name.iterdir()):
                    if tag.name.startswith("."):
                        continue
                    if not (tag.is_file() or tag.is_dir()):
                        continue
                    full = name.name if ns.name == "library" else "%s/%s" % (ns.name, name.name)
                    out.append("%s:%s" % (full, tag.name))
    except OSError:
        return []
    # 全局排序（而不是按命名空间分组排序）—— 调用方/界面拿到的是稳定、
    # 可预测的顺序，例如 ["bge-m3:latest", "deepseek-r1:8b", ...]。
    return sorted(out)


def _resolve_models_dir(models_dir: Optional[str] = None) -> Optional[Path]:
    """定位模型仓库目录。

    语义（重要）：

    - **显式传入 ``models_dir`` 时只看它** —— 不是仓库就返回 ``None``，
      **不**回退到机器默认位置。否则调用方"指定了一个空目录"会被
      静默替换成机器上的真实仓库，排查时完全看不出区别。
    - 未指定时按「环境变量 → 常见位置」的顺序找。
    """

    def is_store(p: Path) -> bool:
        try:
            return (p / "manifests").is_dir()
        except OSError:
            return False

    if models_dir:
        p = Path(models_dir)
        return p if is_store(p) else None

    cands: List[str] = []
    for var in ("ROCKX_OLLAMA_MODELS", "OLLAMA_MODELS"):
        v = os.environ.get(var)
        if v:
            cands.append(v)
    cands.extend(_MODEL_DIR_HINTS)
    for c in cands:
        p = Path(c)
        if is_store(p):
            return p
    return None


def find_ollama_exe() -> Optional[str]:
    """定位 ollama 可执行文件（PATH 优先，其次常见安装目录）。"""
    found = shutil.which("ollama")
    if found:
        return found
    for p in _EXE_HINTS:
        if p and os.path.isfile(p):
            return p
    return None


# ---------------------------------------------------------------- 网络探测

def _fetch_json(url: str, api_key: str = "", timeout: float = 4.0) -> Tuple[bool, Any, str]:
    """GET 一个 JSON。返回 ``(成功?, 解析后的对象或 None, 失败原因)``。

    异常一律转成简短的中文原因，不向外抛。
    """
    headers = {"Accept": "application/json", "User-Agent": "RockXQlib/1.0"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False, None, "认证失败（HTTP %d），请检查 API Key" % e.code
        if e.code == 404:
            return False, None, "端点不存在（HTTP 404），该地址可能不是 OpenAI/Ollama 接口"
        return False, None, "服务返回 HTTP %d" % e.code
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, (ConnectionRefusedError, ConnectionResetError)):
            return False, None, "连接被拒绝：服务未启动或端口不对"
        return False, None, "无法连接：%s" % reason
    except TimeoutError:
        return False, None, "请求超时"
    except OSError as e:
        return False, None, "网络错误：%s" % e
    try:
        return True, json.loads(raw), ""
    except ValueError:
        return False, None, "响应不是合法 JSON（可能不是 OpenAI/Ollama 接口）"


def _url_variants(base_url: str) -> Sequence[Tuple[str, str]]:
    """把用户填的地址展开成「(协议, 待探测 URL)」候选。

    - OpenAI 协议：``<base>/models``
    - Ollama 原生：``<root>/api/tags``，其中 root 是去掉尾部 ``/v1`` 的地址

    用户可能填 ``http://localhost:11434``（原生）或
    ``http://localhost:11434/v1``（OpenAI 兼容），两种都试，避免让人去猜。
    """
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return ()
    root = base[:-3].rstrip("/") if base.endswith("/v1") else base
    out: List[Tuple[str, str]] = [("openai", base + "/models")]
    if root != base:
        out.append(("ollama", root + "/api/tags"))
    else:
        out.append(("ollama", base + "/api/tags"))
    return tuple(out)


def probe(base_url: str, api_key: str = "", timeout: float = 4.0,
          models_dir: Optional[str] = None) -> ProbeResult:
    """探测单个端点，返回结构化结果（含可操作建议）。"""
    res = ProbeResult(base_url=(base_url or "").strip())
    if not res.base_url:
        res.error = "接口地址为空"
        res.hints.append("填写形如 http://localhost:11434/v1 的地址")
        return res

    last_error = ""
    for protocol, url in _url_variants(res.base_url):
        ok, obj, err = _fetch_json(url, api_key, timeout)
        if not ok:
            last_error = err
            continue
        # 连上了：区分「有模型」和「服务在跑但没模型」
        res.reachable = True
        models = (_parse_openai_models(obj) if protocol == "openai"
                  else _parse_ollama_tags(obj))
        if models:
            res.ok = True
            res.protocol = protocol
            res.models = models
            res.error = ""
            return res
        res.protocol = protocol

    if res.reachable:
        res.error = "服务可达，但没有可用模型"
        res.hints.extend(_no_model_hints(res.base_url, models_dir))
    else:
        res.error = last_error or "无法连接"
        res.hints.extend(_unreachable_hints(res.base_url, models_dir))
    return res


def _unreachable_hints(base_url: str, models_dir: Optional[str]) -> List[str]:
    """连不上时给出的建议（区分本地 / 远程）。"""
    hints: List[str] = []
    is_local = any(h in base_url for h in ("localhost", "127.0.0.1", "0.0.0.0"))
    exe = find_ollama_exe()
    local = local_ollama_models(models_dir)
    if is_local:
        if exe:
            hints.append("本机已安装 Ollama（%s），启动服务：`ollama serve`" % exe)
        else:
            hints.append("未检测到 ollama 可执行文件 —— 需先安装 Ollama 才能用本地模型")
        if local:
            root = _resolve_models_dir(models_dir)
            hints.append(
                "本机模型仓库已有 %d 个模型（%s）：%s"
                % (len(local), root, ", ".join(local[:6])))
            hints.append(
                "启动服务时让 Ollama 指向该目录即可直接复用，无需重新下载：\n"
                "        set OLLAMA_MODELS=%s && ollama serve" % root)
        else:
            hints.append("拉取一个模型试试：`ollama pull qwen3.5:9b`")
        hints.append("或改用其它 OpenAI 兼容端点（把上面的接口地址换成网关地址 + API Key）")
    else:
        hints.append("确认地址、端口与网络可达性（远程端点需要本机能访问）")
        hints.append("若端点需要鉴权，请填写 API Key")
    return hints


def _no_model_hints(base_url: str, models_dir: Optional[str]) -> List[str]:
    """服务通了但没有模型时的建议。"""
    hints = ["服务已就绪，但模型列表为空 —— 需要在服务端部署/拉取模型"]
    local = local_ollama_models(models_dir)
    if local:
        root = _resolve_models_dir(models_dir)
        hints.append(
            "本机仓库里已有 %d 个模型（%s）：%s"
            % (len(local), root, ", ".join(local[:6])))
        hints.append("若这是本地 Ollama，设置 OLLAMA_MODELS=%s 后重启服务即可" % root)
    else:
        hints.append("例如 Ollama：`ollama pull qwen3.5:9b`；"
                     "网关类（GPUStack/vLLM）：在服务端部署模型后重试")
    return hints


# ---------------------------------------------------------------- 批量诊断

def candidates() -> List[Tuple[str, str]]:
    """返回候选端点 ``(base_url, api_key)``。

    来源与优先级：环境变量 → 常见默认值。密钥与地址按变量名配对，
    避免把 A 服务的 key 发到 B 服务。
    """
    out: List[Tuple[str, str]] = []
    seen = set()

    def add(url: Optional[str], key: str = "") -> None:
        if not url:
            return
        u = url.strip()
        if not u or u in seen:
            return
        seen.add(u)
        out.append((u, key))

    # 显式配置优先
    add(os.environ.get("LLM_BASE_URL"), os.environ.get("LLM_API_KEY", ""))
    # 本机已有的网关（环境变量里带 key）
    add(os.environ.get("FRACSTUDIO_GPUSTACK_BASE_URL"),
        os.environ.get("FRACSTUDIO_GPUSTACK_API_KEY", ""))
    add(os.environ.get("OPENAI_BASE_URL"), os.environ.get("OPENAI_API_KEY", ""))
    # 常见本地默认值
    add(DEFAULT_BASE_URL)
    add("http://127.0.0.1:11434/v1")
    return out


def diagnose(base_url: Optional[str] = None, api_key: str = "",
             timeout: float = 4.0, models_dir: Optional[str] = None
             ) -> Tuple[ProbeResult, List[ProbeResult]]:
    """诊断端点。返回 ``(最佳结果, 全部探测结果)``。

    - 指定了 ``base_url``：只探测它（用户明确指定的优先，不做猜测）
    - 未指定：逐个探测 ``candidates()``，返回第一个可用的；都不可用时
      返回「最接近可用」的那个（可达但无模型 > 不可达），便于给出准确建议
    """
    if base_url:
        r = probe(base_url, api_key, timeout, models_dir)
        return r, [r]

    results: List[ProbeResult] = []
    for url, key in candidates():
        r = probe(url, key, timeout, models_dir)
        results.append(r)
        if r.ok:
            return r, results
    # 都不可用：优先展示"可达但无模型"（说明离成功更近）
    for r in results:
        if r.reachable:
            return r, results
    if results:
        return results[0], results
    empty = ProbeResult(base_url="")
    empty.error = "没有可探测的端点"
    empty.hints.append("请填写接口地址，或用环境变量 LLM_BASE_URL 指定")
    return empty, []


def format_report(primary: ProbeResult, all_results: Optional[Sequence[ProbeResult]] = None,
                  local_models: Optional[Sequence[str]] = None) -> str:
    """把探测结果渲染成给人看的报告（CLI 与 GUI 共用）。"""
    lines: List[str] = []
    lines.append("LLM 端点检测")
    lines.append("=" * 52)

    if primary.ok:
        lines.append("[可用] %s" % primary.base_url)
        lines.append("  协议: %s" % primary.protocol)
        lines.append("  模型: %s" % ", ".join(primary.models))
        lines.append("  建议: 把模型名填为上面任意一个（例如 %s）" % primary.models[0])
    elif primary.reachable:
        lines.append("[不可用] %s" % primary.base_url)
        lines.append("  服务可达，但没有可用模型")
    else:
        lines.append("[不可用] %s" % primary.base_url)
        if primary.error:
            lines.append("  原因: %s" % primary.error)

    if primary.hints:
        lines.append("")
        lines.append("建议:")
        for h in primary.hints:
            lines.append("  - %s" % h)

    others = [r for r in (all_results or []) if r.base_url != primary.base_url]
    if others:
        lines.append("")
        lines.append("其它已探测端点:")
        for r in others:
            mark = "可用" if r.ok else ("可达无模型" if r.reachable else "不可达")
            extra = ("，模型 %d 个" % len(r.models)) if r.models else ""
            lines.append("  [%s] %s%s" % (mark, r.base_url, extra))

    local = list(local_models) if local_models is not None else local_ollama_models()
    if local:
        root = _resolve_models_dir()
        lines.append("")
        lines.append("本机模型仓库（%s）已有 %d 个模型:" % (root, len(local)))
        lines.append("  " + ", ".join(local))
    return "\n".join(lines)
