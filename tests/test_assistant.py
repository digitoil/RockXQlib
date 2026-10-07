# -*- coding: utf-8 -*-
"""交互式助手测试（假 LLM，无需 Qt/qlib）。python -m unittest tests.test_assistant -v"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.assistant import (Assistant, diff_workflows, slim_workflow,  # noqa: E402
                                summarize_run)
from pipeline.runner import prepare  # noqa: E402
from pipeline.specs import extract_specs  # noqa: E402

SPECS = extract_specs()
BASE = {"steps": ["init", "data", "dataset", "model", "strategy", "backtest"]}


def canvas():
    wf, errs, _ = prepare(BASE)
    assert not errs
    for n in wf["nodes"]:
        n["pos"] = [7, 7]
    return wf


class Scripted:
    """按顺序返回预设回复，并记录收到的消息。"""
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, msgs):
        self.calls.append(msgs)
        return self.replies.pop(0)


def reply(text, wf=None, run=False):
    return json.dumps({"reply": text, "workflow": wf, "run": run}, ensure_ascii=False)


def modified(cv, **model_props):
    wf = slim_workflow(cv)
    for n in wf["nodes"]:
        if n["type"] == "qlib.core.model":
            n["props"] = {**n["props"], **model_props}
    return wf


class DiffTest(unittest.TestCase):
    def test_default_props_are_not_changes(self):
        cv = canvas()
        slim = slim_workflow(cv)
        for n in slim["nodes"]:       # LLM 只回显一部分属性，不应被当成改动
            n["props"] = {}
        self.assertEqual(diff_workflows(cv, slim, SPECS), [])

    def test_prop_node_link_changes(self):
        cv = canvas()
        new = modified(cv, model_class="XGBModel")
        new["nodes"].append({"id": "n7", "type": "qlib.core.handler", "props": {}})
        new["links"] = new["links"][:-1]
        d = diff_workflows(cv, new, SPECS)
        self.assertIn("~ n4.model_class: LGBModel → XGBModel", d)
        self.assertIn("+ 新增节点 n7（qlib.core.handler）", d)
        self.assertTrue(any(x.startswith("- 连线") for x in d))


class TurnTest(unittest.TestCase):
    def test_question_only_has_no_proposal(self):
        a = Assistant(Scripted(reply("LGB 是梯度提升树模型。")), SPECS)
        p = a.turn("LGB 是什么", canvas())
        self.assertIsNone(p.workflow)
        self.assertIn("梯度提升", p.reply)

    def test_plain_text_reply_tolerated(self):
        a = Assistant(Scripted("这不是 JSON，但是个回答"), SPECS)
        p = a.turn("hi", canvas())
        self.assertEqual(p.reply, "这不是 JSON，但是个回答")
        self.assertIsNone(p.workflow)

    def test_modification_proposal_with_diff_and_positions(self):
        cv = canvas()
        a = Assistant(Scripted(reply("已换成 XGB", modified(cv, model_class="XGBModel"))), SPECS)
        p = a.turn("换 XGB", cv)
        self.assertIsNotNone(p.workflow)
        self.assertEqual(p.changes, ["~ n4.model_class: LGBModel → XGBModel"])
        self.assertTrue(all(n["pos"] == [7, 7] for n in p.workflow["nodes"]))  # 位置保留

    def test_noop_modification_dropped(self):
        cv = canvas()
        a = Assistant(Scripted(reply("没变", slim_workflow(cv))), SPECS)
        self.assertIsNone(a.turn("x", cv).workflow)

    def test_canvas_and_last_run_sent_to_llm_each_turn(self):
        cv = canvas()
        llm = Scripted(reply("a"), reply("b"))
        a = Assistant(llm, SPECS)
        a.turn("第一句", cv)
        cv2 = modified(cv, model_class="Zed")   # 用户手动改了画布
        cv2["nodes"] = [{**n, "props": n["props"]} for n in cv2["nodes"]]
        a.turn("第二句", cv2, {"status": "partial", "ok_count": 3, "total": 6,
                              "records": [{"node": "模型", "ok": False, "detail": "boom"}]})
        last_user = llm.calls[1][-1]["content"]
        self.assertIn("Zed", last_user)
        self.assertIn("boom", last_user)
        # 历史里是用户原话，不含上一轮的画布快照
        hist = " ".join(m["content"] for m in llm.calls[1][1:-1])
        self.assertIn("第一句", hist)
        self.assertNotIn("画布当前工作流", hist)

    def test_invalid_proposal_repaired(self):
        cv = canvas()
        bad = modified(cv)
        bad["nodes"][3]["props"]["no_such_prop"] = 1
        llm = Scripted(reply("试试", bad), reply("修好了", modified(cv, model_class="XGBModel")))
        p = Assistant(llm, SPECS).turn("改", cv)
        self.assertIsNotNone(p.workflow)
        self.assertIn("no_such_prop", llm.calls[1][-1]["content"])  # 错误被喂回

    def test_unfixable_proposal_never_touches_canvas(self):
        cv = canvas()
        bad = modified(cv)
        bad["nodes"][3]["props"]["zzz"] = 1
        llm = Scripted(*[reply("坚持", bad)] * 3)
        p = Assistant(llm, SPECS).turn("改", cv)
        self.assertIsNone(p.workflow)
        self.assertFalse(p.run_suggested)
        self.assertIn("没有改动画布", p.reply)

    def test_lookahead_leak_rejected(self):
        cv = canvas()
        bad = slim_workflow(cv)
        for n in bad["nodes"]:
            if n["type"] == "qlib.core.dataset":
                n["props"] = {**n["props"], "train_end": "2016-06-30"}
        llm = Scripted(*[reply("x", bad)] * 3)
        p = Assistant(llm, SPECS).turn("延长训练", cv)
        self.assertIsNone(p.workflow)
        self.assertIn("前视泄漏", llm.calls[1][-1]["content"])

    def test_run_flag_is_only_a_suggestion(self):
        cv = canvas()
        a = Assistant(Scripted(reply("跑吧", modified(cv, model_class="XGBModel"), run=True)),
                      SPECS)
        p = a.turn("改完就跑", cv)
        self.assertTrue(p.run_suggested)   # 仅建议；真正执行由界面确认

    def test_unknown_model_class_is_repaired(self):
        """类名不在注册表里 -> 提案被拒并回喂错误让 LLM 改（而不是放过）。"""
        cv = canvas()
        bad = modified(cv, model_class="Transformer")   # 正确写法是 TransformerModel
        llm = Scripted(reply("换模型", bad),
                       reply("已修正", modified(cv, model_class="TransformerModel")))
        p = Assistant(llm, SPECS).turn("用 Transformer", cv)
        self.assertIsNotNone(p.workflow)
        self.assertIn("Transformer", llm.calls[1][-1]["content"])   # 错误被喂回

    def test_missing_required_hyperparam_is_repaired(self):
        """TRAModel 漏了必填超参 -> 也该在提案阶段被拦下。"""
        cv = canvas()
        bad = modified(cv, model_class="TRAModel",
                       module_path="qlib.contrib.model.pytorch_tra",
                       model_params="{}")
        llm = Scripted(reply("上 TRA", bad),
                       reply("补上", modified(cv, model_class="LGBModel")))
        Assistant(llm, SPECS).turn("用 TRA", cv)
        self.assertIn("tra_config", llm.calls[1][-1]["content"])

    def test_history_is_bounded(self):
        a = Assistant(Scripted(*[reply("ok")] * 30), SPECS)
        for i in range(30):
            a.turn("q%d" % i, canvas())
        self.assertLessEqual(len(a.history[-16:]), 16)
        sent = a.chat.calls[-1]
        self.assertLessEqual(len(sent), 1 + 16 + 1)


class DiagnoseTest(unittest.TestCase):
    FAIL = {"status": "partial", "ok_count": 1, "total": 6, "elapsed": 3.2,
            "records": [{"node": "Qlib初始化", "ok": True},
                        {"node": "Qlib数据获取", "ok": False, "detail": "provider_uri 不存在"}]}

    def test_no_run_yet(self):
        p = Assistant(Scripted(), SPECS).diagnose(canvas(), None)
        self.assertIn("先运行", p.reply)

    def test_failure_prompt_contains_error(self):
        llm = Scripted(reply("数据目录不对"))
        Assistant(llm, SPECS).diagnose(canvas(), self.FAIL)
        sent = llm.calls[0][-1]["content"]
        self.assertIn("provider_uri 不存在", sent)
        self.assertIn("失败", sent)

    def test_summarize_never_invents_metrics(self):
        self.assertIn("指标: 无", summarize_run(self.FAIL))
        s = summarize_run({"status": "success", "ok_count": 6, "total": 6,
                           "metrics": {"sharpe": 1.2, "note": "x"}})
        self.assertIn('"sharpe": 1.2', s)
        self.assertNotIn("note", s)


if __name__ == "__main__":
    unittest.main()
