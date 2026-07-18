"""
Ψ_human: реализация Action_t ∈ {accept, reject, request_explain, modify}
для кандидатов из корзины NEEDS_REVIEW — правил, чья корректность
подтверждена semantic_check, но терминация НЕ гарантирована автоматически
(is_size_safe=False).

Это тот самый недостающий элемент исходной формулы:
    (L_{t+1}, A_{t+1}) = Ψ(L_t, A_t, Action_t)

Теперь Ψ — условный оператор:
    - Ψ_agent  (AUTO_ACCEPT): риск допустим -> коммит без участия человека.
    - Ψ_human  (NEEDS_REVIEW): риск НЕ признан допустимым автоматически ->
      решение делегируется реальному Action_t человека через терминал.

input_fn заменяем параметром — по умолчанию настоящий input() (пауза и
реальный вопрос в терминале при запуске на машине оператора), но в тестах
подменяется списком заранее заданных ответов, чтобы проверить всю логику
без ожидания живого человека.
"""
from typing import Callable, Optional
from ..rules.trs import Rule, ast_size
from ..rules.generator import is_size_safe, semantic_check


def _print_candidate(rule: Rule, raw_d: float) -> None:
    print(f"\n--- Кандидат требует решения человека (NEEDS_REVIEW) ---")
    print(f"  Правило:      {rule}")
    print(f"  d(L,L'):      {raw_d:.2f}")
    print(f"  Почему здесь: корректность подтверждена (semantic_check прошёл),")
    print(f"                но терминация НЕ гарантирована автоматически")
    print(f"                (is_size_safe=False: правая часть не короче левой)")


def psi_human(rule: Rule, raw_d: float, evaluator: Callable, input_fn: Callable[[str], str] = input) -> Optional[Rule]:
    """Возвращает правило для коммита (исходное или изменённое), либо None
    если человек отклонил. Реализует все четыре Action_t."""
    _print_candidate(rule, raw_d)
    while True:
        action = input_fn("Ваше решение [accept / reject / request_explain / modify]: ").strip().lower()

        if action == "accept":
            print("  -> ПРИНЯТО человеком. Коммит без автоматической гарантии терминации, на риск оператора.")
            return rule

        elif action == "reject":
            print("  -> ОТКЛОНЕНО человеком. Правило не коммитится.")
            return None

        elif action == "request_explain":
            print("  [объяснение] semantic_check: 25 случайных подстановок переменных —")
            print("               левая и правая часть правила совпадали во всех случаях.")
            print(f"               is_size_safe=False: skeleton-размер правой части "
                  f"({ast_size(rule.replacement)}) не меньше строго левой ({ast_size(rule.pattern)}) —")
            print("               нет автоматической гарантии, что многократное применение")
            print("               этого правила (в т.ч. вместе с другими) когда-нибудь остановится.")
            continue  # переспрашиваем — та самая "не забегать вперёд" из самого начала модели

        elif action == "modify":
            new_repl_text = input_fn("Введите новую правую часть в виде S-выражения (например: (+ ?y ?x)): ")
            from ..core.minilisp import read
            try:
                new_replacement = read(new_repl_text)
            except Exception as e:
                print(f"  Не удалось разобрать выражение: {e}. Попробуйте снова.")
                continue
            modified = Rule(rule.name + "_modified", rule.pattern, new_replacement)
            # ВАЖНО: модификация человека сама проходит ту же верификацию, что и
            # автоматические кандидаты — modify не обходит безопасность, а подаёт
            # новый кандидат на проверку заново.
            if not semantic_check(modified, evaluator):
                print("  -> Изменённое правило НЕ прошло проверку корректности. Отклонено.")
                return None
            if is_size_safe(modified):
                print("  -> Изменённое правило теперь доказуемо терминирует (Ψ_agent принял бы его сам).")
                return modified
            print("  -> Изменённое правило корректно, но терминация всё ещё не гарантирована.")
            confirm = input_fn("Всё равно принять? [accept/reject]: ").strip().lower()
            if confirm == "accept":
                return modified
            print("  -> ОТКЛОНЕНО.")
            return None

        else:
            print(f"  Неизвестное действие '{action}'. Допустимые: accept, reject, request_explain, modify.")
