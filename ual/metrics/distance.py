"""
Метрика сдвига языка d(L_t, L_{t+1}) — считается по РЕАЛЬНОМУ состоянию
работающей системы (Env + rules_table), а не по синтетическим
LanguageState-объектам из прошлых тестовых скриптов.

Состояние языка L_t раскладывается на две части:
  - definitions: пользовательские (define name ...) в окружении -> тело как S-выражение
  - rules:       правила переписывания из rules_table -> (pattern, replacement)

Веса и принцип расчёта — тот же откалиброванный d_v2 (см. дневник, раздел 10):
  - добавление/удаление сущности стоит BASE + SIZE_WEIGHT * ast_size(...)
    (пропорционально её реальному размеру, а не плоской константой)
  - изменение существующей сущности с тем же именем — рекурсивное AST-расстояние,
    с отдельным весом для "скачка абстракции" (число <-> переменная/имя)

ВАЖНО: атомы здесь — настоящие Python int/str (из реального парсера mini-Lisp),
а не строки "0"/"1" как в старых синтетических тестах — сравнение атомов
переписано под реальные типы, а не портировано вслепую.
"""
from dataclasses import dataclass
from typing import Dict, Tuple, Any, Union
from ..rules.trs import SExpr, ast_size
from ..core.minilisp import Env, Procedure

# Встроенные имена окружения — фиксированный алфавит ядра (Σ_t), НЕ считаются
# "определениями пользователя", которые растут самоскриптованием
BUILTIN_NAMES = {
    "+", "-", "*", "/", ">", "<", ">=", "<=", "=",
    "car", "cdr", "cons", "list", "null?", "eq?", "not", "print",
    "eval", "define-rule", "rewrite", "__rules__",
}

MACRO_ADD_BASE = 1.0
MACRO_ADD_SIZE_WEIGHT = 0.5
MACRO_REMOVE_BASE = 1.0
MACRO_REMOVE_SIZE_WEIGHT = 0.3
ABSTRACTION_JUMP_WEIGHT = 2.0

Entity = Union[SExpr, Tuple[SExpr, SExpr]]  # определение (S-выражение) ИЛИ правило (pattern, replacement)


def ast_distance(node1: SExpr, node2: SExpr) -> float:
    """Рекурсивное расстояние между двумя S-выражениями. Работает с реальными
    типами атомов (int/float/str), а не только со строками."""
    if node1 == node2:
        return 0.0
    n1_is_list, n2_is_list = isinstance(node1, list), isinstance(node2, list)
    if n1_is_list and n2_is_list:
        max_len = max(len(node1), len(node2))
        dist = 0.0
        for i in range(max_len):
            if i >= len(node1) or i >= len(node2):
                dist += 2.0  # добавленная/удалённая ветвь
            else:
                dist += ast_distance(node1[i], node2[i])
        return dist
    if n1_is_list != n2_is_list:
        return 5.0  # смена топологии: атом <-> поддерево
    # оба — атомы: число (int/float) или строка (символ/имя)
    n1_num, n2_num = isinstance(node1, (int, float)), isinstance(node2, (int, float))
    if n1_num and n2_num:
        return 0.1  # два разных числа — мелкая правка константы
    if n1_num != n2_num:
        return ABSTRACTION_JUMP_WEIGHT  # число <-> символ — скачок абстракции
    return 1.0  # два разных символа — переименование


def _entity_size(entity: Entity) -> int:
    if isinstance(entity, tuple):
        pattern, repl = entity
        return ast_size(pattern) + ast_size(repl)
    return ast_size(entity)


def _entity_distance(e1: Entity, e2: Entity) -> float:
    if isinstance(e1, tuple) and isinstance(e2, tuple):
        return ast_distance(e1[0], e2[0]) + ast_distance(e1[1], e2[1])
    return ast_distance(e1, e2)


