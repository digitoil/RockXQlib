# -*- coding: utf-8 -*-
"""``pipeline/llm_probe.py`` 的单元测试。

策略：网络部分用**本地起的假 HTTP 服务**验证（确定性、不依赖外网），
解析部分直接用构造的数据验证纯函数。
"""
from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.llm_probe import (
    ProbeResult,
    _parse_ollama_tags,
    _parse_openai_models,
    _url_variants,
    candidates,
    diagnose,
    format_report,
    local_ollama_models,
    probe,
)


# ---------------------------------------------------------------- 纯函数

class TestParsers(unittest.TestCase):
    def test_openai_models_normal(self):
        obj = {"object": "list", "data": [{"id": "qwen3.5:9b"}, {"id": "deepseek-r1:8b"}]}
        self.assertEqual(_parse_openai_models(obj), ["qwen3.5:9b", "deepseek-r1:8b"])

    def test_openai_models_empty(self):
        """网关可达但没部署模型 —— 必须能区分出来，不能当成解析失败。"""
        self.assertEqual(_parse_openai_models({"object": "list", "data": []}), [])

    def test_openai_models_malformed(self):
        for bad in (None, [], "x", {}, {"data": None}, {"data": "x"},
                    {"data": [None, 1, {}, {"id": "  "}]}):
            self.assertEqual(_parse_openai_models(bad), [], "输入 %r" % (bad,))

    def test_ollama_tags_normal(self):
        obj = {"models": [{"name": "qwen3.5:9b"}, {"name": "bge-m3:latest"}]}
        self.assertEqual(_parse_ollama_tags(obj), ["qwen3.5:9b", "bge-m3:latest"])

    def test_ollama_tags_fallbacks(self):
        # 旧版本字段名是 model
        self.assertEqual(_parse_ollama_tags({"models": [{"model": "a:1"}]}), ["a:1"])
        for bad in (None, {}, {"models": []}, {"models": "x"}):
            self.assertEqual(_parse_ollama_tags(bad), [])

    def test_url_variants_with_v1(self):
        v = dict(_url_variants("http://localhost:11434/v1"))
        self.assertEqual(v["openai"], "http://localhost:11434/v1/models")
        self.assertEqual(v["ollama"], "http://localhost:11434/api/tags")

    def test_url_variants_without_v1(self):
        v = dict(_url_variants("http://localhost:11434"))
        self.assertEqual(v["openai"], "http://localhost:11434/models")
        self.assertEqual(v["ollama"], "http://localhost:11434/api/tags")

    def test_url_variants_trailing_slash_and_empty(self):
        self.assertEqual(_url_variants(""), ())
        self.assertEqual(dict(_url_variants("http://x/v1/"))["openai"],
                         "http://x/v1/models")


class TestLocalModels(unittest.TestCase):
    def _fake_store(self, root: Path, entries, tag_as_file: bool = True) -> None:
        """构造假的 Ollama 仓库。

        ⚠️ 真实仓库里 ``<tag>`` 是**文件**（manifest JSON）。
        最初按目录实现，导致本机 9 个模型一个也列不出来 ——
        所以这里默认按文件构造，另有 tag_as_file=False 覆盖目录形态。
        """
        reg = root / "manifests" / "registry.ollama.ai"
        for ns, name, tag in entries:
            d = reg / ns / name
            d.mkdir(parents=True, exist_ok=True)
            if tag_as_file:
                (d / tag).write_text('{"schemaVersion": 2}', encoding="utf-8")
            else:
                (d / tag).mkdir(parents=True, exist_ok=True)

    def test_lists_library_and_namespaced(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            self._fake_store(root, [
                ("library", "deepseek-r1", "8b"),
                ("library", "qwen3.5", "9b"),
                ("sinhang", "qwen3.5-claude-4.6-opus", "27b-q4_K_M"),
            ])
            got = local_ollama_models(str(root))
        # library 下的不加前缀；其它命名空间带前缀
        self.assertIn("deepseek-r1:8b", got)
        self.assertIn("qwen3.5:9b", got)
        self.assertIn("sinhang/qwen3.5-claude-4.6-opus:27b-q4_K_M", got)
        self.assertEqual(got, sorted(got))

    def test_tag_as_directory_also_supported(self):
        """兼容 tag 为目录的形态（不同版本/工具可能有差异）。"""
        with TemporaryDirectory() as td:
            root = Path(td)
            self._fake_store(root, [("library", "m", "1")], tag_as_file=False)
            self.assertEqual(local_ollama_models(str(root)), ["m:1"])

    def test_hidden_entries_skipped(self):
        """不应把 .DS_Store 之类当成模型 tag。"""
        with TemporaryDirectory() as td:
            root = Path(td)
            self._fake_store(root, [("library", "m", "1")])
            reg = root / "manifests" / "registry.ollama.ai"
            (reg / "library" / "m" / ".DS_Store").write_text("x", encoding="utf-8")
            (reg / ".hidden_ns").mkdir(parents=True, exist_ok=True)
            self.assertEqual(local_ollama_models(str(root)), ["m:1"])

    def test_missing_dir_returns_empty(self):
        with TemporaryDirectory() as td:
            self.assertEqual(local_ollama_models(td), [])

    def test_not_a_store_returns_empty(self):
        """目录存在但不是 Ollama 仓库结构 —— 不能误报。"""
        with TemporaryDirectory() as td:
            (Path(td) / "whatever").mkdir()
            self.assertEqual(local_ollama_models(td), [])


# ---------------------------------------------------------------- 网络（本地假服务）

class _Handler(BaseHTTPRequestHandler):
    """按测试注入的行为返回 JSON。"""

    payload = None
    status = 200

    def do_GET(self):  # noqa: N802
        body = json.dumps(self.payload).encode() if self.payload is not None else b""
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):      # 静音
        pass


