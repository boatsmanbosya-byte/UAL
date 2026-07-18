# UAL — рабочий прототип

```
ual/
├── core/minilisp.py       # гомоиконичное eval/apply-ядро (mini-Lisp)
├── rules/trs.py           # движок переписывания правил (термы, терминация, конфлюэнтность)
├── rules/generator.py     # генератор кандидатов (is_size_safe + semantic_check), включая шаблон commute
├── metrics/distance.py    # d(L,L') по реальным снимкам живой системы
└── control/
    ├── autonomy.py        # sigma, C(K), update_K, update_alpha
    ├── psi.py              # Ψ: троттлинг + κ-скидка доверия + psi_step (условный Ψ_agent|Ψ_human)
    └── human_review.py    # Ψ_human: реализация Action_t (accept/reject/request_explain/modify)
demo_pipeline.py            # генератор -> коммит -> d(L,L')
demo_psi_pipeline.py        # генератор -> d -> Ψ (троттлинг + κ)
demo_action_pipeline.py     # генератор -> Ψ_agent/Ψ_human -> реальный Action_t
```

## Запуск

```bash
python3 -m ual.rules.trs
python3 -m ual.core.minilisp
python3 -m ual.rules.generator
python3 -m ual.metrics.distance
python3 -m ual.control.psi
python3 demo_pipeline.py
python3 demo_psi_pipeline.py
python3 demo_action_pipeline.py     # здесь input_fn подменён — см. файл, чтобы увидеть живой input()
```

Полная история, найденные баги и обоснование каждого решения — в ual_journal.md.

## Что ещё НЕ реализовано
- κ и константы C(K) — дизайнерские, не калиброванные на реальных людях.
- Формальное доказательство конфлюэнтности (critical pairs / Knuth-Bendix).
- Расширение языка (let, полноценная рекурсия, мутация списков).
- git-репозиторий ещё не инициализирован.

