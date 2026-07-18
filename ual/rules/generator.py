"""
Генератор кандидатов правил переписывания — эвристический/шаблонный (не ML),
как и договаривались: "пусть примитивный, случайный/эвристический".

КЛЮЧЕВОЙ ПРИНЦИП: две НЕЗАВИСИМЫЕ проверки перед автономным принятием правила:

1. is_size_safe   — ГАРАНТИРУЕТ терминацию (правило не зациклит систему).
                     Это простой, но строгий критерий: если правая часть
                     правила при ЛЮБОЙ подстановке переменных не длиннее
                     левой (skeleton-размер меньше И ни одна переменная не
                     встречается справа чаще, чем слева) — размер терма
                     строго убывает при каждом применении. А поскольку размер
                     — натуральное число, бесконечно убывать он не может:
                     значит, ЛЮБОЙ набор таких правил гарантированно
                     терминирует, независимо от порядка применения.
                     Это НЕ эвристика — это доказуемый факт (стандартный
                     приём теории переписывания термов: size-decreasing
                     reduction ordering).

2. semantic_check — ГАРАНТИРУЕТ (эмпирически, через много случайных
                     подстановок) семантическую корректность: что левая и
                     правая часть правила при любых значениях переменных
                     дают ОДИНАКОВЫЙ результат вычисления.

ВАЖНО: это две РАЗНЫЕ оси. Правило может быть терминирующим (безопасным
в смысле "не зависнет") и при этом семантически НЕВЕРНЫМ (тихо ломающим
программу). Автономное принятие без человека допустимо только когда
пройдены ОБЕ проверки.
"""
import random
from typing import Dict, List, Tuple
from .trs import Rule, SExpr, ast_size, count_var_occurrences, substitute, extract_vars

BINARY_OPS = ["+", "*", "-"]
CONST_POOL = [0, 1]


def is_size_safe(rule: Rule) -> bool:
    """Гарантирует терминацию: skeleton-размер строго убывает при любой подстановке."""
    pattern_vars = count_var_occurrences(rule.pattern)
    repl_vars = count_var_occurrences(rule.replacement)
    for v, cnt in repl_vars.items():
        if cnt > pattern_vars.get(v, 0):
            return False  # переменная используется справа чаще, чем слева -> размер не гарантированно убывает
    return ast_size(rule.replacement) < ast_size(rule.pattern)


def semantic_check(rule: Rule, evaluator, n_trials: int = 25, value_range=(-10, 10)) -> bool:
    """Эмпирическая проверка корректности: для n_trials случайных подстановок
    переменных левая и правая часть правила должны вычисляться в одно и то же значение.
    evaluator(ground_term) -> число, независимый "оракул" семантики (реальный интерпретатор)."""
    variables = extract_vars(rule.pattern) or extract_vars(rule.replacement)
    if not variables:
        try:
            return evaluator(rule.pattern) == evaluator(rule.replacement)
        except Exception:
            return False
    for _ in range(n_trials):
        bindings = {v: random.randint(*value_range) for v in variables}
        lhs_ground = substitute(rule.pattern, bindings)
        rhs_ground = substitute(rule.replacement, bindings)
        try:
            if evaluator(lhs_ground) != evaluator(rhs_ground):
                return False
        except Exception:
            return False
    return True


