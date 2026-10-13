# -*- coding: utf-8 -*-
"""模型 / 策略注册表的测试。

两部分：
1. **离线夹具**（临时目录里造一套假的 qlib 源码）—— 覆盖解析规则本身：
   哪些类该收、哪些该排除、包再导出怎么算、同名歧义怎么判、超参怎么校验。
   夹具让这些规则可被精确断言，不受真实 qlib 版本影响。
2. **对真实仓库的集成断言** —— 确认注册表在本项目里真的能用
   （找得到已安装或随仓库带上的 qlib 模型、LSTM 有歧义、
   官方模板的包路径写法不被误判）。没有 qlib 源码时这组测试跳过。

注意：全程不 import qlib。这正是本模块的设计约束 ——
``qlib/contrib/model`` 下几乎每个文件都 ``import torch``。
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline.registry import (MODEL, STRATEGY, Registry, autofill_workflow, build,
                               catalog_text, clear_cache)

# --------------------------------------------------------------------------
# 夹具：临时目录里的假 qlib
# --------------------------------------------------------------------------

_GBDT = '''
class LGBModel(ModelFT):
    """LightGBM 模型"""
    def __init__(self, loss=None, num_boost_round=100, **kwargs):
        pass
    def fit(self, dataset):
        pass
    def predict(self, dataset):
        pass
'''

_NN = '''
class FooNet(nn.Module):
    def __init__(self, hidden=64):
        pass
    def fit(self, dataset):
        pass
    def predict(self, dataset):
        pass
'''

_DUP_A = '''
class Dup(Model):
    """A 模块里的同名模型"""
    def __init__(self, a_param=1):
        pass
    def fit(self, dataset):
        pass
    def predict(self, dataset):
        pass
'''

_DUP_B = '''
class Dup(Model):
    """B 模块里的同名模型"""
    def __init__(self, b_param=2):
        pass
    def fit(self, dataset):
        pass
    def predict(self, dataset):
        pass
'''

# 完全没有基准背书、两个模块都有的同名类 -> 应当判为「无法确定」
_TWIN_A = '''
class Twin(Model):
    def __init__(self, x=1):
        pass
    def fit(self, dataset):
        pass
    def predict(self, dataset):
        pass
'''

_TWIN_B = '''
class Twin(Model):
    def __init__(self, y=2):
        pass
    def fit(self, dataset):
        pass
    def predict(self, dataset):
        pass
'''

_STRICT = '''
class Strict(Model):
    """没有 **kwargs 的模型 —— 传未知参数会 TypeError"""
    def __init__(self, alpha=0.1, fit_intercept=True):
        pass
    def fit(self, dataset):
        pass
    def predict(self, dataset):
        pass
'''

_SIG = '''
class Topk(BaseSignalStrategy):
    """Topk 策略"""
    def __init__(self, topk, n_drop=5, method_sell="bottom", **kwargs):
        pass
    def generate_trade_decision(self, execute_result=None):
        pass
'''

# 继承实现（自己没写 generate_trade_decision），靠包的 __init__ 公开
_INHERITED = '''
class Enhanced(WeightStrategyBase):
    """由基类提供 generate_trade_decision"""
    def __init__(self, topk=50, **kwargs):
        pass
'''

_BENCHMARK = """
task:
  model:
    class: Dup
    module_path: qlib.contrib.model.dup_a
    kwargs:
      a_param: 7
      loss: mse
port_analysis_config:
  strategy:
    class: Topk
    module_path: qlib.contrib.strategy
    kwargs:
      topk: 50
      n_drop: 5
