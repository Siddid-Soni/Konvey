"""Agent 1 compute tools: exact arithmetic and a restricted Python sandbox."""

from konvey.compute import ComputeLog, calc, check_code, make_tools, run_python


def test_calc_exact_and_safe():
    assert calc("log2(1048576)") == "20.0"
    assert calc("17 % 5") == "2"
    assert calc("2^10") == "1024"
    assert calc("__import__('os')").startswith("ERROR")


def test_run_python_traces_a_program():
    out = run_python("a, b = 48, 18\nwhile b:\n    a, b = b, a % b\n    print(a, b)")
    assert out.split("\n")[:3] == ["18 12", "12 6", "6 0"]
    assert run_python("print(math.floor(7 / 2))").strip() == "3"


def test_run_python_blocks_escapes():
    for code in ("import os", "().__class__.__bases__", "open('/etc/passwd')",
                 "eval('1')", "getattr(1, 'real')", "__builtins__"):
        assert check_code(code), code
        assert run_python(code).startswith("REJECTED"), code


def test_run_python_limits():
    assert "CPU limit" in run_python("while True: pass")
    assert "ERROR" in run_python("x = [0] * 10**9")
    assert "ZeroDivisionError" in run_python("1/0")


def test_tools_are_logged():
    log = ComputeLog()
    calc_t, py_t = make_tools(log)
    assert calc_t.__name__ == "calc" and py_t.__name__ == "run_python"
    calc_t("1+1")
    py_t("print(3)")
    assert [c["tool"] for c in log.calls] == ["calc", "run_python"]
    assert log.calls[1]["output"].strip() == "3"
