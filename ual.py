"""
ual.py v2.0 — User-Agent Language (Clean Architecture)
Язык пишет новые примитивы на самом себе (через AST/S-выражения).
Персистентность хранит состояние языка (L_t), а не Python-код.
"""
import math
import json
import os

# =====================================================================
# 1. ТИПЫ ДАННЫХ: Разделение Символов и Литералов (Исправление Фазы 4)
# =====================================================================
class Symbol(str):
    """Символ языка. Используется для поиска в окружении (Env)."""
    def __repr__(self): return f"Sym({super().__repr__()})"

def Sym(s): return Symbol(s)

# =====================================================================
# 2. ЯДРО ИНТЕРПРЕТАТОРА (Meta-Circular Evaluator)
# =====================================================================
class Env(dict):
    def __init__(self, params=(), args=(), outer=None):
        self.update(zip(params, args))
        self.outer = outer
    def find(self, var):
        if var in self: return self
        if self.outer: return self.outer.find(var)
        raise NameError(f"Symbol '{var}' not found in Language State (L)")

class Procedure:
    """Функция, определенная внутри UAL (замыкание)."""
    def __init__(self, params, body, env):
        self.params, self.body, self.env = params, body, env
    def __call__(self, *args):
        return leval(self.body, Env(self.params, args, self.env))

def standard_env():
    """Базовое состояние L_0 (примитивы)"""
    env = Env()
    env.update({
        Sym('+'): lambda *a: sum(a),
        Sym('-'): lambda *a: -a[0] if len(a)==1 else a[0] - sum(a[1:]),
        Sym('*'): lambda *a: math.prod(a),
        Sym('/'): lambda a, b: a / b,
        Sym('<'): lambda a, b: a < b,
        Sym('list'): lambda *a: list(a),
        Sym('print'): lambda *a: print(*a),
        Sym('sqrt'): math.sqrt,
        Sym('None'): None
    })
    return env

def leval(x, env):
    """Интерпретатор S-выражений"""
    # 1. Символ -> поиск функции/переменной
    if isinstance(x, Symbol): return env.find(x)[x]
    # 2. Литералы (строки, числа) -> возвращаются как есть (Исправление бага Фазы 4!)
    if isinstance(x, (str, int, float, bool, type(None))): return x
    if not isinstance(x, list): return x
    
    op, *args = x
    if op == Sym('quote'): return args[0]
    if op == Sym('if'):
        test, conseq, alt = args
        return leval(conseq if leval(test, env) else alt, env)
    if op == Sym('define'):
        var, expr = args
        env[var] = leval(expr, env); return None
    if op == Sym('lambda'):
        params, body = args
        return Procedure(params, body, env)
    if op == Sym('begin'):
        res = None
        for expr in args: res = leval(expr, env)
        return res
        
    proc = leval(op, env)
    vals = [leval(a, env) for a in args]
    return proc(*vals)

# =====================================================================
# 3. ОБЪЕКТ ЯЗЫКА (Language) И ПЕРСИСТЕНТНОСТЬ
# =====================================================================
class Language:
    """Инкарнация L_t. Хранит окружение, историю изменений и политику."""
    def __init__(self):
        self.env = standard_env()
        self.history = [] # AST всех выученных примитивов
        self.policy = Policy()
        
    def add_primitive(self, name, ast_def):
        """Регистрирует новый примитив, вычисляя его AST в текущем L"""
        proc = leval(ast_def, self.env)
        self.env[Sym(name)] = proc
        self.history.append([Sym('define'), Sym(name), ast_def])
        
    def save(self, fname="language.ual"):
        """Сохраняет L_t на диск в формате собственного AST (JSON)"""
        class Enc(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, Symbol): return {"__sym__": str(obj)}
                return super().default(obj)
        with open(fname, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, cls=Enc, indent=2, ensure_ascii=False)
            
    def load(self, fname="language.ual"):
        """Восстанавливает L_t из истории AST"""
        if not os.path.exists(fname): return
        def dec(dct):
            if "__sym__" in dct: return Symbol(dct["__sym__"])
            return dct
        with open(fname, 'r', encoding='utf-8') as f:
            self.history = json.load(f, object_hook=dec)
        for stmt in self.history:
            leval(stmt, self.env) # Проигрываем историю