"""


def _make_fake_qlib(root: Path) -> None:
    m = root / "qlib" / "contrib" / "model"
    s = root / "qlib" / "contrib" / "strategy"
    m.mkdir(parents=True)
    s.mkdir(parents=True)
    (m / "__init__.py").write_text(
        "from .gbdt import LGBModel\n"
        "from .nn import FooNet\n"          # 应当被排除（基类是 nn.Module）
        "from .dup_a import Dup\n",
        encoding="utf-8")
    (m / "gbdt.py").write_text(_GBDT, encoding="utf-8")
    (m / "nn.py").write_text(_NN, encoding="utf-8")
    (m / "dup_a.py").write_text(_DUP_A, encoding="utf-8")
    (m / "dup_b.py").write_text(_DUP_B, encoding="utf-8")
    (m / "twin_a.py").write_text(_TWIN_A, encoding="utf-8")
    (m / "twin_b.py").write_text(_TWIN_B, encoding="utf-8")
    (m / "strict.py").write_text(_STRICT, encoding="utf-8")

    (s / "__init__.py").write_text(
        "from .sig import Topk\n"
        "from .inherit import Enhanced\n",
        encoding="utf-8")
    (s / "sig.py").write_text(_SIG, encoding="utf-8")
    (s / "inherit.py").write_text(_INHERITED, encoding="utf-8")

    b = root / "examples" / "benchmarks" / "Demo"
    b.mkdir(parents=True)
    (b / "workflow_config_demo.yaml").write_text(_BENCHMARK, encoding="utf-8")


class RegistryFixtureTest(unittest.TestCase):
    """用临时目录里的假 qlib 精确验证解析规则。"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        _make_fake_qlib(cls.root)
        cls.reg: Registry = build(cls.root, use_cache=False)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    # ---- 收录规则 ----

    def test_collects_classes_defining_required_methods(self):
        names = {c.name for c in self.reg.of_kind(MODEL)}
        self.assertIn("LGBModel", names)
        self.assertIn("Dup", names)
        self.assertIn("Strict", names)

    def test_excludes_nn_module_subclasses(self):
        """``FooNet(nn.Module)`` 是网络层不是模型 —— 必须排除。"""
        self.assertNotIn("FooNet", {c.name for c in self.reg.of_kind(MODEL)})

    def test_collects_strategy_inheriting_the_method(self):
        """``Enhanced`` 没自己写 generate_trade_decision，但被包公开导出。"""
        names = {c.name for c in self.reg.of_kind(STRATEGY)}
        self.assertIn("Topk", names)
        self.assertIn("Enhanced", names)
        enhanced = self.reg.by_name("Enhanced", STRATEGY)[0]
        self.assertTrue(enhanced.inherited)
        self.assertFalse(self.reg.by_name("Topk", STRATEGY)[0].inherited)

    def test_package_reexport_becomes_alias(self):
        """``qlib.contrib.strategy`` 是合法 module_path（官方基准就这么写）。"""
        topk = self.reg.by_name("Topk", STRATEGY)[0]
        self.assertIn("qlib.contrib.strategy", topk.all_modules)
        self.assertIn("qlib.contrib.strategy.sig", topk.all_modules)

    def test_docstring_first_line_captured(self):
        self.assertEqual(self.reg.by_name("LGBModel", MODEL)[0].doc, "LightGBM 模型")

    def test_file_path_is_relative_to_root(self):
        self.assertEqual(self.reg.by_name("LGBModel", MODEL)[0].file,
                         "qlib/contrib/model/gbdt.py")

    # ---- 构造函数签名 ----

    def test_signature_marks_required_vs_optional(self):
        topk = self.reg.preferred("Topk", STRATEGY)
        self.assertEqual(topk.required_params, ["topk"])
        self.assertIn("n_drop", topk.known_params)
        self.assertTrue(topk.takes_any_kw)

    def test_strict_class_has_no_var_kw(self):
        strict = self.reg.preferred("Strict", MODEL)
        self.assertFalse(strict.takes_any_kw)
        self.assertEqual(strict.known_params, ["alpha", "fit_intercept"])

    # ---- 歧义与 module_path ----

    def test_ambiguous_names_detected(self):
        self.assertIn("Dup", self.reg.ambiguous_names(MODEL))
        self.assertIn("Twin", self.reg.ambiguous_names(MODEL))

    def test_benchmark_breaks_tie(self):
        """Dup 在两个模块里都有，但官方基准指定了 dup_a -> 取它。"""
        self.assertEqual(self.reg.module_of("Dup", MODEL),
                         "qlib.contrib.model.dup_a")

    def test_unverifiable_ambiguity_returns_nothing(self):
        """Twin 两个模块都有、都没基准背书 -> 不猜。"""
        self.assertEqual(self.reg.module_of("Twin", MODEL), "")
        self.assertIsNone(self.reg.preferred("Twin", MODEL))

    def test_module_of_keeps_already_valid_value(self):
        """已经写对的包路径不该被改写成文件路径（否则会churn 48个官方模板）。"""
        self.assertEqual(self.reg.module_of("Topk", STRATEGY, "qlib.contrib.strategy"),
                         "qlib.contrib.strategy")

    def test_module_of_replaces_invalid_value(self):
        self.assertEqual(
            self.reg.module_of("LGBModel", MODEL, "qlib.contrib.model.wrong"),
            "qlib.contrib.model.gbdt")

    # ---- check_class ----

    def test_empty_class_is_error(self):
        errs, _ = self.reg.check_class("", MODEL)
        self.assertEqual(len(errs), 1)
        self.assertIn("未填写", errs[0])

    def test_unknown_class_is_error_with_suggestion(self):
        errs, _ = self.reg.check_class("LGBModell", MODEL, where="n4")
        self.assertTrue(errs)
        self.assertIn("不在注册表里", errs[0])
        self.assertIn("LGBModel", errs[0])      # 拼写建议

    def test_matching_pair_has_no_error(self):
        errs, warns = self.reg.check_class("LGBModel", MODEL, "qlib.contrib.model.gbdt")
        self.assertEqual(errs, [])
        self.assertEqual(warns, [])

    def test_alias_module_accepted(self):
        errs, warns = self.reg.check_class("Topk", STRATEGY, "qlib.contrib.strategy")
        self.assertEqual(errs, [])
        self.assertEqual(warns, [])

    def test_mismatched_module_is_error(self):
        errs, _ = self.reg.check_class("LGBModel", MODEL, "qlib.contrib.model.dup_a")
        self.assertTrue(errs)
        self.assertIn("里没有", errs[0])
        self.assertIn("gbdt", errs[0])

    def test_ambiguous_without_module_warns(self):
        errs, warns = self.reg.check_class("Twin", MODEL)
        self.assertEqual(errs, [])
        self.assertTrue(any("必须补 module_path" in w for w in warns))

    def test_unique_without_module_is_quiet_by_default(self):
        """类名唯一时留空 module_path 不会出错，所以默认不提示（避免噪音）。"""
        errs, warns = self.reg.check_class("LGBModel", MODEL)
        self.assertEqual((errs, warns), ([], []))
        errs, warns = self.reg.check_class("LGBModel", MODEL, suggest_missing=True)
        self.assertTrue(any("可补上 module_path" in w for w in warns))

    # ---- check_kwargs ----

    def test_missing_required_kwarg_is_error(self):
        errs, _ = self.reg.check_kwargs("Topk", STRATEGY, {"n_drop": 5})
        self.assertTrue(any("缺少必填参数 topk" in e for e in errs))

    def test_benchmark_whitelist_param_accepted(self):
        """基准用过的参数要算合法 —— 否则 num_leaves 这类会被误报。"""
        errs, warns = self.reg.check_kwargs("Dup", MODEL, {"a_param": 7, "loss": "mse"},
                                            "qlib.contrib.model.dup_a")
        self.assertEqual(errs, [])
        self.assertEqual(warns, [])

    def test_unknown_param_without_var_kw_is_error(self):
        errs, warns = self.reg.check_kwargs("Strict", MODEL, {"alphas": 0.1})
        self.assertTrue(any("alphas" in e for e in errs))
        self.assertIn("alpha", errs[0])          # 拼写建议
        self.assertEqual(warns, [])

    def test_unknown_param_with_var_kw_is_warning(self):
        """有 **kwargs 时未知参数降级为警告（可能真是底层库参数），但仍给拼写建议。"""
        errs, warns = self.reg.check_kwargs("LGBModel", MODEL, {"lose": "mse"})
        self.assertEqual(errs, [])
        self.assertTrue(any("lose" in w for w in warns))
        self.assertIn("loss", warns[0])          # 拼写建议

    def test_ambiguous_kwargs_uses_union_without_required_check(self):
        """歧义未定时不能报「缺必填」—— 不知道是哪个类，那是瞎猜。"""
        errs, _ = self.reg.check_kwargs("Twin", MODEL, {})
        self.assertEqual(errs, [])

    # ---- check_node ----

    def test_check_node_model(self):
        errs, _ = self.reg.check_node(
            "qlib.core.model", {"model_class": "Nope", "module_path": "",
                                "model_params": "{}"}, "n4")
        self.assertTrue(errs)

    def test_check_node_strategy_merges_param_props(self):
        errs, _ = self.reg.check_node(
            "qlib.core.strategy",
            {"strategy_class": "Topk", "module_path": "qlib.contrib.strategy",
             "strategy_params": "{}", "strategy_kwargs": '{"n_drop": 3}'}, "n5")
        self.assertTrue(any("缺少必填参数 topk" in e for e in errs))

    def test_check_node_ignores_other_node_types(self):
        self.assertEqual(self.reg.check_node("qlib.core.init", {"region": "cn"}), ([], []))

    def test_check_node_survives_broken_json(self):
        """属性不是合法 JSON 时交给 lint 报，注册表不该重复报或抛异常。"""
        errs, _ = self.reg.check_node(
            "qlib.core.model", {"model_class": "LGBModel", "module_path": "",
                                "model_params": "{不是 json"}, "n4")
        self.assertEqual(errs, [])

    # ---- autofill ----

    def test_autofill_fills_unambiguous(self):
        wf = {"nodes": [{"id": "n4", "type": "qlib.core.model",
                         "props": {"model_class": "LGBModel", "module_path": ""}}]}
        out, changes = autofill_workflow(wf, reg=self.reg)
        self.assertEqual(len(changes), 1)
        self.assertEqual(out["nodes"][0]["props"]["module_path"], "qlib.contrib.model.gbdt")

    def test_autofill_skips_ambiguous(self):
        wf = {"nodes": [{"id": "n4", "type": "qlib.core.model",
                         "props": {"model_class": "Twin", "module_path": ""}}]}
        _out, changes = autofill_workflow(wf, reg=self.reg)
        self.assertEqual(changes, [])

    def test_autofill_keeps_valid_value(self):
        wf = {"nodes": [{"id": "n5", "type": "qlib.core.strategy",
                         "props": {"strategy_class": "Topk",
                                   "module_path": "qlib.contrib.strategy"}}]}
        _out, changes = autofill_workflow(wf, reg=self.reg)
        self.assertEqual(changes, [])

    def test_autofill_uses_specs_defaults_for_missing_props(self):
        """类名可能来自节点默认值，所以要看 specs 的 defaults。"""
        specs = {"qlib.core.model": {"defaults": {"model_class": "LGBModel",
                                                 "module_path": ""}}}
        wf = {"nodes": [{"id": "n4", "type": "qlib.core.model", "props": {}}]}
        out, changes = autofill_workflow(wf, specs, reg=self.reg)
        self.assertEqual(len(changes), 1)
        self.assertEqual(out["nodes"][0]["props"]["module_path"],
                         "qlib.contrib.model.gbdt")

    def test_autofill_does_not_inject_other_defaults(self):
        """只写 module_path，不能把 defaults 里的其它属性灌进节点。"""
        specs = {"qlib.core.model": {"defaults": {"model_class": "LGBModel",
                                                 "module_path": "",
                                                 "model_params": "{}"}}}
        wf = {"nodes": [{"id": "n4", "type": "qlib.core.model", "props": {}}]}
        out, _ = autofill_workflow(wf, specs, reg=self.reg)
        self.assertEqual(set(out["nodes"][0]["props"]), {"module_path"})

    def test_autofill_returns_same_object_when_nothing_to_do(self):
        wf = {"nodes": [{"id": "n1", "type": "qlib.core.init", "props": {}}]}
        out, changes = autofill_workflow(wf, reg=self.reg)
        self.assertIs(out, wf)
        self.assertEqual(changes, [])

    # ---- 展示 ----

    def test_format_list_and_class(self):
        text = self.reg.format_list(MODEL)
        self.assertIn("LGBModel", text)
        self.assertIn("同名类", text)
        detail = self.reg.format_class("Topk", STRATEGY)
        self.assertIn("qlib.contrib.strategy.sig", detail)
        self.assertIn("必填参数", detail)

    def test_format_class_unknown_suggests(self):
        self.assertIn("LGBModel", self.reg.format_class("LGBModell", MODEL))

    def test_catalog_lists_names_and_modules(self):
        text = self.reg.catalog(MODEL)
        self.assertIn("LGBModel", text)
        self.assertIn("qlib.contrib.model.gbdt", text)


