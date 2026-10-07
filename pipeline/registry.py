# -*- coding: utf-8 -*-
"""qlib 模型 / 策略类注册表：AST 静态扫描，**不导入 qlib**。

为什么需要这个模块
------------------
模型节点和策略节点只有两个文本框：「类名」和「module_path」。三个问题：

1. **填错要到运行时才报错**。类名写错 → ``ModuleNotFoundError: No module
   named 'qlib.contrib.model.pytorch_lstmm'``，或者更糟：``**kwargs`` 把
   拼错的参数静静吞掉，跑完才发觉指标不对。
2. **类名有歧义**。``LSTM`` 同时存在于 ``pytorch_lstm`` 和 ``pytorch_lstm_ts``
   两个模块里（``ALSTM`` / ``GRU`` / ``GATs`` / ``TCN`` / ``TransformerModel``
   / ``LocalformerModel`` 同理）。光填类名无法确定用哪个。
3. **没人知道有哪些类可用**。qlib 自带 32 个模型、7 个策略，官方基准
   （``examples/benchmarks/``）还给出了「类名 + 模块 + 超参」的权威组合，
   但这些信息此前只散落在源码里。

本模块用 ``ast`` 直接读源码，得到三样东西：

- **有哪些类**：32 个模型 / 7 个策略（含官方基准之外的 ``TFTModel``）
- **类在哪个模块**：用来补 ``module_path``，并解决同名歧义
- **``__init__`` 的参数名与必填性**：用来校验参数名拼错 / 漏填必填项

**为什么坚持不 import**：``qlib/contrib/model`` 下几乎每个模块都
``import torch``，导入一次要几秒并吃几百 MB 内存；``ast`` 解析只要毫秒级。
而且 CI / 服务器上可能没装 torch，注册表在这些环境里也必须能用
（``pipeline.lint`` 会在每次 ``prepare()`` 时调用它）。

权威配对来自官方基准
--------------------
``examples/benchmarks/**/workflow_config*.yaml`` 里的
``task.model.module_path`` + ``class`` 是 **qlib 官方验证过**的组合，
比任何猜测都可靠。所以同名歧义时优先采用基准里出现过的那个，
并在列表里标出 ``★``（表示这条组合被官方基准验证过）。
"""
from __future__ import annotations

import ast
import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL = "model"
STRATEGY = "strategy"

# 扫描来源：(相对目录, 模块前缀, 类别)
_SOURCES: Tuple[Tuple[str, str, str], ...] = (
    ("qlib/contrib/model", "qlib.contrib.model", MODEL),
    ("qlib/contrib/strategy", "qlib.contrib.strategy", STRATEGY),
)

# 官方基准里还有独立实现的模型，不在 qlib 包内，模块名就是文件名。
# 之所以单独列出而不递归扫 examples/：那里的 .py 大多是辅助脚本，
# 递归扫描会混进一堆与建模无关的类。
_EXTRA_FILES: Tuple[Tuple[str, str, str], ...] = (
    ("examples/benchmarks/TFT/tft.py", "tft", MODEL),
)

_BENCHMARK_GLOB = "examples/benchmarks/**/workflow_config*.yaml"

# 类别 -> (判定方法名集合, 节点类型, 类名属性, 参数属性列表)
_KIND_RULES: Dict[str, Dict[str, Any]] = {
    MODEL: {
        "methods": ("fit", "predict"),      # 两个都要有才算模型
        "node_type": "qlib.core.model",
        "class_prop": "model_class",
        "module_prop": "module_path",
        # 简化路径的参数在 model_params；完整路径在 model_kwargs
        "param_props": ("model_params", "model_kwargs"),
    },
    STRATEGY: {
        "methods": ("generate_trade_decision",),
        "node_type": "qlib.core.strategy",
        "class_prop": "strategy_class",
        "module_prop": "module_path",
        "param_props": ("strategy_params", "strategy_kwargs"),
    },
}