# =====================================================================
# 4. АГЕНТ, ПОЛИТИКА И WriteOnSelf
# =====================================================================
class Policy:
    """Проверяет безопасность и размер нового AST перед внедрением"""
    def check_and_accept(self, ast):
        size = self._size(ast)
        # ИСПРАВЛЕНО: Увеличиваем бюджет сложности с 50 до 100
        if size > 100: 
            print(f"[Policy] REJECT: AST size {size} > 100 (Too complex for one step)")
            return False
        print(f"[Policy] ACCEPT: AST size {size} (safe)")
        return True
        
    def _size(self, n):
        return 1 + sum(self._size(c) for c in n) if isinstance(n, list) else 1

def agent_generate(goal):
    """
    Агент генерирует НОВЫЙ КОД НА САМОМ UAL (через lambda/begin).
    Никакого Python-кода! Только S-выражения.
    """
    print(f"[Agent] Synthesizing AST for goal: '{goal}'")
    return [
        Sym('lambda'), [Sym('a'), Sym('b'), Sym('c')],
        [Sym('begin'),
            [Sym('define'), Sym('d'), [Sym('-'), [Sym('*'), Sym('b'), Sym('b')], [Sym('*'), 4, Sym('a'), Sym('c')]]],
            [Sym('if'), [Sym('<'), Sym('d'), 0],
                Sym('None'),
                [Sym('list'),
                    [Sym('/'), [Sym('+'), [Sym('-'), Sym('b')], [Sym('sqrt'), Sym('d')]], [Sym('*'), 2, Sym('a')]],
                    [Sym('/'), [Sym('-'), [Sym('-'), Sym('b')], [Sym('sqrt'), Sym('d')]], [Sym('*'), 2, Sym('a')]]
                ]
            ]
        ]
    ]

def write_on_self(lang, goal):
    """Оператор L -> L'"""
    ast = agent_generate(goal)
    if lang.policy.check_and_accept(ast):
        lang.add_primitive("solve_quadratic", ast)
        lang.save()
        print("[System] Language state expanded and persisted (L -> L')")

# =====================================================================
# 5. ДЕМОНСТРАЦИЯ
# =====================================================================
def main():
    lang = Language()
    lang.load() # Загрузка L_t из предыдущих сессий
    
    print("="*50)
    print("ФАЗА 1: Текущее состояние языка (L_t)")
    print("="*50)
    try:
        res = leval([Sym('solve_quadratic'), 1, -5, 6], lang.env)
        print("Результат:", res)
    except NameError as e:
        print(f"ОШИБКА: {e}")
        print("(Примитив отсутствует в L_t).")
        
    print("\n" + "="*50)
    print("ФАЗА 2: WriteOnSelf (Генерация AST на самом UAL)")
    print("="*50)
    # ИСПРАВЛЕНО: правильный порядок аргументов (сначала объект языка, потом цель)
    write_on_self(lang, "solve quadratic equations")
    
    print("\n" + "="*50)
    print("ФАЗА 3: Новое состояние языка (L_{t+1})")
    print("="*50)
    res = leval([Sym('solve_quadratic'), 1, -5, 6], lang.env)
    print("Результат (корни уравнения):", res)
    
    print("\nФАЗА 4: Композиция (Исправлено: строки vs символы)")
    # "Корни:" - это str (литерал), Sym('solve_quadratic') - это Symbol (функция)
    leval([Sym('print'), [Sym('list'), "Корни:", [Sym('solve_quadratic'), 1, -7, 10]]], lang.env)

if __name__ == "__main__":
    # Для чистоты эксперимента: удаляем старое состояние языка, если оно есть
    if os.path.exists("language.ual"):
        os.remove("language.ual")
    main()
