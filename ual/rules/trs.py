"""
Минимальный движок переписывания термов (Term Rewriting System) над S-выражениями.
Библиотечный модуль — без побочных эффектов при импорте (демо/тесты вынесены
в блок if __name__ == "__main__").
"""
from typing import Union, List, Dict, Optional, Tuple
import random

SExpr = Union[str, int, float, List['SExpr']]


def is_var(token) -> bool:
    return isinstance(token, str) and token.startswith("?")


def match(pattern: SExpr, term: SExpr, bindings: Optional[Dict[str, SExpr]] = None) -> Optional[Dict[str, SExpr]]:
    if bindings is None:
        bindings = {}
    if is_var(pattern):
        if pattern in bindings:
            return bindings if bindings[pattern] == term else None
        new_bindings = dict(bindings)
        new_bindings[pattern] = term
        return new_bindings
    if not isinstance(pattern, list):
        # Любой атом, не являющийся переменной паттерна: строка, int, float —
        # сравниваем на равенство напрямую (важно: раньше здесь была ветка
        # только для str, из-за чего числовые атомы int/float ошибочно
        # проваливались в ветку для списков и матчинг всегда проваливался).
        return bindings if pattern == term else None
    if not isinstance(term, list) or len(pattern) != len(term):
        return None
    for p_sub, t_sub in zip(pattern, term):
        bindings = match(p_sub, t_sub, bindings)
        if bindings is None:
            return None
    return bindings


def substitute(template: SExpr, bindings: Dict[str, SExpr]) -> SExpr:
    if is_var(template):
        return bindings.get(template, template)
    if isinstance(template, list):
        return [substitute(t, bindings) for t in template]
    return template


def ast_size(node: SExpr) -> int:
    if isinstance(node, list):
        return 1 + sum(ast_size(c) for c in node)
    return 1


def count_var_occurrences(node: SExpr, counts: Optional[Dict[str, int]] = None) -> Dict[str, int]:
    if counts is None:
        counts = {}
    if is_var(node):
        counts[node] = counts.get(node, 0) + 1
    elif isinstance(node, list):
        for c in node:
            count_var_occurrences(c, counts)
    return counts


def extract_vars(node: SExpr) -> List[str]:
    return sorted(set(count_var_occurrences(node).keys()))


class Rule:
    def __init__(self, name: str, pattern: SExpr, replacement: SExpr):
        self.name = name
        self.pattern = pattern
        self.replacement = replacement

    def __repr__(self):
        return f"{self.name}: {self.pattern} -> {self.replacement}"


def try_apply_rule(rule: Rule, term: SExpr) -> Optional[SExpr]:
    bindings = match(rule.pattern, term)
    if bindings is not None:
        return substitute(rule.replacement, bindings)
    return None


def rewrite_step(rules: List[Rule], term: SExpr) -> Tuple[SExpr, Optional[str]]:
    for rule in rules:
        result = try_apply_rule(rule, term)
        if result is not None:
            return result, rule.name
    if isinstance(term, list):
        for i, sub in enumerate(term):
            new_sub, applied = rewrite_step(rules, sub)
            if applied is not None:
                new_term = list(term)
                new_term[i] = new_sub
                return new_term, applied
    return term, None


def normalize(rules: List[Rule], term: SExpr, max_steps: int = 50) -> Tuple[SExpr, List[str], bool]:
    trace = []
    current = term
    for _ in range(max_steps):
        new_term, applied = rewrite_step(rules, current)
        if applied is None:
            return current, trace, True
        trace.append(f"{applied}: {current} -> {new_term}")
        current = new_term
    return current, trace, False


def check_confluence(rules: List[Rule], term: SExpr, n_shuffles: int = 8, max_steps: int = 50) -> Tuple[bool, List[SExpr]]:
    # Эмпирическая (не доказательная!) проверка: разный порядок правил -> одна ли нормальная форма
    results = []
    for i in range(n_shuffles):
        shuffled = list(rules)
        random.Random(i).shuffle(shuffled)
        nf, _, terminated = normalize(shuffled, term, max_steps)
        results.append(nf if terminated else None)
    all_same = all(r == results[0] for r in results) and results[0] is not None
    return all_same, results


if __name__ == "__main__":
    good_rules = [
        Rule("add-zero-r", ["add", "?x", "0"], "?x"),
        Rule("add-zero-l", ["add", "0", "?x"], "?x"),
        Rule("mul-one-r", ["mul", "?x", "1"], "?x"),
        Rule("mul-zero-r", ["mul", "?x", "0"], "0"),
    ]
    test_term = ["add", ["mul", "x", "1"], "0"]
    print("=== ЭКСПЕРИМЕНТ 1: терминация + конфлюэнтность ===")
    nf, trace, terminated = normalize(good_rules, test_term)
    print(f"Нормальная форма: {nf}  |  Терминировано: {terminated}")
    for line in trace:
        print("  " + line)
    confluent, variants = check_confluence(good_rules, test_term)
    print(f"Конфлюэнтность: {'ПОДТВЕРЖДЕНА' if confluent else 'НАРУШЕНА'}  {variants}")

    bad_rules = [Rule("f-to-g", ["f", "?x"], ["g", "?x"]), Rule("g-to-f", ["g", "?x"], ["f", "?x"])]
    print("\n=== ЭКСПЕРИМЕНТ 2: нетерминирующийся набор ===")
    nf2, trace2, terminated2 = normalize(bad_rules, ["f", "a"], max_steps=10)
    print(f"Терминировано за 10 шагов: {terminated2} (ожидаем False)")