# --------------------------------------------------------------------------
# 数据结构
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Param:
    """``__init__`` 的一个形参。"""

    name: str
    kind: str        # 'pos' | 'kwonly' | 'vararg' | 'kwarg'
    required: bool   # 无默认值（vararg/kwarg 恒为 False）

    def __str__(self) -> str:
        if self.kind == "vararg":
            return "*" + self.name
        if self.kind == "kwarg":
            return "**" + self.name
        return self.name if self.required else "%s=%s" % (self.name, "?")


@dataclass(frozen=True)
class ClassInfo:
    """一个可用的模型 / 策略类。"""

    name: str                       # 'LGBModel'
    kind: str                       # 'model' | 'strategy'
    module: str                     # 'qlib.contrib.model.gbdt'
    file: str                       # 'qlib/contrib/model/gbdt.py'（相对项目根）
    bases: Tuple[str, ...] = ()
    params: Tuple[Param, ...] = ()
    has_init: bool = True           # 类里是否显式定义了 __init__
    doc: str = ""                   # docstring 首行
    benchmarks: Tuple[str, ...] = ()  # 用到该组合的官方基准 slug
    aliases: Tuple[str, ...] = ()   # 还能通过哪些模块路径访问到（包的再导出）
    inherited: bool = False         # 必需方法来自基类（由包 __init__ 公开）
    extra_params: Tuple[str, ...] = ()  # 官方基准用过的超参名（**kwargs 白名单）

    # ---- 派生属性 ----

    @property
    def verified(self) -> bool:
        """该「类名 + 模块」组合是否被官方基准使用过。"""
        return bool(self.benchmarks)

    @property
    def all_modules(self) -> Tuple[str, ...]:
        """能访问到该类的全部模块路径（本文件 + 包的再导出）。

        官方基准里策略写的是 ``qlib.contrib.strategy``（包），而类其实定义在
        ``qlib.contrib.strategy.signal_strategy``；两个都合法，校验时都要认。
        """
        return (self.module,) + tuple(m for m in self.aliases if m != self.module)

    @property
    def takes_any_kw(self) -> bool:
        """是否有 ``**kwargs`` —— 有的话未知参数会被静默吞掉。"""
        return any(p.kind == "kwarg" for p in self.params)

    @property
    def known_params(self) -> List[str]:
        return [p.name for p in self.params if p.kind in ("pos", "kwonly")]

    @property
    def required_params(self) -> List[str]:
        return [p.name for p in self.params if p.required]

    def signature(self) -> str:
        return ", ".join(str(p) for p in self.params) or "（无参数）"

    def __str__(self) -> str:
        star = " ★" if self.verified else ""
        return "%s  ->  %s%s" % (self.name, self.module, star)


