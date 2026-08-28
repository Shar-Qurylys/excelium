"""Реестр именованных операций (ops.yaml). Fail-fast: кривой конфиг
не даёт сервису стартовать.

Правила подстановки в argv:
- встроенные плейсхолдеры {workdir}, {app_dir}, {python} могут стоять
  внутри элемента;
- пользовательские параметры — ТОЛЬКО отдельным элементом целиком
  ("{text}", "{files...}"): значение параметра никогда не
  конкатенируется в строку команды.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

BUILTINS = {"workdir", "app_dir", "python"}
# Команду можно задавать из интерфейса, поэтому argv[0] ограничен каталогами:
# конструктор операций иначе превратил бы админ-токен в доступ к оболочке.
ALLOWED_BIN_DIRS = ("/usr/bin", "/bin", "/usr/local/bin", "/opt")
PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)(\.\.\.)?\}")
PARAM_TYPES = {"str", "file", "file_list"}


class OpsConfigError(Exception):
    pass


@dataclass
class ParamDef:
    name: str
    type: str = "str"
    pattern: re.Pattern | None = None
    required: bool = True
    max_items: int = 50


@dataclass
class Operation:
    name: str
    argv: list[str]
    params: dict[str, ParamDef] = field(default_factory=dict)
    collect: str | None = None
    timeout_sec: int = 30
    max_output_kb: int = 64
    description: str = ""


def load_registry(path: Path) -> dict[str, Operation]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    ops_raw = raw.get("operations")
    if not isinstance(ops_raw, dict):
        raise OpsConfigError(f"{path}: нет секции operations")
    registry = {}
    for name, spec in ops_raw.items():
        registry[name] = _parse_operation(name, spec)
    return registry


def _parse_operation(name: str, spec: dict) -> Operation:
    def fail(msg: str):
        raise OpsConfigError(f"операция {name!r}: {msg}")

    if not re.fullmatch(r"[a-z0-9_]{1,64}", name):
        fail("имя — только [a-z0-9_]")
    known = {"description", "argv", "params", "collect", "timeout_sec", "max_output_kb"}
    if unknown := set(spec) - known:
        fail(f"неизвестные ключи {sorted(unknown)}")
    argv = spec.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        fail("argv — непустой список строк")
    head = argv[0]
    if not (head.startswith("{python}") or head.startswith("{app_dir}")
            or any(head.startswith(d + "/") for d in ALLOWED_BIN_DIRS)):
        fail(f"argv[0] должен быть {{python}}, {{app_dir}}/… или лежать в "
             f"{', '.join(ALLOWED_BIN_DIRS)}; получено {head!r}")

    params: dict[str, ParamDef] = {}
    for pname, pspec in (spec.get("params") or {}).items():
        pspec = pspec or {}
        if bad := set(pspec) - {"pattern", "required", "type", "max_items"}:
            fail(f"параметр {pname!r}: неизвестные ключи {sorted(bad)}")
        ptype = pspec.get("type", "str")
        if ptype not in PARAM_TYPES:
            fail(f"параметр {pname!r}: тип {ptype!r} не из {sorted(PARAM_TYPES)}")
        pattern = None
        if ptype == "str":
            if "pattern" not in pspec:
                fail(f"параметр {pname!r}: строковому параметру обязателен pattern")
            try:
                pattern = re.compile(pspec["pattern"])
            except re.error as exc:
                fail(f"параметр {pname!r}: битый regex ({exc})")
        params[pname] = ParamDef(
            name=pname, type=ptype, pattern=pattern,
            required=bool(pspec.get("required", True)),
            max_items=int(pspec.get("max_items", 50)),
        )

    used = set()
    for element in argv:
        found = PLACEHOLDER_RE.findall(element)
        for pname, ellipsis in found:
            if pname in BUILTINS:
                if ellipsis:
                    fail(f"{{{pname}...}} — встроенный плейсхолдер не разворачивается")
                continue
            if pname not in params:
                fail(f"в argv есть {{{pname}}}, но параметр не объявлен")
            expected = f"{{{pname}...}}" if params[pname].type == "file_list" else f"{{{pname}}}"
            if element != expected:
                fail(f"параметр {{{pname}}} должен стоять отдельным элементом argv")
            used.add(pname)
    if missing := set(params) - used:
        fail(f"объявлены, но не используются в argv: {sorted(missing)}")

    return Operation(
        name=name, argv=list(argv), params=params,
        collect=spec.get("collect"),
        timeout_sec=int(spec.get("timeout_sec", 30)),
        max_output_kb=int(spec.get("max_output_kb", 64)),
        description=str(spec.get("description", "")),
    )


def dump_registry(registry: dict[str, Operation]) -> str:
    """Реестр -> текст ops.yaml (шапка-пояснение сохраняется)."""
    ops: dict = {}
    for name, op in sorted(registry.items()):
        spec: dict = {}
        if op.description:
            spec["description"] = op.description
        spec["argv"] = list(op.argv)
        if op.params:
            spec["params"] = {}
            for pname, p in op.params.items():
                entry: dict = {}
                if p.type != "str":
                    entry["type"] = p.type
                if p.pattern is not None:
                    entry["pattern"] = p.pattern.pattern
                if not p.required:
                    entry["required"] = False
                if p.type == "file_list" and p.max_items != 50:
                    entry["max_items"] = p.max_items
                spec["params"][pname] = entry
        if op.collect:
            spec["collect"] = op.collect
        if op.timeout_sec != 30:
            spec["timeout_sec"] = op.timeout_sec
        if op.max_output_kb != 64:
            spec["max_output_kb"] = op.max_output_kb
        ops[name] = spec
    return HEADER + yaml.safe_dump({"operations": ops}, allow_unicode=True,
                                   sort_keys=False, width=100)


def parse_operation(name: str, spec: dict) -> Operation:
    """Проверка одной операции (для конструктора в интерфейсе)."""
    return _parse_operation(name, spec)


HEADER = """# Реестр операций шлюза — замена платного действия «Запуск».
#
# Каждая операция — фиксированный argv-шаблон. Shell не используется
# никогда; значения параметров валидируются regex-ом и попадают в
# команду только отдельным аргументом. Файловые параметры принимают
# токен из /files и копируются во временную папку под человеческим
# именем; файлы, попавшие под collect, возвращаются ссылками в ответе.
#
# Встроенные плейсхолдеры: {workdir} — временная папка запуска,
# {app_dir} — корень сервиса, {python} — python из venv сервиса.
#
# Файл правится и руками, и через конструктор в /ui («Операции»).

"""
