#!/usr/bin/env python3
"""
check_algebra.py —— 推导机械检查(SymPy 真算,不靠模型直觉)。实现 CLAUDE.md §5 / derivation_checks.md。

设计:供 AI 助手把用户的推导翻译成结构化调用后逐项核验,也可命令行直接用。
每项返回 ✓ / ✗ + 简述;发现问题指出具体差异,而非笼统结论。

子命令:
  equality   验证一步 "LHS = RHS"(可带变量替换)是否符号等价
  dimension  验证等式两边量纲是否一致(符号→量纲用 M,L,T,I,Theta 基)
  limit      令某变量趋某值,验证是否退回期望的简单情形
  selftest   用真实加速器物理例子自测(展示既能算对、也能抓错)

示例:
  check_algebra.py equality "(beta*gamma)**2" "gamma**2-1" --subs "gamma=1/sqrt(1-beta**2)"
  check_algebra.py dimension "eps_n" "beta*gamma*eps" --dims "eps_n=L,eps=L,beta=1,gamma=1"
  check_algebra.py limit "1/gamma**2" --var gamma --to oo --expect 0
"""
from __future__ import annotations
import argparse, re, sys
import sympy as sp

BASE = sp.symbols("M L T I Theta", positive=True)   # 质量/长度/时间/电流/温度
_BASE_NS = {str(b): b for b in BASE}

# 这些名字保留为 SymPy 的函数/常量,其余裸标识符一律当普通符号
# (否则 beta/gamma/E/I/N/S/Q 等会被解释成内置特殊函数或常量)
_KEEP = {"sqrt", "exp", "log", "sin", "cos", "tan", "cot", "sec", "csc",
         "asin", "acos", "atan", "atan2", "sinh", "cosh", "tanh",
         "Abs", "floor", "ceiling", "Min", "Max", "pi", "oo"}


def _sym(expr):
    """把字符串解析成表达式;裸标识符强制为普通符号,避免与内置函数/常量冲突。"""
    if isinstance(expr, sp.Basic):
        return expr
    names = set(re.findall(r"[A-Za-z_]\w*", str(expr)))
    loc = {n: sp.Symbol(n) for n in names if n not in _KEEP}
    return sp.sympify(expr, locals=loc, rational=True)


def _parse_assign(s: str | None, ns: dict | None = None) -> dict:
    """'a=expr, b=expr2' → {Symbol(a): expr, ...}。"""
    out = {}
    for part in (s or "").split(","):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[sp.Symbol(k.strip())] = sp.sympify(v.strip(), locals=ns or {})
    return out


# ---------- ① 符号代数验证 ----------
def check_equality(lhs, rhs, subs: dict | None = None):
    L, R = _sym(lhs), _sym(rhs)
    if subs:
        L, R = L.subs(subs), R.subs(subs)
    diff = sp.simplify(L - R)
    if diff != 0:
        diff = sp.simplify(sp.radsimp(sp.expand(diff)))
    return diff == 0, diff


# ---------- ② 量纲检查 ----------
class DimError(Exception):
    pass


def dim_of(expr, dims: dict):
    expr = _sym(expr)
    if expr.is_Number:
        return sp.Integer(1)
    if expr.is_Symbol:
        if expr in BASE:
            return expr
        if expr in dims:
            return dims[expr]
        raise DimError(f"符号未声明量纲:{expr}")
    if isinstance(expr, sp.Add):
        ds = [dim_of(a, dims) for a in expr.args]
        for d in ds[1:]:
            if sp.simplify(d / ds[0]) != 1:
                raise DimError(f"相加项量纲不一致:[{ds[0]}] vs [{d}]")
        return ds[0]
    if isinstance(expr, sp.Mul):
        r = sp.Integer(1)
        for a in expr.args:
            r *= dim_of(a, dims)
        return sp.simplify(r)
    if isinstance(expr, sp.Pow):
        base, exp = expr.args
        if not exp.is_number:
            if sp.simplify(dim_of(base, dims)) != 1:
                raise DimError(f"指数为符号时底必须无量纲:{expr}")
            return sp.Integer(1)
        return sp.simplify(dim_of(base, dims) ** exp)
    if expr.is_Function:  # sin/exp/log… 宗量须无量纲,结果无量纲
        for a in expr.args:
            if sp.simplify(dim_of(a, dims)) != 1:
                raise DimError(f"超越函数宗量必须无量纲:{expr}")
        return sp.Integer(1)
    raise DimError(f"无法判定量纲:{expr}")


def check_dimension(lhs, rhs, dims: dict):
    try:
        dl, dr = dim_of(lhs, dims), dim_of(rhs, dims)
    except DimError as e:
        return False, str(e)
    return sp.simplify(dl / dr) == 1, f"左 [{dl}]  右 [{dr}]"


# ---------- ③ 极限 / 特例 ----------
def check_limit(expr, var: str, to, expect, direction: str = "+"):
    """direction: '+' 从右趋近 / '-' 从左趋近(物理极限常为单侧,如 β→1⁻)。"""
    e = _sym(expr)
    v = sp.Symbol(var)
    pt = sp.oo if str(to) in ("oo", "inf", "+oo") else (-sp.oo if str(to) in ("-oo", "-inf") else _sym(to))
    got = sp.limit(e, v, pt, dir=direction)
    exp = _sym(expect)
    special = (sp.oo, -sp.oo, sp.zoo, sp.nan)
    ok = (got == exp) if (got in special or exp in special) else (sp.simplify(got - exp) == 0)
    return ok, f"极限({var}→{to}{'⁻' if direction=='-' else ''})={got}, 期望={exp}"