@dataclass
class Registry:
    """扫描结果。用 :func:`build` 构造，一般不用直接实例化。"""

    classes: Tuple[ClassInfo, ...] = ()
    root: Path = PROJECT_ROOT

    # ---- 查询 ----

    def of_kind(self, kind: str) -> List[ClassInfo]:
        return [c for c in self.classes if c.kind == kind]

    def by_name(self, name: str, kind: Optional[str] = None) -> List[ClassInfo]:
        """按类名找候选。同名类会返回多条（这正是需要 module_path 的原因）。"""
        name = (name or "").strip()
        if not name:
            return []
        return [c for c in self.classes
                if c.name == name and (kind is None or c.kind == kind)]

    def names(self, kind: str) -> List[str]:
        return sorted({c.name for c in self.of_kind(kind)})

    def ambiguous_names(self, kind: str) -> List[str]:
        """在多个模块里重复出现的类名。"""
        seen: Dict[str, int] = {}
        for c in self.of_kind(kind):
            seen[c.name] = seen.get(c.name, 0) + 1
        return sorted(n for n, k in seen.items() if k > 1)

    def preferred(self, name: str, kind: str,
                  module_path: str = "") -> Optional[ClassInfo]:
        """在候选里挑一个「最可能想要的」。

        优先级：显式给的 module_path 匹配 > 官方基准用过 > 唯一候选。
        挑不出（多个候选都没被基准验证过）时返回 ``None``，让调用方
        如实报告歧义，而不是猜一个。
        """
        cands = self.by_name(name, kind)
        if not cands:
            return None
        if module_path:
            exact = [c for c in cands if module_path.strip() in c.all_modules]
            if exact:
                return exact[0]
        verified = [c for c in cands if c.verified]
        if len(verified) == 1:
            return verified[0]
        if len(cands) == 1:
            return cands[0]
        return None

    def module_of(self, name: str, kind: str, module_path: str = "") -> str:
        """类名 -> 该填的 ``module_path``。

        已经是合法值（含包的再导出路径）时**原样返回**，避免把官方模板里
        正确写着 ``qlib.contrib.strategy`` 的地方改成别的写法；
        只有缺失或对不上时才给出补全值。
        """
        cur = (module_path or "").strip()
        if cur and any(cur in c.all_modules for c in self.by_name(name, kind)):
            return cur
        c = self.preferred(name, kind, cur)
        return c.module if c else ""

    def suggest(self, name: str, kind: str, n: int = 3) -> List[str]:
        """类名拼错时的候选（按相似度）。"""
        return difflib.get_close_matches(
            (name or "").strip(), self.names(kind), n=n, cutoff=0.5)

    # ---- 校验 ----

    def check_class(self, name: str, kind: str, module_path: str = "",
                    where: str = "", suggest_missing: bool = False
                    ) -> Tuple[List[str], List[str]]:
        """校验「类名 + module_path」这一对是否自洽。返回 ``(errors, warnings)``。

        ``suggest_missing=True`` 时，类名唯一但没填 module_path 也会给一条提示
        （默认关闭 —— 那种情况运行时不会出错，每次跑都提示就是噪音；
        要补全用 :func:`autofill_workflow`）。
        """
        errors: List[str] = []
        warns: List[str] = []
        label = _label(kind)
        pre = (where + ": ") if where else ""
        name = (name or "").strip()
        module_path = (module_path or "").strip()

        if not name:
            errors.append("%s%s未填写（可选值见 python -m pipeline %s）"
                          % (pre, label, _cmd(kind)))
            return errors, warns

        cands = self.by_name(name, kind)
        if not cands:
            hint = self.suggest(name, kind)
            extra = "；是否想写 %s？" % " / ".join(hint) if hint else ""
            errors.append("%s%s「%s」不在注册表里（共 %d 个类名，"
                          "python -m pipeline %s 可列出全部）%s"
                          % (pre, label, name, len(self.names(kind)),
                             _cmd(kind), extra))
            return errors, warns

        # 合法模块路径（含包的再导出，如 qlib.contrib.strategy）
        modules = sorted({m for c in cands for m in c.all_modules})

        # module_path 填了，但和类名对不上 —— 这是运行时必炸的组合
        if module_path:
            if module_path not in modules:
                # 该模块里有没有这个类？没有就是彻底对不上
                errors.append(
                    "%smodule_path「%s」里没有 %s「%s」；它实际在 %s"
                    % (pre, module_path, label, name, " 或 ".join(modules)))
            return errors, warns

        # 没填 module_path
        if len(cands) > 1:
            verified = [c for c in cands if c.verified]
            if len(verified) == 1:
                best = verified[0]
                warns.append("[警告] %s%s「%s」在多个模块里都有，建议补上 "
                             "module_path: %s（官方基准用的就是它）%s"
                             % (pre, label, name, best.module, _ts_hint(modules)))
            elif verified:
                warns.append("[警告] %s%s「%s」在多个模块里都有，且都被官方基准用过，"
                             "必须补 module_path 才能确定（候选: %s）%s"
                             % (pre, label, name,
                                " / ".join(c.module for c in verified),
                                _ts_hint(modules)))
            else:
                warns.append("[警告] %s%s「%s」在多个模块里都有，必须补 module_path"
                             "（候选: %s）%s" % (pre, label, name, " / ".join(modules),
                                                _ts_hint(modules)))
        else:
            if suggest_missing:
                warns.append("[警告] %s%s「%s」可补上 module_path: %s（留空时用默认值，"
                             "类名重复或有歧义时会取错）"
                             % (pre, label, name, cands[0].module))
        return errors, warns

    def check_kwargs(self, name: str, kind: str, kwargs: Dict[str, Any],
                     module_path: str = "", where: str = "",
                     prop: str = "") -> Tuple[List[str], List[str]]:
        """校验参数字典的键是否对得上 ``__init__`` 签名。

        「已知参数」= ``__init__`` 形参 ∪ **官方基准用过的参数名**。后者不可省：
        qlib 的模型基本都带 ``**kwargs`` 转发给底层库（lightgbm 的
        ``num_leaves``、xgboost 的 ``eta``、catboost 的 ``grow_policy`` …），
        只看签名会把它们全判成拼错 —— 实测会造成 124 条假警告。

        严重程度按后果分：
        - 漏填必填参数        -> **错误**（运行时必炸）
        - 未知参数且无 ``**kwargs`` -> **错误**（``TypeError: unexpected keyword``）
        - 未知参数但有 ``**kwargs`` -> **警告**（可能拼错，也可能真是底层库参数）
        """
        errors: List[str] = []
        warns: List[str] = []
        pre = (where + ": ") if where else ""
        pname = prop or _KIND_RULES[kind]["param_props"][0]

        cands = self.by_name(name, kind)
        info = self.preferred(name, kind, module_path)
        if info is not None and info.has_init:
            pool = [info]
        else:
            # 歧义未定（同名类且都没填 module_path）：对**所有候选都认不出**的
            # 键才报，且不检查必填项 —— 不知道是哪个类，报必填就是瞎猜。
            pool = [c for c in cands if c.has_init]
            if not pool:
                return errors, warns

        known: set = set()
        extra: set = set()
        for c in pool:
            known.update(c.known_params)
            extra.update(c.extra_params)
        vocabulary = sorted(known | extra)

        if info is not None:
            missing = [p for p in info.required_params if p not in kwargs]
            if missing:
                errors.append("%s%s 缺少必填参数 %s（%s.__init__ 要求 %s）"
                              % (pre, pname, "、".join(missing), info.name,
                                 "、".join(info.required_params)))

        unknown = sorted(set(kwargs) - known - extra)
        # 没有 **kwargs 的类传未知参数会直接 TypeError，是硬错误
        strict = info is not None and not info.takes_any_kw
        for k in unknown:
            hit = difflib.get_close_matches(k, vocabulary, n=1, cutoff=0.7)
            tail = "，是否想写「%s」？" % hit[0] if hit else ""
            if strict:
                errors.append("%s%s 里的「%s」不是 %s 的参数%s"
                              "（该类没有 **kwargs，传入会直接 TypeError）"
                              % (pre, pname, k, info.name, tail))
            else:
                warns.append("[警告] %s%s 里的「%s」不在已知参数表里%s"
                             "（%s 有 **kwargs，会转发给底层库；"
                             "若确属底层库参数可忽略）"
                             % (pre, pname, k, tail, pool[0].name))
        return errors, warns

    def check_node(self, node_type: str, props: Dict[str, Any],
                   node_id: str = "") -> Tuple[List[str], List[str]]:
        """对模型节点 / 策略节点做完整检查（lint 的入口）。

        ``props`` 应当是**合并了默认值之后**的属性表，否则「只改了
        module_path 没写类名」这类写法会漏检。
        """
        kind = _kind_of_node(node_type)
        if kind is None:
            return [], []
        rule = _KIND_RULES[kind]
        errors, warns = self.check_class(
            props.get(rule["class_prop"], ""), kind,
            props.get(rule["module_prop"], ""), where=node_id)
        kwargs = _merged_params(props, rule["param_props"])
        if kwargs is None:
            return errors, warns      # 参数属性不是合法 JSON，交给 lint 报
        kerrs, kwarns = self.check_kwargs(
            props.get(rule["class_prop"], ""), kind, kwargs,
            props.get(rule["module_prop"], ""), where=node_id)
        return errors + kerrs, warns + kwarns

    # ---- 展示 ----

    def catalog(self, kind: str, only_verified: bool = False) -> str:
        """给 LLM 看的紧凑清单：``类名 -> 模块``（附参数名）。"""
        lines: List[str] = []
        for c in sorted(self.of_kind(kind), key=lambda x: (not x.verified, x.name)):
            if only_verified and not c.verified:
                continue
            star = "★" if c.verified else " "
            lines.append("%s %-22s %s" % (star, c.name, c.module))
            if c.params:
                lines.append("     参数: %s" % ", ".join(str(p) for p in c.params))
        return "\n".join(lines)

    def format_list(self, kind: str) -> str:
        """CLI 用的分组清单。"""
        items = sorted(self.of_kind(kind), key=lambda x: (x.name, x.module))
        if not items:
            return "（没有扫描到任何%s）" % _label(kind)
        amb = set(self.ambiguous_names(kind))
        out = ["%s（共 %d 个，★ = 官方基准验证过的组合）" % (_label(kind), len(items)), ""]
        width = max(len(c.name) for c in items)
        for c in items:
            flag = "★" if c.verified else " "
            tail = "  ⚠ 同名" if c.name in amb else ""
            out.append("  %s %-*s  %s%s" % (flag, width, c.name, c.module, tail))
        if amb:
            out += ["", "同名类（必须填 module_path 才能确定）: %s"
                    % "、".join(sorted(amb))]
        out += ["", "用法: python -m pipeline %s --class <类名>   查看某个类的完整签名"
                % _cmd(kind)]
        return "\n".join(out)

    def format_class(self, name: str, kind: str) -> str:
        """CLI 用的单类详情。"""
        cands = self.by_name(name, kind)
        if not cands:
            hint = self.suggest(name, kind)
            tail = "；是否想写 %s？" % " / ".join(hint) if hint else ""
            return "注册表里没有 %s「%s」%s" % (_label(kind), name, tail)
        blocks: List[str] = []
        for c in cands:
            head = "%s「%s」" % (_label(kind), c.name)
            if c.verified:
                head += "   ★ 官方基准: %s" % ", ".join(c.benchmarks)
            lines = [head,
                     "  module_path : %s" % c.module,
                     "  源码        : %s" % c.file]
            if c.bases:
                lines.append("  基类        : %s" % ", ".join(c.bases))
            if c.doc:
                lines.append("  说明        : %s" % c.doc)
            lines.append("  __init__    : %s" % c.signature())
            if c.required_params:
                lines.append("  必填参数    : %s" % "、".join(c.required_params))
            if c.takes_any_kw:
                lines.append("  ⚠ 该类接受 **kwargs —— 拼错的参数会被静默忽略")
            blocks.append("\n".join(lines))
        return ("\n\n" + "-" * 60 + "\n\n").join(blocks)


