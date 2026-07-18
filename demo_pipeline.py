"""
Демонстрация полного конвейера: генератор кандидатов правил -> реальный
коммит в живую rules_table интерпретатора -> расчёт d(L,L') для КАЖДОГО
принятого правила (а не абстрактно, а по факту произошедшего изменения).

Это то, чего не хватало раньше: d(L,L') существовал только как отдельные
тестовые скрипты, оторванные от generator.py. Здесь это один связанный процесс.
"""
from ual.core.minilisp import standard_env, leval
from ual.rules.generator import propose_candidates, classify_candidates
from ual.metrics.distance import snapshot, compute_distance

env = standard_env()


def evaluator(term):
    return leval(term, env)


candidates = propose_candidates(n=20, seed=42)
buckets = classify_candidates(candidates, evaluator)

print(f"Кандидатов: {len(candidates)}  "
      f"AUTO_ACCEPT={len(buckets['AUTO_ACCEPT'])}  "
      f"NEEDS_REVIEW={len(buckets['NEEDS_REVIEW'])}  "
      f"REJECTED={len(buckets['REJECTED'])}")

print("\n=== d(L, L') ДЛЯ КАЖДОГО РЕАЛЬНО ПРИНЯТОГО ПРАВИЛА ===")
total_d = 0.0
per_rule_d = []
for rule in buckets["AUTO_ACCEPT"]:
    before = snapshot(env)
    env["__rules__"].append(rule)          # <-- реальный коммит в живую систему
    after = snapshot(env)
    d_total, d_defs, d_rules = compute_distance(before, after)
    total_d += d_total
    per_rule_d.append((rule.name, d_total))
    print(f"  +{rule.name:32s} d={d_total:.2f}")

print(f"\nСуммарный сдвиг языка за весь батч AUTO_ACCEPT: {total_d:.2f}")
print(f"Средний d на одно автономно принятое правило: {total_d/len(buckets['AUTO_ACCEPT']):.2f}")
print("(REJECTED/NEEDS_REVIEW НЕ коммитятся — язык не менялся, d для них не определён)")

print("\n=== ПРОВЕРКА: язык реально работает с новыми правилами ===")
term = ["+", ["*", "x", 1], 0]
from ual.rules.trs import normalize
nf, trace, terminated = normalize(env["__rules__"], term)
print(f"rewrite({term}) = {nf}  (терминировано: {terminated})")