def _collection_distance(before: Dict[str, Entity], after: Dict[str, Entity]) -> float:
    before_names, after_names = set(before.keys()), set(after.keys())
    added, removed, common = after_names - before_names, before_names - after_names, before_names & after_names
    d = 0.0
    for name in added:
        d += MACRO_ADD_BASE + MACRO_ADD_SIZE_WEIGHT * _entity_size(after[name])
    for name in removed:
        d += MACRO_REMOVE_BASE + MACRO_REMOVE_SIZE_WEIGHT * _entity_size(before[name])
    for name in common:
        d += _entity_distance(before[name], after[name]) * 0.5
    return d


@dataclass
class LanguageSnapshot:
    definitions: Dict[str, SExpr]
    rules: Dict[str, Tuple[SExpr, SExpr]]


def _definition_body(value: Any) -> SExpr:
    if isinstance(value, Procedure):
        return ["lambda", list(value.params), value.body]
    return value  # атомарное значение (например, из (define x 5)) — само по себе валидный лист


def snapshot(env: Env) -> LanguageSnapshot:
    """Снимает текущее состояние ЖИВОГО окружения: пользовательские определения + правила."""
    definitions = {name: _definition_body(value) for name, value in env.items() if name not in BUILTIN_NAMES}
    rules_table = env.get("__rules__", [])
    rules = {r.name: (r.pattern, r.replacement) for r in rules_table}
    return LanguageSnapshot(definitions=definitions, rules=rules)


def compute_distance(before: LanguageSnapshot, after: LanguageSnapshot) -> Tuple[float, float, float]:
    """Возвращает (d_total, d_defs, d_rules)."""
    d_defs = _collection_distance(before.definitions, after.definitions)
    d_rules = _collection_distance(before.rules, after.rules)
    return d_defs + d_rules, d_defs, d_rules


if __name__ == "__main__":
    from ..core.minilisp import standard_env, run

    env = standard_env()

    print("=== ТЕСТ A: пустое -> пустое (d должно быть 0) ===")
    snap0 = snapshot(env)
    snap0b = snapshot(env)
    print("d =", compute_distance(snap0, snap0b))

    print("\n=== ТЕСТ B: маленькое определение vs большое определение ===")
    snap_before = snapshot(env)
    run("(define small (lambda (x) (+ x 1)))", env)
    snap_after_small = snapshot(env)
    d_small, d_defs_s, d_rules_s = compute_distance(snap_before, snap_after_small)
    print(f"добавили 'small' (+x 1):        d_total={d_small:.2f}  d_defs={d_defs_s:.2f}")

    run("(define big (lambda (x) (if (> x 0) (* x (* x x)) (- 0 (* x (* x x))))))", env)
    snap_after_big = snapshot(env)
    d_big, d_defs_b, d_rules_b = compute_distance(snap_after_small, snap_after_big)
    print(f"добавили 'big' (кубический if): d_total={d_big:.2f}  d_defs={d_defs_b:.2f}  (ожидаем d_big > d_small)")

    print("\n=== ТЕСТ C: переименование vs скачок абстракции внутри существующего определения ===")
    env2 = standard_env()
    run("(define f (lambda (x) (+ x 1)))", env2)
    snap_c0 = snapshot(env2)
    # эмулируем "переименование" ветки константы на другую константу (мелкая правка)
    env2["f"].body = ["+", "x", 5]
    snap_c1 = snapshot(env2)
    d_const, _, _ = compute_distance(snap_c0, snap_c1)
    # эмулируем "скачок абстракции": константа 1 заменяется на свободную переменную y
    env2["f"].body = ["+", "x", "y"]
    snap_c2 = snapshot(env2)
    d_jump, _, _ = compute_distance(snap_c1, snap_c2)
    print(f"смена константы 5->... :  d={d_const:.2f}")
    print(f"константа -> переменная (скачок абстракции): d={d_jump:.2f}  (ожидаем d_jump > d_const)")