# --------------------------------------------------------------------------
# 构造
# --------------------------------------------------------------------------

def _label(kind: str) -> str:
    return "模型" if kind == MODEL else "策略"


def _cmd(kind: str) -> str:
    return "models" if kind == MODEL else "strategies"


def _kind_of_node(node_type: str) -> Optional[str]:
    for kind, rule in _KIND_RULES.items():
        if rule["node_type"] == node_type:
            return kind
    return None


def _ts_hint(modules: Sequence[str]) -> str:
    """同名歧义时，指出 ``*_ts`` 变体的语义差别（用户最难自己判断的一点）。"""
    ts = [m for m in modules if m.endswith("_ts")]
    if not ts or len(ts) == len(modules):
        return ""
    return ("。注意：%s 结尾的是「时间序列」变体，需要 TSDatasetH 数据集，"
            "普通 DatasetH 会报错" % "、".join(m.rsplit(".", 1)[-1] for m in ts))


def _merged_params(props: Dict[str, Any], prop_names: Sequence[str]) -> Optional[Dict[str, Any]]:
    """把节点的参数属性合并成一个 dict（后者覆盖前者）。

    属性值是字符串（JSON）或 dict（YAML 直接写对象）都可能，统一处理。
    任何一个是非法 JSON 就返回 ``None`` —— 那是 ``lint`` 的职责，不在这里重复报。
    """
    out: Dict[str, Any] = {}
    for key in prop_names:
        raw = props.get(key)
        if raw is None or raw == "":
            continue
        if isinstance(raw, dict):
            out.update(raw)
            continue
        if isinstance(raw, str):
            import json
            try:
                val = json.loads(raw)
            except ValueError:
                return None
            if isinstance(val, dict):
                out.update(val)
    return out


