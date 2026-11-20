from __future__ import annotations

import sys

from planetary_eos_lab.cli import gui


def test_gui_runs_streamlit_with_current_interpreter_on_localhost(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(gui.subprocess, "run", lambda cmd, check: calls.append(cmd))

    assert gui.main(["--port", "8600"]) == 0

    cmd = calls[0]
    assert cmd[:4] == [sys.executable, "-m", "streamlit", "run"]
    assert cmd[cmd.index("--server.address") + 1] == "127.0.0.1"
    assert cmd[cmd.index("--server.port") + 1] == "8600"
