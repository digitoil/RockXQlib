# -*- coding: utf-8 -*-
r"""把 qlib 官方基准工作流配置导入为 RockXQlib 流水线模板。

## 为什么需要它

qlib 仓库自带 ``examples/benchmarks/``，里面有 **25 个模型、55 个
``workflow_config*.yaml``**，每个都是一条完整可跑的流水线：
数据区间、处理器、**模型超参（论文里的官方调优值）**、策略、回测
全部配好了。

但它们是 qlib 的 ``qrun`` 格式，与本项目的流水线格式不同，所以一直没用上 ——
用户只能从**一个**手写模板（``pipelines/lgb_alpha158.yaml``）起步，
想跑 LSTM / Transformer / TabNet 得自己查论文抄超参。

本模块做格式转换：把这些现成配置变成 RockXQlib 模板，
于是模板库从 1 个变成几十个，且超参与官方基准一致（结果可与论文比对）。

## 转换对照

===============================  ==========================================
qlib (qrun) 配置                  RockXQlib 流水线
===============================  ==========================================
``qlib_init.region``             ``init.props.region``
``market``                       ``data.props.instruments``
``data_handler_config``          ``dataset.props.handler_kwargs``
``task.dataset.handler.class``   ``dataset.props.handler_class``
``task.dataset.segments``        ``dataset.props.{train,valid,test}_*``
``task.model.class``             ``model.props.model_class``
``task.model.kwargs``            ``model.props.model_params``
``port_analysis_config.strategy``  ``strategy.props.*``
``port_analysis_config.backtest``  ``backtest.props.*``
===============================  ==========================================

## 两个刻意的处理

1. **``provider_uri`` 会被换成本机真实数据目录**。官方配置写的是
   ``~/.qlib/qlib_data/cn_data``，本机并不存在（真实数据在
   ``RockXFWV21/qlib_data/cn_data``）。照搬会让导入的模板**开箱即错**。
2. **无法映射的字段写进生成文件的注释**，不静默丢弃。
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:                                  # pragma: no cover
    yaml = None                                      # type: ignore

from .runner import PROJECT_ROOT

__all__ = [
    "BENCH_ROOT",
    "Benchmark",
    "discover",
    "convert",
    "to_yaml",
    "dump",
    "import_all",
]

BENCH_ROOT = PROJECT_ROOT / "examples" / "benchmarks"
DEFAULT_OUT_DIR = PROJECT_ROOT / "pipelines"

# 文件名形如 workflow_config_<model>_<Handler>[_<market>].yaml
_NAME_RE = re.compile(
    r"^workflow_config_(?P<model>[A-Za-z0-9_]+?)_(?P<handler>Alpha\d+)(?:_(?P<market>[a-z0-9]+))?\.ya?ml$",
    re.IGNORECASE,
)

# dataset 节点支持的 handler kwargs（其余写进注释提示）
_KNOWN_HANDLER_KEYS = {"start_time", "end_time", "fit_start_time", "fit_end_time",
                       "instruments", "label", "benchmark", "infer_processors",
                       "learn_processors", "handler_class", "module_path"}


@dataclass
class Benchmark:
    """一个官方基准配置。"""

    slug: str                     # 生成的文件名（不含扩展），如 qlib_lightgbm_alpha158
    src: Path                     # 源 yaml
    model: str = ""               # LGBModel
    model_module: str = ""        # qlib.contrib.model.gbdt
    handler: str = ""             # Alpha158
    market: str = ""              # csi300 / csi500
    title: str = ""               # 人类可读标题

    def __str__(self) -> str:
        return "%-42s %-18s %-8s %s" % (self.slug, self.model or "?", self.handler, self.market)


def discover(root: Optional[Path] = None) -> List[Benchmark]:
    """扫描 ``examples/benchmarks``，返回全部可导入的基准（按 slug 排序）。

    找不到目录时返回空列表（不抛异常）—— 便于在没带 examples 的环境里降级。
    """
    base = Path(root) if root else BENCH_ROOT
    if not base.is_dir():
        return []
    out: List[Benchmark] = []
    for path in sorted(base.rglob("workflow_config*.y*ml")):
        m = _NAME_RE.match(path.name)
        if not m:
            continue
        model = m.group("model")
        handler = m.group("handler")
        market = (m.group("market") or "").lower()
        slug = "qlib_%s_%s" % (model.lower(), handler.lower())
        if market:
            slug += "_" + market
        bm = Benchmark(slug=slug, src=path, model="", handler=handler, market=market)
        # 标题用目录名（比文件名好看）：LightGBM / Alpha158 / csi300
        parent = path.parent.name
        bm.title = "%s · %s%s" % (parent, handler, (" · " + market) if market else "")
        # 顺手读出模型类名 —— 列表展示与筛选都要用。
        # 读失败（yaml 缺失/格式怪）不影响发现，留空即可。
        try:
            _cfg = _load_yaml(path)
            _m = ((_cfg.get("task") or {}).get("model") or {})
            bm.model = _m.get("class") or ""
            bm.model_module = _m.get("module_path") or ""
        except Exception:
            pass
        out.append(bm)
    # 同名 slug（例如同名文件在不同目录）只保留第一个，避免互相覆盖
    seen: Dict[str, Benchmark] = {}
    for bm in out:
        seen.setdefault(bm.slug, bm)
    return sorted(seen.values(), key=lambda b: b.slug)


def _load_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("需要 pyyaml 才能读取 qlib 配置（pip install pyyaml）")
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict):
        raise ValueError("%s 顶层不是对象" % path)
    return _normalize(doc)


def _normalize(obj: Any) -> Any:
    """递归把 YAML 解析出来的特殊类型转成节点属性可用的形式。

    两件事：

    1. **日期转字符串**。``start_time: 2008-01-01`` 在 YAML 里会被解析成
       ``datetime.date`` 对象，而节点属性存的是文本；不转的话写进模板后
       类型不一致，下游还得靠隐式 ``str()`` 兜。
    2. **重建容器，切断对象共享**。官方配置里同一个日期对象会在多处出现
       （如 ``data_handler_config.start_time`` 与 ``market`` 同时被引用），
       共享引用会让 YAML 输出**锚点**（``&id001`` / ``*id001``）——
       虽然合法，但生成的模板可读性差、也容易让别的工具解析出错。
    """
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    if isinstance(obj, datetime.datetime):
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(obj, datetime.date):
        return obj.strftime("%Y-%m-%d")
    return obj


class _NoAliasDumper(yaml.SafeDumper if yaml else object):  # type: ignore[misc]
    """禁止输出 YAML 锚点/别名。

    默认 dumper 遇到「同一个对象被多处引用」就生成 ``&id001`` / ``*id001``。
    生成的模板是给人看、给人改的，锚点只会造成困惑。
    """

    def ignore_aliases(self, data):        # noqa: D102
        return True


def _seg(cfg: Dict[str, Any], key: str, idx: int) -> Any:
    """取 ``task.dataset.kwargs.segments.<key>[idx]``，取不到返回 None。"""
    segs = (((cfg.get("task") or {}).get("dataset") or {}).get("kwargs") or {}).get("segments") or {}
    v = segs.get(key)
    if isinstance(v, (list, tuple)) and len(v) > idx:
        return v[idx]
    return None


def convert(bm: Benchmark, provider_uri: Optional[str] = None
            ) -> Tuple[Dict[str, Any], List[str]]:
    """把官方配置转成 RockXQlib 流水线文档。

    返回 ``(pipeline_doc, notes)``。``notes`` 是需要人看一眼的提示
    （无法映射的字段、默认值替换等），会写进生成文件的注释里。
    """
    cfg = _load_yaml(bm.src)
    notes: List[str] = []

    qinit = cfg.get("qlib_init") or {}
    market = cfg.get("market") or ""
    handler_cfg = dict(cfg.get("data_handler_config") or {})
    task = cfg.get("task") or {}
    ds_kwargs = ((task.get("dataset") or {}).get("kwargs") or {})
    ds_handler = ds_kwargs.get("handler") or {}
    model_cfg = task.get("model") or {}
    pa = cfg.get("port_analysis_config") or {}
    st_cfg = pa.get("strategy") or {}
    bt_cfg = pa.get("backtest") or {}

    # ---- init ----
    uri = provider_uri or qinit.get("provider_uri") or ""
    if provider_uri:
        notes.append("provider_uri 已替换为本机数据目录：%s" % provider_uri)
    elif uri:
        notes.append("provider_uri 沿用官方配置：%s"
                     "（若本机没有该目录，请改用本机数据目录）" % uri)
    init_props: Dict[str, Any] = {}
    if uri:
        init_props["provider_uri"] = uri
    if qinit.get("region"):
        init_props["region"] = qinit["region"]

    # ---- data ----
    data_props: Dict[str, Any] = {}
    inst = handler_cfg.get("instruments") or market
    if inst:
        data_props["instruments"] = inst
    if handler_cfg.get("start_time"):
        data_props["start_time"] = handler_cfg["start_time"]
    if handler_cfg.get("end_time"):
        data_props["end_time"] = handler_cfg["end_time"]

    # ---- dataset ----
    ds_props: Dict[str, Any] = {}
    if ds_handler.get("class"):
        ds_props["handler_class"] = ds_handler["class"]
    if ds_handler.get("module_path"):
        ds_props["module_path"] = ds_handler["module_path"]
    if inst:
        ds_props["instruments"] = inst
    # 官方 data_handler_config 原样传给 handler（含 fit_start/fit_end）
    if handler_cfg:
        ds_props["handler_kwargs"] = handler_cfg
        unknown = sorted(set(handler_cfg) - _KNOWN_HANDLER_KEYS)
        if unknown:
            notes.append("handler_kwargs 含本工具未显式声明的键（原样透传，通常没问题）：%s"
                         % ", ".join(unknown))
    for key, a, b in (("train", "train_start", "train_end"),
                      ("valid", "valid_start", "valid_end"),
                      ("test", "test_start", "test_end")):
        s, e = _seg(cfg, key, 0), _seg(cfg, key, 1)
        if s:
            ds_props[a] = str(s)
        if e:
            ds_props[b] = str(e)

    # ---- model ----
    model_props: Dict[str, Any] = {}
    if model_cfg.get("class"):
        model_props["model_class"] = model_cfg["class"]
        bm.model = model_cfg["class"]
    if model_cfg.get("module_path"):
        model_props["module_path"] = model_cfg["module_path"]
        bm.model_module = model_cfg["module_path"]
    if model_cfg.get("kwargs"):
        model_props["model_params"] = model_cfg["kwargs"]

    # ---- strategy ----
    st_props: Dict[str, Any] = {}
    if st_cfg.get("class"):
        st_props["strategy_class"] = st_cfg["class"]
    if st_cfg.get("module_path"):
        st_props["module_path"] = st_cfg["module_path"]
    st_kw = dict(st_cfg.get("kwargs") or {})
    sig = st_kw.pop("signal", None)
    if sig:
        st_props["signal"] = sig
    if st_kw:
        st_props["strategy_params"] = st_kw

    # ---- backtest ----
    bt_props: Dict[str, Any] = {}
    if bt_cfg.get("start_time"):
        bt_props["start_time"] = str(bt_cfg["start_time"])
    if bt_cfg.get("end_time"):
        bt_props["end_time"] = str(bt_cfg["end_time"])
    if bt_cfg.get("account") is not None:
        bt_props["initial_capital"] = bt_cfg["account"]
    if bt_cfg.get("benchmark"):
        bt_props["benchmark"] = bt_cfg["benchmark"]
    if bt_cfg.get("exchange_kwargs"):
        bt_props["exchange_kwargs"] = bt_cfg["exchange_kwargs"]

    # ---- 记录未映射的顶层键，避免静默丢弃 ----
    known_top = {"qlib_init", "market", "benchmark", "data_handler_config",
                 "port_analysis_config", "task"}
    extra_top = sorted(set(cfg) - known_top)
    if extra_top:
        notes.append("官方配置里这些顶层键未映射（本工具不使用）：%s" % ", ".join(extra_top))

    def _step(t: str, props: Dict[str, Any]) -> Dict[str, Any]:
        return {"type": t, "props": props} if props else {"type": t}

    # 源文件路径只用于注释。**不能假定它一定在项目目录下** ——
    # 用户可以指向任意 benchmarks 目录（测试里就是临时目录），
    # 那种情况下 relative_to 会抛 ValueError。
    try:
        src_label = bm.src.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        src_label = bm.src.as_posix()

    doc: Dict[str, Any] = {
        "name": bm.slug,
        "title": bm.title,
        "source": "qlib 官方基准: %s" % src_label,
        "steps": [
            _step("init", init_props),
            _step("data", data_props),
            _step("dataset", ds_props),
            _step("model", model_props),
            _step("strategy", st_props),
            _step("backtest", bt_props),
        ],
    }
    return doc, notes


_HEADER = """\
# {title}
# 由 qlib 官方基准配置自动导入，**模型超参与官方一致**（可与论文结果比对）
# 源文件: {src}
#
# 运行:      python -m pipeline run pipelines/{slug}.yaml --backend dry   # 先演练接线
#            python -m pipeline run pipelines/{slug}.yaml                # 真跑（需本机有数据）
# 导入画布:  GUI「文件 → 导入工作流(JSON)」或 python -m pipeline export pipelines/{slug}.yaml out.json
#
# 生成命令:  python -m pipeline import-benchmarks
"""


def to_yaml(doc: Dict[str, Any], notes: Optional[List[str]] = None) -> str:
    """渲染成带说明注释的 YAML 文本（供人阅读，也便于手工微调）。"""
    if yaml is None:
        raise RuntimeError("需要 pyyaml（pip install pyyaml）")
    head = _HEADER.format(title=doc.get("title") or doc.get("name", ""),
                          src=doc.get("source", ""), slug=doc.get("name", ""))
    if notes:
        head += "#\n# 注意:\n"
        for n in notes:
            head += "#   - %s\n" % n
    # title/source 只用于注释，不进 YAML（避免校验器报未知键）
    body = {k: v for k, v in doc.items() if k not in ("title", "source")}
    return head + "\n" + yaml.dump(body, Dumper=_NoAliasDumper, allow_unicode=True,
                                   sort_keys=False, default_flow_style=False, width=100)


def dump(bm: Benchmark, out_dir: Optional[Path] = None, provider_uri: Optional[str] = None,
         overwrite: bool = False) -> Path:
    """转换并写盘，返回生成的文件路径。已存在且 ``overwrite=False`` 时跳过。"""
    out = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    dest = out / ("%s.yaml" % bm.slug)
    if dest.exists() and not overwrite:
        return dest
    doc, notes = convert(bm, provider_uri)
    dest.write_text(to_yaml(doc, notes), encoding="utf-8", newline="\n")
    return dest


def import_all(root: Optional[Path] = None, out_dir: Optional[Path] = None,
               provider_uri: Optional[str] = None, overwrite: bool = False,
               limit: Optional[int] = None
               ) -> List[Tuple[Benchmark, Path]]:
    """批量导入。返回 ``[(benchmark, 生成路径), ...]``。

    ``provider_uri`` 留空时自动用 ``core.qlib_paths`` 探测本机数据目录 ——
    这样导入的模板开箱可用，而不是指向不存在的 ``~/.qlib/...``。
    """
    if provider_uri is None:
        try:
            from core.qlib_paths import get_default_provider_uri
            provider_uri = get_default_provider_uri()
        except Exception:
            provider_uri = None
    bms = discover(root)
    if limit:
        bms = bms[:limit]
    return [(bm, dump(bm, out_dir, provider_uri, overwrite)) for bm in bms]