def _init_params(cls: ast.ClassDef) -> Tuple[bool, Tuple[Param, ...]]:
    """取 ``__init__`` 形参。返回 ``(是否显式定义, 参数表)``。"""
    for m in cls.body:
        if not (isinstance(m, ast.FunctionDef) and m.name == "__init__"):
            continue
        a = m.args
        positional = [x.arg for x in a.args if x.arg != "self"]
        ndef = len(a.defaults)
        params: List[Param] = []
        for i, nm in enumerate(positional):
            params.append(Param(nm, "pos", required=i < len(positional) - ndef))
        for arg, dflt in zip(a.kwonlyargs, a.kw_defaults):
            # 注意 a.kwonlyargs 的元素是 ast.arg 而不是 str（和 a.args 一样）
            params.append(Param(arg.arg, "kwonly", required=dflt is None))
        if a.vararg:
            params.append(Param(a.vararg.arg, "vararg", False))
        if a.kwarg:
            params.append(Param(a.kwarg.arg, "kwarg", False))
        return True, tuple(params)
    return False, ()


def _doc_line(cls: ast.ClassDef) -> str:
    doc = ast.get_docstring(cls) or ""
    for line in doc.splitlines():
        line = line.strip()
        if line:
            return line[:110]
    return ""


def _parse_file(path: Path) -> Optional[ast.Module]:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _methods(cls: ast.ClassDef) -> set:
    return {m.name for m in cls.body if isinstance(m, ast.FunctionDef)}


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return "?"


