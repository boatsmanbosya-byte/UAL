"""
Policy — центральный объект принятия решений (см. дневник, раздел 21):
Ψ = f(Goals, Constraints, Knowledge, Policy, Trust).

До этого момента Ψ был выражен последовательностью пороговых if внутри
psi_step, консультируясь только с Safety/Correctness (tier из
generator.py) и d/κ (distance.py/psi.py) — но НЕ с Goals. Из-за этого
безопасное и корректное правило, вредящее цели, проходило бы автоматически
без единой проверки "а оно вообще полезно?". Policy закрывает этот пробел.

ДВА РЕЖИМА — с явно разной ценой компромисса (см. обсуждение η):
  - scalar: Score = w_eta*η - w_d*d + w_alpha*α - w_risk*Risk
            Одно число, легко ранжировать; но веса произвольны — та же
            проблема, что и с κ, можно "спрятать" плохое решение подбором
            весов.
  - pareto: каждый критерий проверяется ОТДЕЛЬНО по своему порогу, ничего
            не сворачивается в одно число — но требует настройки НЕСКОЛЬКИХ
            порогов вместо одних весов. Не более "объективно", просто
            произвольно по-другому. Пользователь предпочёл этот режим по
            умолчанию явно ("или, ещё лучше, как многокритериальную
            политику без сведения всего к одной скалярной оценке").

ЧЕСТНО: все константы ниже (веса, пороги) — дизайнерские, не
калиброванные на реальных операторах, как и κ/C(K) до этого.
"""
from dataclasses import dataclass
from typing import Literal, Optional
from .psi import KAPPA

Decision = Literal["auto_accept", "human_review", "reject"]


@dataclass
class DecisionContext:
    name: str
    tier: str                    # AUTO_ACCEPT / NEEDS_REVIEW / REJECTED — из generator.py
    d: float                     # metrics/distance.py — структурная стоимость
    eta: float                   # control/goals.py — полезность на единицу стоимости
    alpha: float                 # control/autonomy.py — текущая автономия
    risk: Optional[float] = None  # если не задан — выводится из tier через (1 - κ)

    def __post_init__(self):
        if self.risk is None:
            # ВАЖНО (найдено и исправлено при тестировании): risk должен
            # указывать в ТУ ЖЕ сторону, что и κ — низкое κ (AUTO_ACCEPT,
            # дважды верифицировано) означает НИЗКИЙ риск, а не высокий.
            # Первая версия ошибочно брала risk = 1 - κ, инвертируя смысл:
            # самый надёжный уровень (AUTO_ACCEPT) получал risk=0.7, как
            # будто он самый рискованный. κ и есть risk напрямую.
            self.risk = KAPPA.get(self.tier, 1.0)


@dataclass
class Policy:
    mode: Literal["scalar", "pareto"] = "pareto"

    # веса для scalar-режима
    w_eta: float = 1.0
    w_d: float = 0.1
    w_alpha: float = 0.5
    w_risk: float = 2.0
    scalar_threshold: float = 0.0

    # пороги для pareto-режима
    eta_min: float = 0.0             # изменение не должно ухудшать цель
    risk_max_for_auto: float = 0.35  # выше этого — не доверяем автоматике даже при tier=AUTO_ACCEPT

    def scalar_score(self, ctx: DecisionContext) -> float:
        return (self.w_eta * ctx.eta - self.w_d * ctx.d
                + self.w_alpha * ctx.alpha - self.w_risk * ctx.risk)

    def decide(self, ctx: DecisionContext) -> Decision:
        if ctx.tier == "REJECTED":
            return "reject"  # Safety уже отсеяла — до Policy не доходит вообще

        if self.mode == "scalar":
            score = self.scalar_score(ctx)
            if score >= self.scalar_threshold:
                return "auto_accept" if ctx.tier == "AUTO_ACCEPT" else "human_review"
            return "reject" if ctx.eta < 0 else "human_review"

        # --- pareto-режим: ни одно измерение не сводится в одно число ---
        goal_hurts = ctx.eta < self.eta_min
        if goal_hurts:
            # Даже безопасное и корректное правило, вредящее цели, не
            # должно проходить автоматически — та самая дыра, которую
            # tier-only psi_step не закрывал.
            return "reject" if ctx.tier != "NEEDS_REVIEW" else "human_review"

        if ctx.tier == "AUTO_ACCEPT" and ctx.risk <= self.risk_max_for_auto:
            return "auto_accept"

        return "human_review"


if __name__ == "__main__":
    from ..core.minilisp import standard_env, leval
    from ..rules.generator import propose_candidates, classify_candidates
    from ..metrics.distance import snapshot, compute_distance
    from ..control.goals import Goal, delta_goal, efficiency
    from ..control.autonomy import comprehension_capacity

    env = standard_env()

    def evaluator(term):
        return leval(term, env)

    # Цель, ПРОТИВОРЕЧАЩАЯ тому, что делают AUTO_ACCEPT-правила: чем МЕНЬШЕ
    # правил в системе, тем лучше (например, ценим компактность/поддерживаемость
    # набора правил самого по себе — прямое продолжение темы когнитивной
    # нагрузки на оператора из самого начала проекта).
    goal_minimize_rule_count = Goal(
        name="MinimizeRuleCount",
        evaluator=lambda rules: -len(rules),
    )

    candidates = propose_candidates(n=20, seed=42)
    buckets = classify_candidates(candidates, evaluator)
    policy = Policy(mode="pareto")

    print("=== Policy проверяет КАЖДОГО AUTO_ACCEPT-кандидата против цели MinimizeRuleCount ===")
    print("(эта цель намеренно противоречит любому добавлению правил — проверяем,")
    print(" действительно ли Policy способна отклонить то, что tier помечал как безопасное)\n")

    for rule in buckets["AUTO_ACCEPT"][:3]:  # достаточно нескольких для демонстрации
        before_rules = []
        after_rules = [rule]

        before = snapshot(env)
        env["__rules__"].append(rule)
        after = snapshot(env)
        env["__rules__"].pop()
        raw_d, _, _ = compute_distance(before, after)

        dg = delta_goal(goal_minimize_rule_count, before_rules, after_rules)
        eta = efficiency(dg, raw_d)

        ctx = DecisionContext(name=rule.name, tier="AUTO_ACCEPT", d=raw_d, eta=eta,
                               alpha=comprehension_capacity(0.0))
        decision = policy.decide(ctx)

        print(f"  {rule.name:20s} d={raw_d:.2f}  η={eta:+.3f}  risk={ctx.risk:.2f}  "
              f"tier=AUTO_ACCEPT  ->  Policy: {decision.upper()}")

    print("\nВывод: tier=AUTO_ACCEPT (Safety+Correctness) сам по себе давал бы")
    print("автокоммит для всех трёх. Policy, консультируясь с Goal, отклоняет их —")
    print("ровно то поведение, ради которого Policy и вводилась.")
