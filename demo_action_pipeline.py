"""
Демонстрация условного оператора Ψ = Ψ_agent | Ψ_human на реальных данных.

AUTO_ACCEPT  -> Ψ_agent: коммит без участия человека (риск допустим).
NEEDS_REVIEW -> Ψ_human: реальный Action_t человека решает судьбу правила.

Здесь input_fn подменён заранее заданной очередью ответов — чтобы
прогнать все четыре действия (accept/reject/request_explain/modify) без
ожидания живого человека В ЭТОЙ демонстрации. На вашей машине при запуске
БЕЗ подмены (input_fn=input по умолчанию) это будет настоящая пауза с
реальным вопросом в терминале.
"""
from ual.core.minilisp import standard_env, leval
from ual.rules.generator import propose_candidates, classify_candidates
from ual.metrics.distance import snapshot, compute_distance
from ual.control.psi import psi_step

env = standard_env()


def evaluator(term):
    return leval(term, env)


# Очередь заранее заданных ответов — в порядке, в котором будут заданы вопросы.
# 'bla' в начале намеренно проверяет ветку "неизвестное действие" (устойчивость к опечатке).
scripted_answers = iter([
    "bla", "request_explain", "accept",     # кандидат 1: опечатка -> объяснение -> принять
    "reject",                                # кандидат 2: отклонить
    "accept",                                # кандидат 3: принять сразу
    "modify", "(* ?y ?x)", "accept",         # кандидат 4: изменить (та же форма) -> подтвердить
    "modify", "(* ?x ?x)",                   # кандидат 5: изменить НА НЕВЕРНОЕ -> автоматически отклонено
])


def scripted_input(prompt: str) -> str:
    answer = next(scripted_answers)
    print(f"{prompt}{answer}   [заранее заданный ответ для демонстрации]")
    return answer


candidates = propose_candidates(n=40, seed=42)
buckets = classify_candidates(candidates, evaluator)
print(f"AUTO_ACCEPT={len(buckets['AUTO_ACCEPT'])}  "
      f"NEEDS_REVIEW={len(buckets['NEEDS_REVIEW'])}  "
      f"REJECTED={len(buckets['REJECTED'])}")

print("\n=== Ψ_agent: автоматический коммит AUTO_ACCEPT ===")
for rule in buckets["AUTO_ACCEPT"]:
    before = snapshot(env)
    committed = psi_step(rule, 0.0, "AUTO_ACCEPT", env, evaluator)
    after = snapshot(env)
    d_total, _, _ = compute_distance(before, after)
    print(f"  +{rule.name:20s} закоммичено автоматически, d={d_total:.2f}")

print("\n=== Ψ_human: реальный Action_t для каждого NEEDS_REVIEW ===")
results = []
for rule in buckets["NEEDS_REVIEW"]:
    before = snapshot(env)
    env["__rules__"].append(rule)              # временно — чтобы измерить НАСТОЯЩИЙ d
    hypothetical_after = snapshot(env)
    env["__rules__"].pop()                      # откатываем: решение ещё не принято
    raw_d, _, _ = compute_distance(before, hypothetical_after)

    committed = psi_step(rule, raw_d, "NEEDS_REVIEW", env, evaluator, input_fn=scripted_input)
    after = snapshot(env)
    d_total, _, _ = compute_distance(before, after)
    status = f"ЗАКОММИЧЕНО (d={d_total:.2f})" if committed else "НЕ закоммичено"
    results.append((rule.name, status))

print("\n=== ИТОГ по всем NEEDS_REVIEW-кандидатам ===")
for name, status in results:
    print(f"  {name:20s} -> {status}")

print(f"\nВсего правил в живой rules_table после всего процесса: {len(env['__rules__'])}")
