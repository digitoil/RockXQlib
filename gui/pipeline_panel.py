# -*- coding: utf-8 -*-
"""GUI 侧的流水线能力：模板库、AI 生成（预览确认）、运行记录。

主窗口通过 ``PipelineGuiMixin`` 获得这些方法；``self.graph`` 是画布，
所有「落到画布」的动作都先校验、失败则画布保持不变。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

PIPELINES_DIR = Path(__file__).resolve().parent.parent / "pipelines"


class _GenerateThread(QThread):
    done = Signal(object, list)   # doc|None, trail

    def __init__(self, request, base_url, model, api_key, specs, parent=None):
        super().__init__(parent)
        self._a = (request, base_url, model, api_key, specs)

    def run(self):
        from pipeline.llm import generate_pipeline, openai_compatible_chat
        request, base_url, model, api_key, specs = self._a
        try:
            doc, trail = generate_pipeline(
                request, openai_compatible_chat(base_url, model, api_key), specs=specs)
        except Exception as e:  # 服务未启动 / 网络错误
            doc, trail = None, ["调用 LLM 失败: %s" % e]
        self.done.emit(doc, trail)


class PipelineGuiMixin:
    """混入 RockXQlibMainWindow。依赖：self.graph / self.log_message / self.status_label。"""

    # ---------- 公共：把流水线 doc 校验后落到画布 ----------
    def _specs_for_pipeline(self):
        from core.workflow_schema import collect_specs_from_graph
        return collect_specs_from_graph(self.graph)

    def _load_pipeline_doc_to_canvas(self, doc, overrides=None, title="流水线"):
        from core.workflow_schema import deserialize_graph
        from pipeline.runner import prepare
        specs = self._specs_for_pipeline()
        wf, errors, warnings = prepare(doc, overrides, specs)
        if errors:
            QMessageBox.critical(self, "校验未通过（画布保持不变）",
                                 "\n".join("• " + e for e in errors[:12]))
            return False
        wf.pop("params", None)
        ok, errs = deserialize_graph(wf, self.graph, clear=True, specs=specs)
        if not ok:
            QMessageBox.critical(self, "载入失败", "\n".join("• " + e for e in errs[:12]))
            return False
        for w in warnings:
            self.log_message(w, "WARNING")
        self.log_message("已载入%s: %s（%d 节点 / %d 连线）" % (
            title, wf.get("name", ""), len(wf["nodes"]), len(wf["links"])), "SUCCESS")
        try:
            self.graph.fit_to_selection() if self.graph.selected_nodes() else self.graph.clear_selection()
        except Exception:
            pass
        return True

    # ---------- 模板库 ----------
    def pipeline_new_from_template(self):
        from pipeline.definition import load_pipeline_file
        files = sorted(list(PIPELINES_DIR.glob("*.yaml")) + list(PIPELINES_DIR.glob("*.json")))
        if not files:
            QMessageBox.information(self, "提示", "pipelines/ 下没有模板")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("从模板新建工作流")
        lay = QVBoxLayout(dlg)
        lst = QListWidget()
        for f in files:
            lst.addItem(f.name)
        lst.setCurrentRow(0)
        lay.addWidget(QLabel("选择模板（载入到画布，可继续拖拽修改）："))
        lay.addWidget(lst)
        form = QFormLayout()
        param_edit = QLineEdit()
        param_edit.setPlaceholderText("可选覆盖参数，如 universe=csi500;train_end=2015-12-31")
        form.addRow("参数覆盖", param_edit)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() != QDialog.Accepted or lst.currentRow() < 0:
            return
        path = files[lst.currentRow()]
        try:
            from pipeline.definition import parse_overrides
            ov = parse_overrides([x for x in param_edit.text().split(";") if x.strip()])
            doc = load_pipeline_file(str(path))
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
            return
        self._load_pipeline_doc_to_canvas(doc, ov, title="模板")

    def pipeline_save_as_template(self):
        """把当前画布存成 pipelines/<name>.json，之后可从模板新建。"""
        from PySide6.QtWidgets import QInputDialog
        from core.workflow_schema import dump_workflow, serialize_graph
        if not self.graph.all_nodes():
            QMessageBox.information(self, "提示", "画布中没有节点")
            return
        name, ok = QInputDialog.getText(self, "保存为模板", "模板名称：")
        if not ok or not name.strip():
            return
        PIPELINES_DIR.mkdir(exist_ok=True)
        dest = PIPELINES_DIR / ("%s.json" % name.strip())
        if dest.exists() and QMessageBox.question(
                self, "覆盖？", "%s 已存在，覆盖吗？" % dest.name) != QMessageBox.Yes:
            return
        dump_workflow(serialize_graph(self.graph, name=name.strip()), str(dest))
        self.log_message("已保存模板: %s" % dest, "SUCCESS")

    # ---------- AI 生成（预览确认）----------
    def pipeline_ai_generate(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("AI 生成工作流（先预览，确认后才落到画布）")
        dlg.resize(560, 360)
        lay = QVBoxLayout(dlg)
        req = QPlainTextEdit()
        req.setPlaceholderText("描述需求，例如：用 CSI500 股票池，LGB 模型，2019 年起回测")
        lay.addWidget(req)
        form = QFormLayout()
        url = QLineEdit(os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"))
        model = QLineEdit(os.environ.get("LLM_MODEL", ""))
        key = QLineEdit(os.environ.get("LLM_API_KEY", ""))
        key.setEchoMode(QLineEdit.Password)
        form.addRow("接口地址", url)
        form.addRow("模型", model)
        form.addRow("API Key", key)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("生成")
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() != QDialog.Accepted:
            return
        if not req.toPlainText().strip() or not model.text().strip():
            QMessageBox.warning(self, "提示", "需求和模型名不能为空")
            return
        self.log_message("AI 生成中…（调用 %s / %s）" % (url.text(), model.text()), "INFO")
        self.status_label.setText("AI 生成中…")
        th = _GenerateThread(req.toPlainText().strip(), url.text().strip(),
                             model.text().strip(), key.text().strip(),
                             self._specs_for_pipeline(), self)
        th.done.connect(self._on_ai_generated)
        th.finished.connect(lambda: setattr(self, "_ai_thread", None))
        self._ai_thread = th
        th.start()

    def _on_ai_generated(self, doc, trail):
        for t in trail:
            self.log_message("AI: " + t, "INFO")
        self.status_label.setText("就绪")
        if doc is None:
            QMessageBox.warning(self, "未生成",
                                "没能得到通过校验的工作流：\n\n" + "\n".join(trail[-3:]))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("预览 AI 生成的工作流")
        dlg.resize(560, 460)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("已通过结构校验。确认后载入画布（会替换当前画布，可 Ctrl+Z 之外请先保存）："))
        txt = QPlainTextEdit(json.dumps(doc, ensure_ascii=False, indent=2))
        txt.setReadOnly(True)
        lay.addWidget(txt)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("载入画布")
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() == QDialog.Accepted:
            self._load_pipeline_doc_to_canvas(doc, title="AI 工作流")

    # ---------- 运行记录 ----------
    def pipeline_record_gui_run(self, summary):
        """GUI 一键运行结束后调用：把画布与结果存成可复现的运行记录。"""
        try:
            from core.workflow_schema import serialize_graph
            from pipeline.runner import record_run
            wf = serialize_graph(self.graph, name="canvas")
            d = record_run(wf, summary, backend="gui")
            self.log_message("运行记录已保存: %s" % d.name, "INFO")
        except Exception as e:
            self.log_message("保存运行记录失败: %s" % e, "WARNING")

    def pipeline_show_runs(self):
        from pipeline.runs import _flat_metrics, list_runs
        runs = list_runs()
        if not runs:
            QMessageBox.information(self, "运行记录", "暂无运行记录（每次一键运行会自动保存）")
            return
        keys = list(dict.fromkeys(k for r in runs for k in _flat_metrics(r)))
        cols = ["运行 ID", "状态", "耗时(s)"] + keys
        dlg = QDialog(self)
        dlg.setWindowTitle("运行记录（选中一行可把当时的工作流载回画布）")
        dlg.resize(900, 460)
        lay = QVBoxLayout(dlg)
        tbl = QTableWidget(len(runs), len(cols))
        tbl.setHorizontalHeaderLabels(cols)
        tbl.setSelectionBehavior(QTableWidget.SelectRows)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        for i, r in enumerate(reversed(runs)):
            m = _flat_metrics(r)
            vals = [r["run_id"], r.get("status", "?"), "%.1f" % r.get("elapsed", 0)] + \
                   [("%.4f" % m[k]) if k in m else "-" for k in keys]
            for j, v in enumerate(vals):
                tbl.setItem(i, j, QTableWidgetItem(v))
        tbl.resizeColumnsToContents()
        lay.addWidget(tbl)
        row = QHBoxLayout()
        load_btn = QPushButton("载回画布")
        close_btn = QPushButton("关闭")
        row.addStretch(1)
        row.addWidget(load_btn)
        row.addWidget(close_btn)
        lay.addLayout(row)
        close_btn.clicked.connect(dlg.reject)

        def load():
            i = tbl.currentRow()
            if i < 0:
                return
            rid = tbl.item(i, 0).text()
            wf_path = next((Path(r["run_dir"]) / "workflow.json" for r in runs
                            if r["run_id"] == rid), None)
            if not wf_path or not wf_path.exists():
                QMessageBox.warning(dlg, "提示", "该记录没有保存工作流")
                return
            dlg.accept()
            self._load_pipeline_doc_to_canvas(json.loads(wf_path.read_text(encoding="utf-8")),
                                              title="历史运行")
        load_btn.clicked.connect(load)
        dlg.exec()
