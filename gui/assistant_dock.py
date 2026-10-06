# -*- coding: utf-8 -*-
"""AI 建模助手面板（停靠在主窗口右侧）。

流程：对话 -> 助手给出「提案」（文字 + 画布修改清单）-> 用户点「应用到画布」
（可「撤销」）-> 点「应用并运行」-> 运行结束后点「诊断/解读」把真实结果交回助手。
助手从不自行改画布或启动运行；每一步都由用户点按钮确认。
"""
from __future__ import annotations

import html
import os
from typing import Any, Dict, Optional

from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDockWidget, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QTextBrowser, QVBoxLayout, QWidget,
)


class _TurnThread(QThread):
    done = Signal(object)    # Proposal
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            self.done.emit(self._fn())
        except Exception as e:      # 服务没启动 / 网络 / 鉴权
            self.failed.emit("%s: %s" % (type(e).__name__, e))


class AssistantDock(QDockWidget):
    def __init__(self, win, parent=None):
        super().__init__("AI 建模助手", parent or win)
        self.win = win
        self.assistant = None
        self.pending = None             # 待应用的提案
        self.undo_wf: Optional[Dict[str, Any]] = None
        self.last_run: Optional[Dict[str, Any]] = None
        self._thread = None
        self._settings = QSettings("RockXQlib", "assistant")

        root = QWidget()
        lay = QVBoxLayout(root)

        cfg = QHBoxLayout()
        self.url = QLineEdit(self._settings.value(
            "base_url", os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")))
        self.model = QLineEdit(self._settings.value("model", os.environ.get("LLM_MODEL", "")))
        self.key = QLineEdit(os.environ.get("LLM_API_KEY", ""))   # 密钥不落盘
        self.key.setEchoMode(QLineEdit.Password)
        self.url.setPlaceholderText("接口地址")
        self.model.setPlaceholderText("模型名")
        self.key.setPlaceholderText("API Key（可空）")
        for w, s in ((self.url, 3), (self.model, 2), (self.key, 2)):
            cfg.addWidget(w, s)
        lay.addLayout(cfg)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(False)
        lay.addWidget(self.view, 1)

        self.inp = QPlainTextEdit()
        self.inp.setPlaceholderText("描述需求或问问题，如：把模型换成 XGBModel，并把回测放到 2019 年起\n（Ctrl+Enter 发送）")
        self.inp.setMaximumHeight(80)
        lay.addWidget(self.inp)

        row1 = QHBoxLayout()
        self.send_btn = QPushButton("发送")
        self.diag_btn = QPushButton("诊断 / 解读上次运行")
        self.diag_btn.setEnabled(False)
        row1.addWidget(self.send_btn)
        row1.addWidget(self.diag_btn)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        self.apply_btn = QPushButton("应用到画布")
        self.run_btn = QPushButton("应用并运行")
        self.undo_btn = QPushButton("撤销上次应用")
        self.new_btn = QPushButton("新对话")
        for b in (self.apply_btn, self.run_btn, self.undo_btn):
            b.setEnabled(False)
        for b in (self.apply_btn, self.run_btn, self.undo_btn, self.new_btn):
            row2.addWidget(b)
        lay.addLayout(row2)
        self.status = QLabel("")
        lay.addWidget(self.status)
        self.setWidget(root)

        self.send_btn.clicked.connect(self.send)
        self.diag_btn.clicked.connect(self.diagnose)
        self.apply_btn.clicked.connect(lambda: self.apply(run=False))
        self.run_btn.clicked.connect(lambda: self.apply(run=True))
        self.undo_btn.clicked.connect(self.undo)
        self.new_btn.clicked.connect(self.new_chat)
        self.inp.installEventFilter(self)
        self._say("系统", "我可以帮你搭建、修改工作流，并在运行后分析结果。"
                          "我只给出建议，画布修改和运行都需要你点按钮确认。")

    # ---- 小工具 ----
    def eventFilter(self, obj, ev):
        if obj is self.inp and ev.type() == ev.Type.KeyPress and \
                ev.key() in (Qt.Key_Return, Qt.Key_Enter) and ev.modifiers() & Qt.ControlModifier:
            self.send()
            return True
        return super().eventFilter(obj, ev)

    def _say(self, who: str, text: str, items=None, color="#8ab4f8"):
        body = html.escape(text).replace("\n", "<br>")
        extra = ""
        if items:
            extra = "<ul>" + "".join("<li>%s</li>" % html.escape(i) for i in items) + "</ul>"
        self.view.append('<p><b style="color:%s">%s</b><br>%s%s</p>' % (color, who, body, extra))

    def _busy(self, on: bool, msg: str = ""):
        for b in (self.send_btn, self.diag_btn):
            b.setEnabled(not on and (b is self.send_btn or self.last_run is not None))
        self.status.setText(msg)

    def _ensure_assistant(self) -> bool:
        if not self.model.text().strip():
            self._say("系统", "请先填写模型名（Ollama 需先启动服务并拉取模型）。", color="#f28b82")
            return False
        from pipeline.assistant import Assistant
        from pipeline.llm import openai_compatible_chat
        chat = openai_compatible_chat(self.url.text().strip(), self.model.text().strip(),
                                      self.key.text().strip())
        if self.assistant is None:
            self.assistant = Assistant(chat, self.win._specs_for_pipeline())
        else:
            self.assistant.chat = chat
            self.assistant.specs = self.win._specs_for_pipeline()
        self._settings.setValue("base_url", self.url.text().strip())
        self._settings.setValue("model", self.model.text().strip())
        return True

    def _canvas(self) -> Dict[str, Any]:
        from core.workflow_schema import serialize_graph
        return serialize_graph(self.win.graph, name="canvas")

    # ---- 对话 ----
    def send(self):
        text = self.inp.toPlainText().strip()
        if not text or not self._ensure_assistant():
            return
        self.inp.clear()
        self._say("你", text, color="#81c995")
        canvas, last = self._canvas(), self.last_run
        self._start(lambda: self.assistant.turn(text, canvas, last), "思考中…")

    def diagnose(self):
        if not self._ensure_assistant():
            return
        self._say("你", "（请诊断/解读上次运行）", color="#81c995")
        canvas, last = self._canvas(), self.last_run
        self._start(lambda: self.assistant.diagnose(canvas, last), "分析运行结果中…")

    def _start(self, fn, msg):
        self._busy(True, msg)
        self.pending = None
        self.apply_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        th = _TurnThread(fn, self)
        th.done.connect(self._on_done)
        th.failed.connect(self._on_failed)
        th.finished.connect(lambda: setattr(self, "_thread", None))
        self._thread = th
        th.start()

    def _on_failed(self, err: str):
        self._busy(False)
        self._say("系统", "调用 LLM 失败：%s\n请检查接口地址、模型名与服务是否已启动。" % err,
                  color="#f28b82")

    def _on_done(self, prop):
        self._busy(False)
        self._say("助手", prop.reply or "（无文字回复）")
        if prop.workflow:
            self.pending = prop
            self._say("提案", "将对画布做如下修改（点「应用到画布」才会生效）：",
                      items=prop.changes, color="#fdd663")
            for w in prop.warnings:
                self._say("提示", w.replace("[警告] ", ""), color="#fdd663")
            self.apply_btn.setEnabled(True)
            self.run_btn.setEnabled(True)
            if prop.run_suggested:
                self._say("系统", "助手建议修改后运行，可点「应用并运行」。", color="#8ab4f8")

    # ---- 应用 / 撤销 / 运行 ----
    def apply(self, run: bool):
        prop = self.pending
        if prop is None:
            return
        from core.workflow_schema import deserialize_graph
        before = self._canvas()
        ok, errs = deserialize_graph(prop.workflow, self.win.graph, clear=True,
                                     specs=self.win._specs_for_pipeline())
        if not ok:
            # 半成品不留在画布上：还原
            if before.get("nodes"):
                deserialize_graph(before, self.win.graph, clear=True)
            self._say("系统", "应用失败，画布已还原：\n" + "\n".join(errs[:6]), color="#f28b82")
            return
        self.undo_wf = before
        self.undo_btn.setEnabled(bool(before.get("nodes")))
        self.pending = None
        self.apply_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        self.win.log_message("AI 助手：已应用 %d 项修改" % len(prop.changes), "SUCCESS")
        self._say("系统", "已应用到画布（可点「撤销上次应用」）。", color="#8ab4f8")
        if run:
            self._say("系统", "开始运行…运行结束后可点「诊断 / 解读上次运行」。", color="#8ab4f8")
            self.win.run_workflow()

    def undo(self):
        if not self.undo_wf:
            return
        from core.workflow_schema import deserialize_graph
        ok, errs = deserialize_graph(self.undo_wf, self.win.graph, clear=True,
                                     specs=self.win._specs_for_pipeline())
        self._say("系统", "已撤销，画布回到应用前的状态。" if ok else "撤销失败：" + "；".join(errs[:3]),
                  color="#8ab4f8" if ok else "#f28b82")
        if ok:
            self.undo_wf = None
            self.undo_btn.setEnabled(False)

    def new_chat(self):
        if self.assistant:
            self.assistant.reset()
        self.pending = None
        self.view.clear()
        self.apply_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        self._say("系统", "已开始新对话（画布内容保持不变）。")

    # ---- 运行结果回灌 ----
    def on_run_finished(self, summary: Dict[str, Any]):
        from pipeline.assistant import summarize_run
        self.last_run = summary
        self.diag_btn.setEnabled(self._thread is None)
        ok = (summary or {}).get("status") == "success"
        self._say("运行结果", summarize_run(summary),
                  color="#81c995" if ok else "#f28b82")
        self._say("系统", "可点「诊断 / 解读上次运行」让助手分析。" if not ok else
                  "运行成功，可点「诊断 / 解读上次运行」让助手解读指标。", color="#8ab4f8")