# 明显不该出现在「可选模型/策略」清单里的基类（内部网络层、工具类）
_BASE_BLOCKLIST = {"Module", "Meter", "Dataset", "DatasetH"}


def _selectable(cls: ast.ClassDef) -> bool:
    """基类看着像内部实现（``nn.Module`` 之类）就排除。

    这条主要防 ``qlib.contrib.model.__init__`` 里的
    ``from .pytorch_sfm import SFM_Model`` —— 它是网络层不是模型。
    """
    for b in cls.bases:
        if _unparse(b).rsplit(".", 1)[-1] in _BASE_BLOCKLIST:
            return False
    return True


def _reexports(init_path: Path, package: str) -> Tuple[Dict[str, str], List[str]]:
    """解析包 ``__init__.py`` 的再导出。

    返回 ``({导出名: 来源模块}, [通配来源模块, ...])``。只认相对导入
    （``from .x import Y``）与指向本包前缀的绝对导入。
    """
    tree = _parse_file(init_path) if init_path.is_file() else None
    if tree is None:
        return {}, []
    names: Dict[str, str] = {}
    wild: List[str] = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.ImportFrom):
            continue
        if n.level:
            src = package + ("." + n.module if n.module else "")
        elif n.module and n.module.startswith(package + "."):
            src = n.module
        else:
            continue
        for a in n.names:
            if a.name == "*":
                if src not in wild:
                    wild.append(src)
            else:
                names[a.asname or a.name] = src
    return names, wild


def _scan_source(d: Path, prefix: str, kind: str, root: Path) -> List[ClassInfo]:
    """扫一个来源目录。

    收录规则（两条取并集）：
    1. **自己定义了必需方法** —— 如 ``LGBModel`` 定义了 fit / predict；
    2. **被包的 ``__init__.py`` 再导出** —— 如 ``EnhancedIndexingStrategy``
       的 ``generate_trade_decision`` 继承自基类、自己没写，但包把它作为
       公开策略导出，那它就是可用的。

    第 2 条同时用来识别「包路径也算合法 module_path」：
    官方基准里策略写的是 ``qlib.contrib.strategy``（包），而类定义在
    ``qlib.contrib.strategy.signal_strategy`` —— 两个都得认，
    否则 48 个官方模板会被误判成 module_path 写错。
    """
    if not d.is_dir():
        return []
    need = _KIND_RULES[kind]["methods"]
    modules: Dict[str, Tuple[str, ast.Module]] = {}
    for f in sorted(d.glob("*.py")):
        if f.name == "__init__.py":
            continue
        tree = _parse_file(f)
        if tree is not None:
            modules["%s.%s" % (prefix, f.stem)] = (_rel(f, root), tree)

    exports, wild = _reexports(d / "__init__.py", prefix)

    out: List[ClassInfo] = []
    for mod, (relpath, tree) in modules.items():
        exported_here = mod in wild
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef):
                continue
            direct = all(m in _methods(cls) for m in need)
            exported = exported_here or exports.get(cls.name) == mod
            if not (direct or exported):
                continue
            if not _selectable(cls):
                continue
            has_init, params = _init_params(cls)
            aliases = (prefix,) if exported else ()
            out.append(ClassInfo(
                name=cls.name, kind=kind, module=mod, file=relpath,
                bases=tuple(_unparse(b) for b in cls.bases),
                params=params, has_init=has_init, doc=_doc_line(cls),
                aliases=aliases, inherited=exported and not direct))
    return out


