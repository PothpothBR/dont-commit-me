from __future__ import annotations

import json

import questionary
from questionary import Style

from dont_commit_me.config import CONFIG_PATH_JSON, CONFIG_PATH_TOML

STYLE = Style(
    [
        ("qmark", "fg:#7c3aed bold"),
        ("question", "bold"),
        ("answer", "fg:#7c3aed bold"),
        ("pointer", "fg:#7c3aed bold"),
        ("highlighted", "fg:#7c3aed bold"),
        ("selected", "fg:#7c3aed"),
        ("separator", "fg:#6b7280"),
        ("instruction", "fg:#6b7280"),
    ]
)

SIMPLE_LINE_RULE_TOML = """\
[[line_rule]]
extensions = [".sql", ".py", ".xml", ".java", ".js", ".ts", ".kt", ".swift", ".c", ".cpp"]
contains = ["[dont-commit-me]", "[wip]", "[fix-me]", "[remove-me]"]

[[line_rule]]
extensions = [".java", ".js", ".ts", ".kt", ".swift", ".c", ".cpp"]
match = "(?i)\\bTODO\\b"
"""

SIMPLE_LINE_RULE_JSON: list[dict] = [
    {
        "extensions": [".sql", ".py", ".xml", ".java", ".js", ".ts", ".kt", ".swift", ".c", ".cpp"],
        "contains": ["[dont-commit-me]", "[wip]", "[fix-me]", "[remove-me]"],
    },
    {
        "extensions": [".java", ".js", ".ts", ".kt", ".swift", ".c", ".cpp"],
        "match": "(?i)\\bTODO\\b",
    },
]


def _build_toml(stop_on_catch: bool, add_simple_rule: bool) -> str:
    lines = ["[config]", f"stop_on_catch = {'true' if stop_on_catch else 'false'}", ""]
    if add_simple_rule:
        lines.append(SIMPLE_LINE_RULE_TOML)
    return "\n".join(lines)


def _build_json(stop_on_catch: bool, add_simple_rule: bool) -> str:
    return json.dumps({
        "config": {"stop_on_catch": stop_on_catch},
        "line_rule": SIMPLE_LINE_RULE_JSON if add_simple_rule else [],
    }, indent=2, ensure_ascii=False)


def run_wizard() -> None:
    existing = CONFIG_PATH_TOML if CONFIG_PATH_TOML.exists() else CONFIG_PATH_JSON if CONFIG_PATH_JSON.exists() else None

    print()
    questionary.print("  dont-commit-me", style="bold fg:#7c3aed")
    questionary.print("  ──────────────────────────────────────", style="fg:#6b7280")

    if existing:
        questionary.print(f"  Configuração existente: {existing}\n", style="fg:#6b7280")
        overwrite = questionary.confirm(
            "  Deseja apagar e reconfigurar?",
            default=False,
            style=STYLE,
        ).ask()
        if not overwrite:
            questionary.print("  Nenhuma alteração feita.\n", style="fg:#6b7280")
            return
        existing.unlink()

    questionary.print("  Configuração inicial\n", style="fg:#6b7280")

    fmt = questionary.select(
        "  Formato do arquivo de configuração",
        choices=[
            questionary.Choice("toml  (~/.dont-commit-me.toml)", value="toml"),
            questionary.Choice("json  (~/.dont-commit-me.json)", value="json"),
        ],
        style=STYLE,
    ).ask()

    if fmt is None:
        return

    on_catch = questionary.select(
        "  Ao encontrar um padrão indesejado",
        choices=[
            questionary.Choice("perguntar se deve continuar", value=False),
            questionary.Choice("bloquear e encerrar o commit", value=True),
        ],
        style=STYLE,
    ).ask()

    if on_catch is None:
        return

    add_rule = questionary.confirm(
        "  Adicionar regras padrão? (detecta [wip], [fix-me], TODOs e outros marcadores)",
        default=True,
        style=STYLE,
    ).ask()

    if add_rule is None:
        return

    if fmt == "toml":
        content = _build_toml(stop_on_catch=on_catch, add_simple_rule=add_rule)
        path = CONFIG_PATH_TOML
    else:
        content = _build_json(stop_on_catch=on_catch, add_simple_rule=add_rule)
        path = CONFIG_PATH_JSON

    print()
    questionary.print("  ── Arquivo gerado ──────────────────────", style="fg:#6b7280")
    for line in content.splitlines():
        questionary.print(f"  {line}", style="fg:#374151")
    questionary.print("  ────────────────────────────────────────\n", style="fg:#6b7280")

    path.write_text(content)

    questionary.print(f"  ✓ Salvo em {path}", style="fg:#059669 bold")
    questionary.print("  Pronto! Suas regras estão ativas.\n", style="fg:#6b7280")