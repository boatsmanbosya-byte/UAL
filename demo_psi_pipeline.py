"""
Полный конвейер на РЕАЛЬНЫХ данных: генератор кандидатов -> коммит в живую
систему -> измеренный distance.py d для каждого правила -> управляющий
оператор Ψ (троттлинг + эпистемическая скидка доверия κ), а не синтетические
3.5, захардкоженные в demo для psi.py.
"""
from ual.core.minilisp import standard_env, leval
from ual.rules.generator import propose_candidates, classify_candidates
from ual.metrics.distance import snapshot, compute_distance
from ual.control.psi import run_psi, PsiState

env = standard_env()


def evaluator(term):
    return leval(term, env)


candidates = propose_candidates(n=20, seed=42)
buckets = classify_candidates(candidates, evaluator)
print(f"AUTO_ACCEPT кандидатов: {len(buckets['AUTO_ACCEPT'])}")

# Считаем РЕАЛЬНЫЙ d для каждого AUTO_ACCEPT кандидата (как в demo_pipeline.py),
# но пока НЕ коммитим необратимо — сначала решает Ψ, в каком темпе это делать
items = []
for rule in buckets["AUTO_ACCEPT"]:
    before = snapshot(env)
    env["__rules__"].append(rule)
    after = snapshot(env)
    d_total, _, _ = compute_distance(before, after)
    items.append((rule.name, d_total, "AUTO_ACCEPT"))
# для честности отката к "чистому" env перед сравнением стратегий:
env["__rules__"].clear()

items_manual_tariff = [(name, d, "MANUAL") for name, d, _ in items]  # тот же d, но БЕЗ скидки доверия

print("\n=== Стратегия А (троттлинг, БЕЗ скидки доверия κ) ===")
state_a = run_psi(items_manual_tariff, PsiState())
for e in state_a.log:
    print(" ", e)
print(f"Шагов потребовалось: {len(state_a.log)}")

print("\n=== Стратегия А+Б (троттлинг + скидка доверия κ=0.3 для AUTO_ACCEPT) ===")
state_b = run_psi(items, PsiState())
for e in state_b.log:
    print(" ", e)
print(f"Шагов потребовалось: {len(state_b.log)}")