def propose_candidates(n: int, seed: int = 0, include_broken: bool = True) -> List[Rule]:
    """Генерирует n кандидатов по небольшому набору алгебраических шаблонов.
    include_broken=True: специально подмешивает заведомо НЕВЕРНЫЕ правила
    (например (+ ?x 0) -> 0 вместо -> ?x), чтобы честно проверить, что
    semantic_check их действительно отлавливает, а не просто заявлен как отлавливающий."""
    rng = random.Random(seed)
    candidates = []
    for i in range(n):
        op = rng.choice(BINARY_OPS)
        const = rng.choice(CONST_POOL)
        shape = rng.choice(["identity_right", "identity_left", "collapse_to_const", "commute"])
        broken = include_broken and rng.random() < 0.35  # ~35% кандидатов — намеренно испорчены

        if shape == "commute":
            # Коммутативность НЕ уменьшает размер (обе части — одинаковой формы),
            # значит is_size_safe=False и кандидат уйдёт в NEEDS_REVIEW, если
            # верен (для + и *), либо в REJECTED, если неверен (для -).
            # Отдельной "испорченной" версии здесь нет — корректность и так
            # зависит только от op, свободная переменная другого рода порчи не нужна.
            pattern = [op, "?x", "?y"]
            replacement = [op, "?y", "?x"]
        elif shape == "identity_right":
            pattern = [op, "?x", const]
            replacement = const if broken else "?x"   # испорченная версия: коллапсирует в константу вместо ?x
        elif shape == "identity_left":
            pattern = [op, const, "?x"]
            replacement = const if broken else "?x"
        else:  # collapse_to_const
            pattern = [op, "?x", const]
            replacement = "?x" if broken else const    # испорченная версия: должно быть const, но "исправлено" на ?x

        broken_label = "_BROKEN" if (broken and shape != "commute") else ""
        name = f"cand_{i}_{op}_{shape}{broken_label}"
        candidates.append(Rule(name, pattern, replacement))
    return candidates


def classify_candidates(candidates: List[Rule], evaluator) -> Dict[str, List[Rule]]:
    buckets = {"AUTO_ACCEPT": [], "NEEDS_REVIEW": [], "REJECTED": []}
    for rule in candidates:
        if not semantic_check(rule, evaluator):
            buckets["REJECTED"].append(rule)
        elif is_size_safe(rule):
            buckets["AUTO_ACCEPT"].append(rule)
        else:
            buckets["NEEDS_REVIEW"].append(rule)
    return buckets


if __name__ == "__main__":
    from ..core.minilisp import standard_env, leval

    env = standard_env()

    def evaluator(ground_term) -> float:
        # "Оракул" семантики: реальный интерпретатор mini-Lisp вычисляет ground-терм
        return leval(ground_term, env)

    candidates = propose_candidates(n=20, seed=42)
    buckets = classify_candidates(candidates, evaluator)

    print(f"Сгенерировано кандидатов: {len(candidates)}")
    for tier in ["AUTO_ACCEPT", "NEEDS_REVIEW", "REJECTED"]:
        print(f"\n--- {tier} ({len(buckets[tier])}) ---")
        for r in buckets[tier]:
            print(" ", r)

    # ЧЕСТНЫЙ аудит: сравниваем решение классификатора не с именем "BROKEN"
    # (эта метка сама может быть неверно присвоена генератором — см. разбор),
    # а с результатом независимой стресс-проверки на 200 случайных x
    # (вместо 25, используемых при классификации) — это ближе к "истине",
    # хотя формально та же природа проверки (эмпирическая, не аналитическая).
    print(f"\n=== НЕЗАВИСИМЫЙ АУДИТ (200 случайных x вместо 25) ===")
    false_positives = 0  # классификатор принял (AUTO_ACCEPT/NEEDS_REVIEW), а правило на деле неверно
    false_negatives = 0  # классификатор отверг (REJECTED), а правило на деле верно
    for rule in candidates:
        really_valid = semantic_check(rule, evaluator, n_trials=200, value_range=(-50, 50))
        was_accepted = rule in buckets["AUTO_ACCEPT"] or rule in buckets["NEEDS_REVIEW"]
        if was_accepted and not really_valid:
            false_positives += 1
            print(f"  ЛОЖНОЕ ПРИНЯТИЕ: {rule}")
        elif not was_accepted and really_valid:
            false_negatives += 1
            print(f"  ЛОЖНЫЙ ОТКАЗ:    {rule}")
    print(f"Ложных принятий (опасно): {false_positives}  |  Ложных отказов (излишняя осторожность): {false_negatives}")
