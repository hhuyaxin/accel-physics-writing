"""能力 B 不变量:SymPy 推导检查既能确认对、也能抓错。"""
import check_algebra as ca
import sympy as sp


def test_equality_true():
    ok, _ = ca.check_equality("(a+b)**2", "a**2+2*a*b+b**2")
    assert ok


def test_equality_false_reports_missing_cross_term():
    ok, diff = ca.check_equality("(a+b)**2", "a**2+b**2")
    assert not ok
    a, b = sp.Symbol("a"), sp.Symbol("b")
    assert sp.simplify(diff - 2 * a * b) == 0   # 差异项正是 2ab


def test_equality_with_subs():
    ok, _ = ca.check_equality("(beta*gamma)**2", "gamma**2-1",
                              {sp.Symbol("gamma"): 1 / sp.sqrt(1 - sp.Symbol("beta")**2)})
    assert ok


def test_dimension_consistent():
    ok, _ = ca.check_dimension("eps_n", "beta*gamma*eps",
                               ca._parse_assign("eps_n=L,eps=L,beta=1,gamma=1", ca._BASE_NS))
    assert ok


def test_dimension_catches_error():
    # E=mc 少了一个 c,量纲必须被抓出
    ok, _ = ca.check_dimension("E", "m*c",
                               ca._parse_assign("E=M*L**2/T**2,m=M,c=L/T", ca._BASE_NS))
    assert not ok


def test_limit_finite():
    ok, _ = ca.check_limit("1/gamma**2", "gamma", "oo", "0")
    assert ok


def test_limit_onesided_infinite():
    ok, _ = ca.check_limit("1/sqrt(1-beta**2)", "beta", "1", "oo", direction="-")
    assert ok


def test_selftest_passes():
    assert ca.selftest() == 0
