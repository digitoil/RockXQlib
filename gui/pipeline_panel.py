# -*- coding: utf-8 -*-
"""GUI 侧的流水线能力：模板库、AI 生成（预览确认）、运行记录。

主窗口通过 ``PipelineGuiMixin`` 获得这些方法；``self.graph`` 是画布，
所有「落到画布」的动作都先校验、失败则画布保持不变。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

PIPELINES_DIR = Path(__file__).resolve().parent.parent / "pipelines"


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

    # ---------- AI 建模助手（交互式）----------
    def pipeline_ai_generate(self):
        """显示 / 隐藏右侧「AI 建模助手」面板（首次调用时创建）。"""
        from gui.assistant_dock import AssistantDock
        dock = getattr(self, "_assistant_dock", None)
        if dock is None:
            dock = AssistantDock(self)
            self.addDockWidget(Qt.RightDockWidgetArea, dock)
            self._assistant_dock = dock
        dock.setVisible(not dock.isVisible() if getattr(self, "_assistant_dock_seen", False)
                        else True)
        self._assistant_dock_seen = True

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
        # 无论存档是否成功，都把真实结果交给助手面板（若已打开）
        dock = getattr(self, "_assistant_dock", None)
        if dock is not None:
            try:
                dock.on_run_finished(summary)
            except Exception as e:
                self.log_message("助手面板更新失败: %s" % e, "WARNING")

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
        cmp_btn = QPushButton("对比选中（Ctrl 多选）")
        close_btn = QPushButton("关闭")
        row.addStretch(1)
        row.addWidget(cmp_btn)
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

        def compare():
            from pipeline.runs import compare_text
            ids = sorted({tbl.item(ix.row(), 0).text() for ix in tbl.selectionModel().selectedRows()})
            picked = [r for r in runs if r["run_id"] in ids]
            if len(picked) < 2:
                QMessageBox.information(dlg, "提示", "请按住 Ctrl 选择至少两条运行记录")
                return
            box = QDialog(dlg)
            box.setWindowTitle("运行对比")
            box.resize(860, 420)
            v = QVBoxLayout(box)
            t = QPlainTextEdit(compare_text(picked))
            t.setReadOnly(True)
            t.setStyleSheet("font-family: Consolas, 'Cascadia Mono', monospace;")
            v.addWidget(t)
            box.exec()
        cmp_btn.clicked.connect(compare)
        tbl.setSelectionMode(QTableWidget.ExtendedSelection)
        dlg.exec()

    # ---------- 参数扫描（在画布上批量试参）----------
    def pipeline_sweep(self):
        """对当前画布做参数网格：逐组合改节点属性 -> 真实运行 -> 存档，结束后还原属性。

        属性读写都在主线程；只有「执行」在 QThread 里，与一键运行一致。
        """
        from core.workflow_schema import serialize_graph
        from pipeline.sweep import expand, parse_grid
        nodes = self.graph.all_nodes()
        if not nodes:
            QMessageBox.information(self, "提示", "画布中没有节点")
            return
        if getattr(self, "workflow_thread", None) is not None and self.workflow_thread.isRunning():
            QMessageBox.information(self, "提示", "已有工作流在运行")
            return
        wf = serialize_graph(self.graph, name="sweep")
        ref = "\n".join("%s  %s" % (n["id"], n["name"]) for n in wf["nodes"])

        dlg = QDialog(self)
        dlg.setWindowTitle("参数扫描")
        dlg.resize(520, 380)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("每行一个参数：节点id.属性=值1,值2,...（组合数 = 各行取值数相乘）"))
        edit = QPlainTextEdit()
        edit.setPlaceholderText("n3.train_start=2008-01-01,2010-01-01\nn4.model_class=LGBModel,XGBModel")
        lay.addWidget(edit)
        lay.addWidget(QLabel("画布节点 id 对照："))
        ids = QPlainTextEdit(ref)
        ids.setReadOnly(True)
        ids.setMaximumHeight(110)
        lay.addWidget(ids)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("开始扫描")
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            lines = [x.strip() for x in edit.toPlainText().splitlines() if x.strip()]
            combos = expand(parse_grid(lines))
            by_id = {n["id"]: node for n, node in zip(wf["nodes"], nodes)}
            props_of = {n["id"]: n["props"] for n in wf["nodes"]}
            for c in combos:
                for k in c:
                    nid, _, prop = k.partition(".")
                    if prop not in props_of.get(nid, {}):
                        raise ValueError("画布上没有 %s（格式：节点id.属性）" % k)
            # 逐组合做语义检查：日期颠倒、区间重叠（前视泄漏）等，跑之前就拦下
            import copy
            from pipeline.lint import lint_workflow
            from pipeline.specs import extract_specs
            bad = []
            for c in combos:
                w2 = copy.deepcopy(wf)
                for k, v in c.items():
                    nid, _, prop = k.partition(".")
                    next(n for n in w2["nodes"] if n["id"] == nid)["props"][prop] = v
                errs, _ = lint_workflow(w2, extract_specs())
                if errs:
                    bad.append("%s → %s" % (c, errs[0]))
            if bad:
                raise ValueError("以下组合不合法，未运行：\n" + "\n".join(bad[:6]))
        except Exception as e:
            QMessageBox.critical(self, "参数有误", str(e))
            return
        if len(combos) > 1 and QMessageBox.question(
                self, "确认", "将依次运行 %d 个组合，真实回测可能耗时很久，继续吗？" % len(combos)
        ) != QMessageBox.Yes:
            return

        self._sweep = {"wf": wf, "by_id": by_id, "combos": combos, "i": 0,
                       "orig": {k: n.get_property(k.split('.', 1)[1])
                                for c in combos for k in c
                                for n in [by_id[k.split('.', 1)[0]]]},
                       "results": []}
        self.run_action.setEnabled(False)
        self._sweep_next()

    def _sweep_next(self):
        sw = self._sweep
        if sw["i"] >= len(sw["combos"]):
            return self._sweep_done()
        combo = sw["combos"][sw["i"]]
        for k, v in combo.items():
            nid, prop = k.split(".", 1)
            sw["by_id"][nid].set_property(prop, v if isinstance(v, str) else json.dumps(v))
        self.log_message("参数扫描 %d/%d: %s" % (sw["i"] + 1, len(sw["combos"]), combo), "INFO")
        # 不能 import 主脚本（作为 __main__ 运行时会重复执行整个 GUI 启动代码），
        # 从已加载的模块里取类
        import sys
        WorkflowExecutionThread = sys.modules[type(self).__module__].WorkflowExecutionThread
        th = WorkflowExecutionThread(self.graph.all_nodes(), parent=self)
        th.progress_updated.connect(self.update_workflow_progress)
        th.execution_completed.connect(self._sweep_point_done)
        th.execution_error.connect(lambda m: self._sweep_point_done({"status": "error", "error": m}))
        self.workflow_thread = th
        th.start()

    def _sweep_point_done(self, summary):
        from core.workflow_schema import serialize_graph
        from pipeline.runner import record_run
        sw = self._sweep
        combo = sw["combos"][sw["i"]]
        try:
            wf = serialize_graph(self.graph, name="sweep")
            record_run(wf, summary or {}, backend="gui-sweep", tag="s%02d" % (sw["i"] + 1))
        except Exception as e:
            self.log_message("保存扫描记录失败: %s" % e, "WARNING")
        sw["results"].append((combo, (summary or {}).get("status")))
        sw["i"] += 1
        # 等线程真正结束再启动下一个，避免两个执行线程重叠
        th = self.workflow_thread
        if th.isFinished():
            QTimer.singleShot(0, self._sweep_next)
        else:
            th.finished.connect(self._sweep_next)

    def _sweep_done(self):
        sw = self._sweep
        for k, v in sw["orig"].items():           # 还原被改动的属性
            nid, prop = k.split(".", 1)
            sw["by_id"][nid].set_property(prop, v)
        self.run_action.setEnabled(True)
        ok = sum(1 for _, st in sw["results"] if st == "success")
        self.log_message("参数扫描完成：%d/%d 成功，已存档，可在「运行记录…」里对比"
                         % (ok, len(sw["results"])), "SUCCESS")
        QMessageBox.information(self, "参数扫描完成",
                                "%d/%d 个组合成功。\n打开「工作流 → 运行记录…」，Ctrl 多选后对比。"
                                % (ok, len(sw["results"])))
        self._sweep = None
