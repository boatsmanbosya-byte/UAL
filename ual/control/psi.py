"""
Управляющий оператор Ψ: две стратегии для проблемы "верифицированного батча",
найденной эмпирически (7 правил по d=3.5, суммарно d=24.5 — при C(K_t)=10-15
это нарушает неравенство синергии d_t <= C(K_t), несмотря на то, что каждое
правило по отдельности математически безупречно).

Стратегия А (троттлинг): Ψ дробит очередь кандидатов на под-батчи так, чтобы
каждый под-батч укладывался в ТЕКУЩУЮ пропускную способность C(K_t). После
каждого закоммиченного под-батча K_t растёт, и следующий под-батч может
быть крупнее.

Стратегия Б (скидка доверия κ): правило, прошедшее ОБА фильтра generator.py
(is_size_safe доказывает терминацию, semantic_check эмпирически проверяет
корректность), требует от оператора меньше усилий на ревью, чем "сырой"
макрос без этих гарантий — поэтому его ВКЛАД в V(t) масштабируется κ<1,
хотя "сырой" структурный d (см. distance.py) при этом не меняется и
продолжает честно отражать геометрический объём изменения.

ЧЕСТНО: κ и его границы (0.3/0.7/1.0) — дизайнерские константы, кодирующие
гипотезу "формально верифицированное дешевле для человека", а не
калиброванный на реальных операторах факт.
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Dict
from .autonomy import comprehension_capacity, update_K, update_alpha

KAPPA: Dict[str, float] = {
    "AUTO_ACCEPT": 0.3,    # оба фильтра пройдены: терминация доказана + корректность проверена
    "NEEDS_REVIEW": 0.7,   # только корректность проверена, терминация не гарантирована автоматически
    "MANUAL": 1.0,         # без формальных гарантий вообще — полный вес, скидки нет
}


def effective_distance(raw_d: float, tier: str) -> float:
    return raw_d * KAPPA.get(tier, 1.0)


@dataclass
class PsiState:
    K: float = 0.0
    alpha: float = 0.0
    log: List[dict] = field(default_factory=list)


def run_psi(items: List[Tuple[str, float, str]], state: PsiState) -> PsiState:
    """items: список (имя, raw_d, tier). Жадно формирует под-батчи так, чтобы
    сумма ЭФФЕКТИВНОГО (со скидкой κ) d батча не превышала текущий C(K_t);
    коммитит батч, обновляет K_t/alpha_t, переходит к следующему батчу уже
    с бОльшей пропускной способностью (эффект накопленного понимания)."""
    queue = list(items)
    step = 0
    while queue:
        budget = comprehension_capacity(state.K)
        batch, raw_total, eff_total = [], 0.0, 0.0
        while queue:
            name, raw_d, tier = queue[0]
            e_d = effective_distance(raw_d, tier)
            if eff_total + e_d > budget and batch:
                break  # следующий кандидат уже не влезает в бюджет ЭТОГО шага
            batch.append(queue.pop(0))
            raw_total += raw_d
            eff_total += e_d
        V = budget - eff_total
        state.K = update_K(state.K, eff_total)
        state.alpha = update_alpha(state.alpha, V)
        step += 1
        state.log.append({
            "step": step,
            "batch": [n for n, _, _ in batch],
            "raw_d_total": round(raw_total, 2),
            "eff_d_total": round(eff_total, 2),
            "budget_C(K)": round(budget, 2),
            "V": round(V, 2),
            "K_after": round(state.K, 2),
            "alpha_after": round(state.alpha, 3),
        })
    return state


def psi_step(rule, raw_d: float, tier: str, env, evaluator, input_fn=input):
    """Условный оператор Ψ:
        risk допустим (tier == AUTO_ACCEPT)  -> Ψ_agent: коммит без участия человека.
        risk НЕ допустим (tier == NEEDS_REVIEW) -> Ψ_human: делегируем Action_t.
        tier == REJECTED -> никогда не доходит до Ψ вообще (уже отсеяно до этого шага).
    Возвращает закоммиченное правило (исходное/изменённое) либо None, если не закоммичено."""
    from .human_review import psi_human

    if tier == "AUTO_ACCEPT":
        env["__rules__"].append(rule)
        return rule
    elif tier == "NEEDS_REVIEW":
        result = psi_human(rule, raw_d, evaluator, input_fn)
        if result is not None:
            env["__rules__"].append(result)
        return result
    else:  # REJECTED
        return None



    # Синтетическая проверка на 7 кандидатах с raw_d=3.5 (как реально
    # измерено в demo_pipeline.py) — сравнение "без κ" (MANUAL, скидки нет)
    # против "с κ" (AUTO_ACCEPT, полная скидка доверия).
    items = [(f"rule_{i}", 3.5, "AUTO_ACCEPT") for i in range(7)]
    items_manual = [(f"rule_{i}", 3.5, "MANUAL") for i in range(7)]

    print("=== БЕЗ скидки доверия (κ=1.0, тариф MANUAL) — только троттлинг ===")
    state_a = run_psi(items_manual, PsiState())
    for entry in state_a.log:
        print(" ", entry)

    print("\n=== С скидкой доверия κ=0.3 (тариф AUTO_ACCEPT) — троттлинг + κ ===")
    state_b = run_psi(items, PsiState())
    for entry in state_b.log:
        print(" ", entry)

    print(f"\nИтого шагов без κ: {len(state_a.log)}   с κ: {len(state_b.log)}")