class RealRepoIntegrationTest(unittest.TestCase):
    """对着真实仓库确认注册表可用。

    源码可以在仓库内的 ``qlib/``（本地完整检出），也可以是已安装的
    pyqlib。两处都没有时跳过 —— 空注册表不该把流水线判失败，那条行为
    由 :class:`AbsentSourceTest` 覆盖。
    """

    @classmethod
    def setUpClass(cls):
        clear_cache()
        cls.reg = build()
        if not cls.reg.names(MODEL):
            raise unittest.SkipTest("需要 qlib 源码（仓库内 qlib/ 或已安装 pyqlib）")

    @classmethod
    def tearDownClass(cls):
        clear_cache()

    def test_finds_the_known_model_set(self):
        names = {c.name for c in self.reg.of_kind(MODEL)}
        for expect in ("LGBModel", "XGBModel", "CatBoostModel", "DEnsembleModel",
                       "LinearModel", "LSTM", "GRU", "ALSTM", "GATs", "SFM", "TCN",
                       "TabnetModel", "TransformerModel", "TRAModel",
                       "DNNModelPytorch"):
            self.assertIn(expect, names, "缺少模型 %s" % expect)
        tft = Path(__file__).resolve().parent.parent / "examples/benchmarks/TFT/tft.py"
        if tft.is_file():
            self.assertIn("TFTModel", names)

    def test_strategy_set_includes_reexported_ones(self):
        names = {c.name for c in self.reg.of_kind(STRATEGY)}
        for expect in ("TopkDropoutStrategy", "WeightStrategyBase",
                       "EnhancedIndexingStrategy", "TWAPStrategy",
                       "SBBStrategyBase", "SBBStrategyEMA", "SoftTopkStrategy"):
            self.assertIn(expect, names, "缺少策略 %s" % expect)

    def test_internal_nn_module_is_not_listed(self):
        """``SFM_Model(nn.Module)`` 是网络层，被包导出但不是可选模型。"""
        self.assertNotIn("SFM_Model", {c.name for c in self.reg.of_kind(MODEL)})

    def test_known_ambiguities(self):
        amb = set(self.reg.ambiguous_names(MODEL))
        for n in ("ALSTM", "GATs", "GRU", "LSTM", "TCN", "TransformerModel",
                  "LocalformerModel"):
            self.assertIn(n, amb)

    def test_lstm_resolves_via_benchmark(self):
        """LSTM 只有 pytorch_lstm 被官方基准用过 -> 能唯一定位。"""
        self.assertEqual(self.reg.module_of("LSTM", MODEL),
                         "qlib.contrib.model.pytorch_lstm")

    def test_ts_hint_for_ambiguous_ts_variants(self):
        errs, warns = self.reg.check_class("GRU", MODEL)
        self.assertEqual(errs, [])
        self.assertTrue(any("TSDatasetH" in w for w in warns))

    def test_official_strategy_package_path_not_flagged(self):
        """48 个官方模板都写 ``module_path: qlib.contrib.strategy``，不能误判。"""
        errs, warns = self.reg.check_class("TopkDropoutStrategy", STRATEGY,
                                           "qlib.contrib.strategy")
        self.assertEqual(errs, [])
        self.assertEqual(warns, [])

    def test_lightgbm_params_pass_the_whitelist(self):
        """``num_leaves`` 等经 **kwargs 转发给 LightGBM 的参数不能算拼错。"""
        for key in ("num_leaves", "learning_rate", "max_depth", "subsample",
                    "colsample_bytree", "lambda_l1"):
            errs, warns = self.reg.check_kwargs(
                "LGBModel", MODEL, {key: 1}, "qlib.contrib.model.gbdt")
            self.assertEqual((errs, warns), ([], []), "参数 %s 被误报" % key)

    def test_tramodel_required_params_detected(self):
        errs, _ = self.reg.check_kwargs("TRAModel", MODEL, {},
                                       "qlib.contrib.model.pytorch_tra")
        self.assertTrue(any("model_config" in e for e in errs))
        self.assertTrue(any("tra_config" in e for e in errs))

    def test_all_official_templates_pass_lint(self):
        """49 个模板全过语义检查 —— 注册表不能给官方配置制造假警报。"""
        from pipeline.runner import prepare
        from pipeline.specs import extract_specs

        templates = sorted((Path(__file__).resolve().parent.parent
                            / "pipelines").glob("*.yaml"))
        self.assertGreater(len(templates), 10, "模板目录为空，测试失去意义")
        specs = extract_specs()
        for t in templates:
            _wf, errs, warns = prepare(str(t), specs=specs)
            self.assertEqual(errs, [], "%s 校验失败: %s" % (t.name, errs[:2]))
            self.assertEqual(warns, [], "%s 出现假警告: %s" % (t.name, warns[:2]))

    def test_catalog_text_covers_both_kinds(self):
        text = catalog_text()
        self.assertIn("LGBModel", text)
        self.assertIn("TopkDropoutStrategy", text)


