"""
mini-Lisp: минимальное гомоиконичное ядро на чистом CPython.
Код = данные (списки Python). eval — первоклассный примитив внутри языка.
Библиотечный модуль — демо вынесены в if __name__ == "__main__".
"""
from typing import Any, Dict, List
from ..rules.trs import Rule, normalize


def tokenize(s: str) -> List[str]:
    return s.replace("(", " ( ").replace(")", " ) ").split()


def parse(tokens: List[str]):
    if len(tokens) == 0:
        raise SyntaxError("неожиданный конец ввода")
    token = tokens.pop(0)
    if token == "(":
        items = []
        while tokens[0] != ")":
            items.append(parse(tokens))
        tokens.pop(0)
        return items
    elif token == ")":
        raise SyntaxError("лишняя ')'")
    else:
        return atomize(token)


def atomize(token: str):
    try:
        return int(token)
    except ValueError:
        try:
            return float(token)
        except ValueError:
            return token


def read(program: str):
    return parse(tokenize(program))


class Env(dict):
    def __init__(self, params=(), args=(), outer=None):
        self.update(zip(params, args))
        self.outer = outer

    def find(self, var: str) -> "Env":
        if var in self:
            return self
        if self.outer is None:
            raise NameError(f"необъявленное имя: {var}")
        return self.outer.find(var)


class Procedure:
    def __init__(self, params, body, env: "Env"):
        self.params, self.body, self.env = params, body, env

    def __call__(self, *args):
        local_env = Env(self.params, args, self.env)
        return leval(self.body, local_env)


def standard_env() -> Env:
    import operator as op
    import functools
    env = Env()
    rules_table: List[Rule] = []   # своя, изолированная таблица правил на каждое окружение
    env["__rules__"] = rules_table  # доступна извне (например, для generator.py)
    env.update({
        "+": lambda *a: sum(a), "-": lambda a, b: a - b,
        "*": lambda *a: functools.reduce(op.mul, a, 1),
        "/": op.truediv, ">": op.gt, "<": op.lt, ">=": op.ge, "<=": op.le, "=": op.eq,
        "car": lambda x: x[0], "cdr": lambda x: x[1:], "cons": lambda a, b: [a] + b,
        "list": lambda *a: list(a), "null?": lambda x: x == [],
        "eq?": lambda a, b: a == b, "not": lambda x: not x,
        "print": lambda *a: print(*a),
        "eval": lambda expr: leval(expr, env),
        "define-rule": lambda name, pattern, repl: (rules_table.append(Rule(name, pattern, repl)), None)[1],
        "rewrite": lambda term: normalize(rules_table, term)[0],
    })
    return env


def leval(x, env: Env):
    if isinstance(x, str):
        return env.find(x)[x]
    elif not isinstance(x, list):
        return x
    op_, *args = x
    if op_ == "quote":
        return args[0]
    elif op_ == "if":
        test, conseq, alt = args
        branch = conseq if leval(test, env) else alt
        return leval(branch, env)
    elif op_ == "define":
        name, expr = args
        env[name] = leval(expr, env)
        return None
    elif op_ == "set!":
        name, expr = args
        env.find(name)[name] = leval(expr, env)
        return None
    elif op_ == "lambda":
        params, body = args
        return Procedure(params, body, env)
    elif op_ == "begin":
        result = None
        for expr in args:
            result = leval(expr, env)
        return result
    else:
        proc = leval(op_, env)
        vals = [leval(a, env) for a in args]
        return proc(*vals)


def run(program_text: str, env: Env):
    return leval(read(program_text), env)


if __name__ == "__main__":
    env = standard_env()
    run("(define square (lambda (x) (* x x)))", env)
    print("(square 5) =", run("(square 5)", env))
    print("eval(list '+ 1 2) =", run("(eval (list (quote +) 1 2))", env))
