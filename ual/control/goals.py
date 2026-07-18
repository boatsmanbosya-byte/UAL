"""
Goal — первая функция полезности в системе: отвечает на вопрос "ЗАЧЕМ
менять язык", а не только "МОЖНО ли" (см. дневник, раздел 20).

Goal — объект (не число): name, evaluator(rules) -> score, weight.
Это поддерживает несколько одновременных целей (многокритериальная
оптимизация), а не единственный порог.

ЧЕСТНО: выбор корпуса эталонных термов для evaluator — это ровно та же
проблема grounding'а "направленного интеллекта", сформулированная в
самом начале проекта (дневник, раздел 1, проблема №4). Goal её не
решает, а корректно локализует в одном месте — выбор корпуса всё ещё
требует человека.
"""
from dataclasses import dataclass
from typing import Callable, List
from ..rules.trs import Rule, normalize, ast_size, SExpr


@dataclass
class Goal:
    name: str
    evaluator: Callable[[List[Rule]], float]  # rules -> score (больше = лучше)
    weight: float = 1.0

    def score(self, rules: List[Rule]) -> float:
        return self.evaluator(rules)


def make_minimize_normal_form_size_goal(corpus: List[SExpr], max_steps: int = 50) -> Goal:
    """Goal(L) = -mean(ast_size(нормальная форма термa)) по корпусу термов.
    НЕ число шагов до нормальной формы: без правил терм тривиально уже
    "нормален" за 0 шагов (ничего не может примениться), поэтому счёт шагов
    даёт ОБРАТНЫЙ знак — рабочее правило всегда требует БОЛЬШЕ шагов, чем
    пустой набор правил, хотя РЕЗУЛЬТАТ при этом становится меньше и проще.
    (Это была первая версия функции — ошибка найдена и исправлена, см.
    дневник, раздел 20: 'ReduceRewriteSteps' переименован и переопределён.)"""
    def evaluator(rules: List[Rule]) -> float:
        total_size = 0
        for term in corpus:
            normal_form, _, terminated = normalize(rules, term, max_steps=max_steps)
            total_size += ast_size(normal_form) if terminated else ast_size(term) * 10  # штраф за незавершённость
        return -total_size / len(corpus)
    return Goal(name="MinimizeNormalFormSize", evaluator=evaluator)


def delta_goal(goal: Goal, rules_before: List[Rule], rules_after: List[Rule]) -> float:
    return goal.score(rules_after) - goal.score(rules_before)


def efficiency(delta_g: float, raw_d: float) -> float:
    """η = ΔGoal / d — benefit-cost ratio (НЕ физический КПД: delta_g и
    raw_d в разных единицах — см. дневник, раздел 20, уточнение
    терминологии). Полезно для СРАВНЕНИЯ кандидатов между собой."""
    if raw_d == 0:
        return float("inf") if delta_g > 0 else 0.0
    return delta_g / raw_d


if __name__ == "__main__":
    from ..metrics.distance import snapshot, compute_distance
    from ..core.minilisp import standard_env

    rule_add_zero = Rule("add-zero", ["+", "?x", 0], "?x")
    rule_mul_one = Rule("mul-one", ["*", "?x", 1], "?x")

    # Два корпуса, отражающие РАЗНЫЕ домены задач — это и есть тот самый
    # выбор, который делает человек, а не Goal сам по себе.
    corpus_addition_heavy = [
        ["+", "a", 0], ["+", ["+", "b", 0], 0], ["+", "c", 0],
        ["+", ["+", "d", 0], ["+", "e", 0]], ["+", "f", 0],
    ]
    corpus_multiplication_heavy = [
        ["*", "a", 1], ["*", ["*", "b", 1], 1], ["*", "c", 1],
        ["*", ["*", "d", 1], ["*", "e", 1]], ["*", "f", 1],
    ]

    goal_add = make_minimize_normal_form_size_goal(corpus_addition_heavy)
    goal_mul = make_minimize_normal_form_size_goal(corpus_multiplication_heavy)

    # Настоящий d (не заглушка!) — через реальный снимок живой системы,
    # как и договаривались после найденной ранее ошибки честности.
    def real_d(rule: Rule) -> float:
        env = standard_env()
        before = snapshot(env)
        env["__rules__"].append(rule)
        after = snapshot(env)
        d_total, _, _ = compute_distance(before, after)
        return d_total

    d_add = real_d(rule_add_zero)
    d_mul = real_d(rule_mul_one)

    print("=== ПРОВЕРКА УТВЕРЖДЕНИЯ: 'полезность — отношение (rule, goal), не свойство правила' ===\n")
    print(f"d(add-zero) = {d_add:.2f}   d(mul-one) = {d_mul:.2f}   (ожидаем: равны)\n")

    for corpus_name, goal in [("корпус СЛОЖЕНИЙ", goal_add), ("корпус УМНОЖЕНИЙ", goal_mul)]:
        print(f"--- {corpus_name} ---")
        dg_add = delta_goal(goal, [], [rule_add_zero])
        dg_mul = delta_goal(goal, [], [rule_mul_one])
        eta_add = efficiency(dg_add, d_add)
        eta_mul = efficiency(dg_mul, d_mul)
        print(f"  add-zero: ΔGoal={dg_add:+.2f}  η={eta_add:+.3f}")
        print(f"  mul-one:  ΔGoal={dg_mul:+.2f}  η={eta_mul:+.3f}")
        winner = "add-zero" if dg_add > dg_mul else ("mul-one" if dg_mul > dg_add else "ничья")
        print(f"  Победитель на этом корпусе: {winner}\n")