class AbsentSourceTest(unittest.TestCase):
    """qlib 源码完全不在时，类名检查必须跳过而不是把每条流水线判失败。"""

    def test_empty_registry_does_not_reject_class_names(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            with patch("pipeline.registry._installed_qlib_root", return_value=None):
                reg = build(Path(tmp), use_cache=False)
            self.assertEqual(reg.names(MODEL), [])
            errs, warns = reg.check_class("LGBModel", MODEL, "qlib.contrib.model.gbdt")
            self.assertEqual(errs, [])
            self.assertEqual(warns, [])


class LintIntegrationTest(unittest.TestCase):
    """注册表检查要能通过 ``lint_workflow`` 浮出来（CLI/GUI/助手都走它）。"""

    @classmethod
    def setUpClass(cls):
        clear_cache()
        if not build().names(MODEL):
            raise unittest.SkipTest("需要 qlib 源码（仓库内 qlib/ 或已安装 pyqlib）")

    def _wf(self, node_type, props):
        return {"nodes": [{"id": "n4", "type": node_type, "props": props}], "links": []}

    def test_bad_model_class_surfaces_as_error(self):
        from pipeline.lint import lint_workflow
        errs, _ = lint_workflow(self._wf("qlib.core.model", {
            "model_class": "LGBModell", "module_path": "", "model_params": "{}"}))
        self.assertTrue(any("LGBModell" in e for e in errs))

    def test_wrong_module_path_surfaces_as_error(self):
        from pipeline.lint import lint_workflow
        errs, _ = lint_workflow(self._wf("qlib.core.model", {
            "model_class": "LGBModel", "module_path": "qlib.contrib.model.pytorch_lstm",
            "model_params": "{}"}))
        self.assertTrue(any("里没有" in e for e in errs))

    def test_missing_required_strategy_param_surfaces(self):
        from pipeline.lint import lint_workflow
        errs, _ = lint_workflow(self._wf("qlib.core.strategy", {
            "strategy_class": "TopkDropoutStrategy",
            "module_path": "qlib.contrib.strategy",
            "strategy_params": "{}", "strategy_kwargs": "{}"}))
        self.assertTrue(any("topk" in e for e in errs))

    def test_clean_node_has_no_registry_messages(self):
        from pipeline.lint import lint_workflow
        errs, warns = lint_workflow(self._wf("qlib.core.model", {
            "model_class": "LGBModel", "module_path": "qlib.contrib.model.gbdt",
            "model_params": '{"num_leaves": 64, "learning_rate": 0.05}'}))
        self.assertEqual(errs, [])
        self.assertEqual(warns, [])

    def test_switch_can_disable_registry_checks(self):
        from pipeline import lint
        wf = self._wf("qlib.core.model", {"model_class": "LGBModell",
                                         "module_path": "", "model_params": "{}"})
        old = lint.USE_REGISTRY
        try:
            lint.USE_REGISTRY = False
            errs, _ = lint.lint_workflow(wf)
            self.assertEqual(errs, [])
        finally:
            lint.USE_REGISTRY = old


def _qt_node_classes():
    """准备好离屏 Qt 并返回节点类；环境不具备时抛 SkipTest。

    ``nodes.qlib_core_nodes`` 依赖 NodeGraphQt，而它在本机是**同级目录**
    ``RockXFWV21/``（不在本仓库里）。CI 上没有它，相关测试自动跳过 ——
    纯逻辑部分由 :class:`RegistryFixtureTest` 覆盖，节点测试只验证粘合层。
    """
    import os
    import sys
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    repo = Path(__file__).resolve().parent.parent
    for p in (str(repo), str(repo.parent / "RockXFWV21")):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as e:                       # pragma: no cover
        raise unittest.SkipTest("需要 PySide6: %s" % e)
    _app = QApplication.instance() or QApplication([])
    try:
        from nodes.qlib_core_nodes import QlibModelNode, QlibStrategyNode
    except Exception as e:                          # pragma: no cover
        raise unittest.SkipTest("节点模块不可用: %s" % e)
    return QlibModelNode, QlibStrategyNode


class NodeAutofillTest(unittest.TestCase):
    """节点在改类名时自动带出 module_path（GUI 体验的关键一环）。"""

    @classmethod
    def setUpClass(cls):
        cls.ModelNode, cls.StrategyNode = _qt_node_classes()

    def test_model_class_change_fills_module_path(self):
        n = self.ModelNode()
        n.set_property("model_class", "XGBModel")
        self.assertEqual(n.get_property("module_path"), "qlib.contrib.model.xgboost")

    def test_ambiguous_class_leaves_module_path_untouched(self):
        """GRU 有歧义（两个模块都被官方基准用过）-> 不猜，保持原值。"""
        n = self.ModelNode()
        n.set_property("model_class", "LSTM")
        before = n.get_property("module_path")
        n.set_property("model_class", "GRU")
        self.assertEqual(n.get_property("module_path"), before)
        self.assertNotEqual(n.get_property("module_path"),
                            "qlib.contrib.model.pytorch_gru_ts")

    def test_user_choice_is_respected(self):
        n = self.ModelNode()
        n.set_property("model_class", "LSTM")
        n.set_property("module_path", "qlib.contrib.model.pytorch_lstm_ts")
        n.set_property("model_class", "LSTM")           # 同名再设一次
        self.assertEqual(n.get_property("module_path"),
                         "qlib.contrib.model.pytorch_lstm_ts")

    def test_strategy_class_change_fills_module_path(self):
        n = self.StrategyNode()
        n.set_property("strategy_class", "ACStrategy")
        self.assertEqual(n.get_property("module_path"),
                         "qlib.contrib.strategy.rule_strategy")

    def test_set_property_still_accepts_ngq_kwargs(self):
        """NodeGraphQt 会以 set_property('selected', False, push_undo=True) 调用。"""
        n = self.ModelNode()
        n.set_property("selected", False, push_undo=True)   # 不该抛异常


class ModelNodeConfigTest(unittest.TestCase):
    """模型节点实际交给 ``init_instance_by_config`` 的配置。

    这里守住一个曾经很严重的 bug：原实现在 ``module_path`` 非空时**只读
    model_kwargs、完全忽略 model_params**，而 48 个导入的官方模板恰好把论文
    超参放在 model_params、同时写了 module_path —— 于是超参被整体丢弃
    （静默、不报错），模型用默认值训练；更糟的是它还会调用
    ``fix_model_config`` 用一张硬编码表**整个覆盖** module_path，
    实测把 LSTM 换成了需要 TSDatasetH 的 ``pytorch_lstm_ts``。
    """

    @classmethod
    def setUpClass(cls):
        cls.ModelNode, _ = _qt_node_classes()

    def _config(self, cls_name, module_path, params, kwargs="{}"):
        n = self.ModelNode()
        n.set_property("model_class", cls_name)
        n.set_property("module_path", module_path)
        n.set_property("model_params", params)
        n.set_property("model_kwargs", kwargs)
        cap = {}
        n.execute_qlib_operation = lambda op, *a, **k: (cap.update(k), None)[1]
        try:
            n.execute()
        except Exception:
            pass
        return cap.get("model_config")

    def test_model_params_are_kept_when_module_path_given(self):
        cfg = self._config("TRAModel", "qlib.contrib.model.pytorch_tra",
                           '{"lr": 0.001, "n_epochs": 100}')
        self.assertEqual(cfg["kwargs"], {"lr": 0.001, "n_epochs": 100})

    def test_module_path_is_not_rewritten_by_hardcoded_table(self):
        cfg = self._config("LSTM", "qlib.contrib.model.pytorch_lstm",
                           '{"d_feat": 20}')
        self.assertEqual(cfg["module_path"], "qlib.contrib.model.pytorch_lstm")

    def test_model_kwargs_overrides_model_params(self):
        cfg = self._config("LGBModel", "qlib.contrib.model.gbdt",
                           '{"num_leaves": 64, "learning_rate": 0.1}',
                           '{"learning_rate": 0.05}')
        self.assertEqual(cfg["kwargs"]["num_leaves"], 64)
        self.assertEqual(cfg["kwargs"]["learning_rate"], 0.05)

    def test_empty_module_path_is_filled_from_registry(self):
        cfg = self._config("XGBModel", "", '{"eta": 0.05}')
        self.assertEqual(cfg["module_path"], "qlib.contrib.model.xgboost")
        self.assertEqual(cfg["kwargs"], {"eta": 0.05})

    def test_ambiguous_class_is_left_without_module_path(self):
        """GRU 有歧义 -> 不猜，交给下游兜底（而不是硬塞一个错的）。"""
        cfg = self._config("GRU", "", '{"n_epochs": 10}')
        self.assertEqual(cfg["kwargs"], {"n_epochs": 10})
        self.assertNotEqual(cfg.get("module_path"),
                            "qlib.contrib.model.pytorch_gru_ts")


if __name__ == "__main__":
    unittest.main()