def _scan_single(path: Path, module: str, kind: str, root: Path) -> List[ClassInfo]:
    """扫单个文件（用于 :data:`_EXTRA_FILES` 里不在包内的模型）。"""
    tree = _parse_file(path)
    if tree is None:
        return []
    need = _KIND_RULES[kind]["methods"]
    out: List[ClassInfo] = []
    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef):
            continue
        if not all(m in _methods(cls) for m in need) or not _selectable(cls):
            continue
        has_init, params = _init_params(cls)
        out.append(ClassInfo(
            name=cls.name, kind=kind, module=module, file=_rel(path, root),
            bases=tuple(_unparse(b) for b in cls.bases),
            params=params, has_init=has_init, doc=_doc_line(cls)))
    return out


def _benchmark_pairs(root: Path) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """读官方基准，得到 ``{kind: {类名: [{"module","slug","params"}, ...]}}``。

    除了「类名 + 模块」的权威配对，这里还顺手收集**该类在官方基准里用过的
    超参名**。这是数据驱动的白名单：qlib 的模型几乎都带 ``**kwargs``
    （把参数转发给 lightgbm / xgboost / catboost 等底层库），只看 ``__init__``
    签名会把 ``num_leaves``、``learning_rate`` 这类完全合法的参数误报成拼错 ——
    实测 49 个官方模板会因此产生 124 条假警告。

    没有 pyyaml 或读不出来时返回空 —— 注册表降级为「无权威配对」，其余照常。
    """
    try:
        import yaml
    except ImportError:
        return {}
    found: Dict[str, Dict[str, List[Dict[str, Any]]]] = {MODEL: {}, STRATEGY: {}}
    try:
        files = sorted(root.glob(_BENCHMARK_GLOB))
    except OSError:
        return {}
    for f in files:
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        slug = f.parent.name if f.parent.name != "benchmarks" else f.stem
        task = doc.get("task")
        model = task.get("model") if isinstance(task, dict) else None
        _add_pair(found[MODEL], model, slug)
        pa = doc.get("port_analysis_config")
        strat = pa.get("strategy") if isinstance(pa, dict) else None
        _add_pair(found[STRATEGY], strat, slug)
    return found


def _add_pair(bucket: Dict[str, List[Dict[str, Any]]], spec: Any, slug: str) -> None:
    if not isinstance(spec, dict):
        return
    cls = spec.get("class")
    if not isinstance(cls, str) or not cls:
        return
    mod = spec.get("module_path")
    kw = spec.get("kwargs")
    bucket.setdefault(cls, []).append({
        "module": mod if isinstance(mod, str) else "",
        "slug": slug,
        "params": sorted(kw) if isinstance(kw, dict) else [],
    })