class _Server:
    def __init__(self, payload, status=200):
        handler = type("H", (_Handler,), {"payload": payload, "status": status})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self) -> str:
        return "http://127.0.0.1:%d/v1" % self.port

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class TestProbe(unittest.TestCase):
    def test_ok_with_models(self):
        srv = _Server({"object": "list", "data": [{"id": "qwen3.5:9b"}]})
        try:
            r = probe(srv.base, timeout=3)
        finally:
            srv.close()
        self.assertTrue(r.ok)
        self.assertTrue(r.reachable)
        self.assertEqual(r.protocol, "openai")
        self.assertEqual(r.models, ["qwen3.5:9b"])
        self.assertEqual(r.error, "")

    def test_reachable_but_no_models(self):
        """网关可达、模型为空 —— 这是本机 GPUStack 的真实情况。"""
        srv = _Server({"object": "list", "data": []})
        try:
            r = probe(srv.base, timeout=3)
        finally:
            srv.close()
        self.assertFalse(r.ok)
        self.assertTrue(r.reachable)
        self.assertIn("没有可用模型", r.error)
        self.assertTrue(r.hints, "应给出可操作建议")

    def test_connection_refused(self):
        """端口关闭：必须返回结构化失败，而不是抛异常。"""
        r = probe("http://127.0.0.1:1/v1", timeout=3)
        self.assertFalse(r.ok)
        self.assertFalse(r.reachable)
        self.assertTrue(r.error)
        self.assertTrue(r.hints)

    def test_empty_url(self):
        r = probe("", timeout=3)
        self.assertFalse(r.ok)
        self.assertIn("为空", r.error)

    def test_auth_failure_message(self):
        srv = _Server({"error": "unauthorized"}, status=401)
        try:
            r = probe(srv.base, timeout=3)
        finally:
            srv.close()
        self.assertFalse(r.ok)
        self.assertIn("认证失败", r.error)

    def test_non_json_response(self):
        """返回 HTML（比如反代首页）时应说明"不是合法 JSON"。"""
        class Html(_Handler):
            def do_GET(self):  # noqa: N802
                body = b"<html>hi</html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Html)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            r = probe("http://127.0.0.1:%d/v1" % port, timeout=3)
        finally:
            httpd.shutdown()
            httpd.server_close()
        self.assertFalse(r.ok)
        self.assertIn("JSON", r.error)


class TestDiagnoseAndReport(unittest.TestCase):
    def test_diagnose_explicit_url_only(self):
        r, allr = diagnose("http://127.0.0.1:1/v1", timeout=3)
        self.assertEqual(len(allr), 1, "显式指定时不应再去猜其它端点")
        self.assertFalse(r.ok)

    def test_candidates_dedup_and_env(self):
        import os
        old = os.environ.get("LLM_BASE_URL")
        os.environ["LLM_BASE_URL"] = "http://example.invalid/v1"
        try:
            c = candidates()
        finally:
            if old is None:
                os.environ.pop("LLM_BASE_URL", None)
            else:
                os.environ["LLM_BASE_URL"] = old
        urls = [u for u, _ in c]
        self.assertEqual(urls[0], "http://example.invalid/v1", "环境变量应排在最前")
        self.assertEqual(len(urls), len(set(urls)), "不应有重复")
        self.assertIn("http://localhost:11434/v1", urls, "应包含常见默认值")

    def test_report_ok_section(self):
        r = ProbeResult(base_url="http://x/v1", ok=True, reachable=True,
                        protocol="openai", models=["m1", "m2"])
        txt = format_report(r, [r], local_models=[])
        self.assertIn("[可用]", txt)
        self.assertIn("m1", txt)

    def test_report_unavailable_with_hints(self):
        r = ProbeResult(base_url="http://x/v1", error="连接被拒绝",
                        hints=["启动服务：`ollama serve`"])
        txt = format_report(r, [r], local_models=["deepseek-r1:8b"])
        self.assertIn("连接被拒绝", txt)
        self.assertIn("ollama serve", txt)
        self.assertIn("deepseek-r1:8b", txt)

    def test_report_lists_other_endpoints(self):
        a = ProbeResult(base_url="http://a/v1", error="x", hints=[])
        b = ProbeResult(base_url="http://b/v1", ok=True, reachable=True,
                        models=["m"], protocol="openai")
        txt = format_report(a, [a, b], local_models=[])
        self.assertIn("其它已探测端点", txt)
        self.assertIn("http://b/v1", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
