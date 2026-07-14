import json
import sys
from types import SimpleNamespace

import ai_web_explorer
from ai_web_explorer import loop as loop_module


def test_explore_cli_writes_web_kobe_collector_output(
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "web_kobe.json"
    created = {}

    class FakeExploreLoop:
        def __init__(self, domain, url, openai_client, config):
            created["domain"] = domain
            created["url"] = url
            created["collector"] = config.collector

        def start(self):
            return None

        def print_graph(self):
            return None

        def print_json(self, simple=True):
            return None

        def stop(self):
            return None

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(
        sys.modules,
        "dotenv",
        SimpleNamespace(load_dotenv=lambda: None),
    )
    monkeypatch.setattr(loop_module, "ExploreLoop", FakeExploreLoop)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "explore",
            "example.test",
            "-i",
            "1",
            "--web-kobe-output",
            str(output_path),
        ],
    )

    ai_web_explorer.main()

    assert created["domain"] == "example.test"
    assert created["url"] == "http://example.test"
    assert created["collector"] is not None
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["schema_version"] == "web-kobe-graph-v1"
    assert data["meta"]["app"] == "example.test"