def build(root: Path = PROJECT_ROOT, use_cache: bool = True) -> Registry:
    """扫描并构造注册表。结果按 ``root`` 缓存（lint 会频繁调用）。"""
    key = str(Path(root).resolve())
    if use_cache and key in _CACHE:
        return _CACHE[key]

    root = Path(root)
    found: List[ClassInfo] = []
    for rel_dir, prefix, kind in _SOURCES:
        found.extend(_scan_source(root / rel_dir, prefix, kind, root))
    for rel, module, kind in _EXTRA_FILES:
        p = root / rel
        if p.is_file():
            found.extend(_scan_single(p, module, kind, root))

    # 用官方基准补上「权威组合」与 slug（基准里 module_path 可能写包名，
    # 所以别名路径也要认），并收集基准用过的超参名作为白名单
    pairs = _benchmark_pairs(root)
    if pairs:
        enriched: List[ClassInfo] = []
        for c in found:
            slugs: set = set()
            extra: set = set()
            for ref in pairs.get(c.kind, {}).get(c.name, []):
                if ref["module"] in c.all_modules:
                    slugs.add(ref["slug"])
                    extra.update(ref["params"])
            enriched.append(_replace(c, benchmarks=tuple(sorted(slugs)),
                                     extra_params=tuple(sorted(extra))))
        found = enriched

    reg = Registry(classes=tuple(sorted(found, key=lambda c: (c.kind, c.name, c.module))),
                   root=root)
    if use_cache:
        _CACHE[key] = reg
    return reg


def _replace(c: ClassInfo, **kw) -> ClassInfo:
    data = {f: getattr(c, f) for f in
            ("name", "kind", "module", "file", "bases", "params",
             "has_init", "doc", "benchmarks", "aliases", "inherited",
             "extra_params")}
    data.update(kw)
    return ClassInfo(**data)


_CACHE: Dict[str, Registry] = {}


def clear_cache() -> None:
    _CACHE.clear()


# ---- 便捷入口 ----

def models(root: Path = PROJECT_ROOT) -> List[ClassInfo]:
    return build(root).of_kind(MODEL)


def strategies(root: Path = PROJECT_ROOT) -> List[ClassInfo]:
    return build(root).of_kind(STRATEGY)


def catalog_text(root: Path = PROJECT_ROOT, only_verified: bool = False) -> str:
    """给 LLM 的模型 / 策略清单（``assistant`` 的系统提示用）。"""
    reg = build(root)
    return ("可选模型（类名 -> module_path；★=官方基准验证过）:\n%s\n\n"
            "可选策略（类名 -> module_path）:\n%s"
            % (reg.catalog(MODEL, only_verified),
               reg.catalog(STRATEGY, only_verified)))


def autofill_workflow(wf: Dict[str, Any],
                      specs: Optional[Dict[str, Dict[str, Any]]] = None,
                      reg: Optional[Registry] = None) -> Tuple[Dict[str, Any], List[str]]:
    """补全模型 / 策略节点的 ``module_path``（不改动其它任何属性）。

    只在「能唯一确定」时补 —— 同名类且没有权威配对时保持原样，
    让 :meth:`Registry.check_class` 去如实报告歧义，而不是猜一个。

    返回 ``(新工作流, 变更说明列表)``；没有可补的项时原样返回（不复制）。
    """
    reg = reg or build()

    # 类名可能来自节点默认值，所以要合并 specs 的 defaults 才能判断
    nodes = wf.get("nodes") or []
    new_nodes: List[Dict[str, Any]] = []
    changes: List[str] = []
    touched = False

    for n in nodes:
        kind = _kind_of_node(n.get("type", ""))
        if kind is None:
            new_nodes.append(n)
            continue
        rule = _KIND_RULES[kind]
        defaults = ((specs or {}).get(n["type"], {}).get("defaults") or {})
        props = {**defaults, **(n.get("props") or {})}
        cls_name = str(props.get(rule["class_prop"]) or "").strip()
        cur = str(props.get(rule["module_prop"]) or "").strip()
        want = reg.module_of(cls_name, kind, cur)
        if not want or want == cur:
            new_nodes.append(n)
            continue
        # 只写回「节点自己声明的 props」，不要把 defaults 灌进去
        props_out = dict(n.get("props") or {})
        props_out[rule["module_prop"]] = want
        new_nodes.append({**n, "props": props_out})
        touched = True
        changes.append("%s: %s「%s」的 module_path %s -> %s"
                       % (n.get("id", "?"), _label(kind), cls_name,
                          cur or "(空)", want))

    if not touched:
        return wf, []
    return {**wf, "nodes": new_nodes}, changes