def leading_term(expr, var: str):
    """var→0 的最低阶项(用于'退回已知简单情形'的展示)。"""
    e, v = _sym(expr), sp.Symbol(var)
    return sp.simplify(e.as_leading_term(v))


# ---------- ④ 数量级 ----------
def order_of_magnitude(expr, subs: dict):
    e = _sym(expr).subs({sp.Symbol(k): v for k, v in subs.items()})
    val = sp.N(e)
    order = int(sp.floor(sp.log(sp.Abs(val), 10))) if val != 0 else None
    return val, order


# ---------- 自测 ----------
def selftest() -> int:
    print("=" * 60)
    print(" check_algebra 自测(真实加速器物理例子)")
    print("=" * 60)
    g = sp.Symbol("gamma")
    b = sp.Symbol("beta")
    fails = 0

    ok, diff = check_equality("(beta*gamma)**2", "gamma**2-1",
                              subs={g: 1 / sp.sqrt(1 - b**2)})
    print(f"① 代数  (βγ)²=γ²−1            : {'✓' if ok else '✗'}  (差={diff})")
    fails += not ok

    ok, info = check_dimension("eps_n", "beta*gamma*eps",
                               _parse_assign("eps_n=L,eps=L,beta=1,gamma=1", _BASE_NS))
    print(f"② 量纲  εₙ=βγε               : {'✓' if ok else '✗'}  ({info})")
    fails += not ok

    ok, info = check_dimension("E", "m*c",
                               _parse_assign("E=M*L**2/T**2,m=M,c=L/T", _BASE_NS))
    caught = not ok
    print(f"②' 量纲  E=mc(故意写错)      : {'✓ 抓到错误' if caught else '✗ 漏判'}  ({info})")
    fails += not caught

    ok, info = check_limit("1/gamma**2", "gamma", "oo", "0")
    print(f"③ 极限  空间电荷 1/γ² (γ→∞)  : {'✓' if ok else '✗'}  ({info})")
    fails += not ok

    lead = leading_term("(1/sqrt(1-beta**2)-1)*m*c**2", "beta")
    expect = _sym("m*c**2*beta**2/2")
    ok = sp.simplify(lead - expect) == 0
    print(f"③' 特例  动能 β→0 最低阶       : {'✓' if ok else '✗'}  (得 {lead})")
    fails += not ok

    val, order = order_of_magnitude("E/m", {"E": 1000, "m": sp.Rational(511, 1000)})  # MeV
    ok = order == 3
    print(f"④ 数量级 1GeV 电子 γ=E/mc²    : {'✓' if ok else '✗'}  γ≈{float(val):.0f}(量级 10^{order})")
    fails += not ok

    print("-" * 60)
    print(f"结果:{'全部通过 ✓' if fails == 0 else f'{fails} 项异常 ✗'}")
    print("注:机械检查能抓量纲/代数/极限类错误,不保证物理建模本身正确。")
    return 1 if fails else 0


# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="推导机械检查(SymPy)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("equality", help="验证 LHS=RHS 是否符号等价")
    pe.add_argument("lhs"); pe.add_argument("rhs")
    pe.add_argument("--subs", default=None, help="变量替换,如 'gamma=1/sqrt(1-beta**2)'")

    pd = sub.add_parser("dimension", help="验证等式两边量纲一致")
    pd.add_argument("lhs"); pd.add_argument("rhs")
    pd.add_argument("--dims", required=True, help="符号量纲,如 'eps=L,beta=1'(基:M,L,T,I,Theta)")

    pl = sub.add_parser("limit", help="验证极限/特例")
    pl.add_argument("expr")
    pl.add_argument("--var", required=True); pl.add_argument("--to", required=True)
    pl.add_argument("--expect", required=True)
    pl.add_argument("--dir", default="+", choices=["+", "-"], help="趋近方向(默认 + 从右;物理单侧极限用 -)")

    sub.add_parser("selftest", help="用真实物理例子自测")

    a = ap.parse_args()
    if a.cmd == "selftest":
        sys.exit(selftest())
    if a.cmd == "equality":
        subs = _parse_assign(a.subs) if a.subs else None
        # --subs 里的值也要走安全解析(beta/gamma 等)
        if subs:
            subs = {k: _sym(str(v)) for k, v in subs.items()}
        ok, diff = check_equality(a.lhs, a.rhs, subs)
        print(f"{'✓ 等价' if ok else '✗ 不等价'}  (LHS−RHS 化简 = {diff})")
        sys.exit(0 if ok else 1)
    if a.cmd == "dimension":
        ok, info = check_dimension(a.lhs, a.rhs, _parse_assign(a.dims, _BASE_NS))
        print(f"{'✓ 量纲一致' if ok else '✗ 量纲不符'}  ({info})")
        sys.exit(0 if ok else 1)
    if a.cmd == "limit":
        ok, info = check_limit(a.expr, a.var, a.to, a.expect, a.dir)
        print(f"{'✓ 退回期望情形' if ok else '✗ 与期望不符'}  ({info})")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
