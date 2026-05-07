# dont-commit-me

Hook `pre-commit` que detecta padrões indesejados em linhas adicionadas ao commit.

## Instalação

### pip

```bash
pip install dont-commit-me
```

### pipx (recomendado — sem poluir o ambiente global)

```bash
pipx install dont-commit-me
```

### Local (por repositório)

Adicione ao `.pre-commit-config.yaml` do repositório:

```yaml
repos:
  - repo: https://github.com/PothpothBR/dont-commit-me
    rev: v0.1.0
    hooks:
      - id: dont-commit-me
```

Ative o hook:

```bash
pre-commit install
```

#### A partir do código fonte

Instale o pacote pelo diretório do dont-commit-me:

```bash
pip install -e .
```

Adicione ao `.pre-commit-config.yaml` do repositório:

```yaml
repos:
  - repo: local
    hooks:
      - id: dont-commit-me
```

### Global (todos os repositórios)

Instale o pacote:

```bash
pip install dont-commit-me
```

Crie o diretório de hooks globais e adicione o script:

```bash
mkdir -p ~/.git-hooks

cat > ~/.git-hooks/pre-commit << 'HOOKEOF'
#!/bin/sh
dont-commit-me
HOOKEOF

chmod +x ~/.git-hooks/pre-commit
```

Configure o git para usar o diretório global:

```bash
git config --global core.hooksPath ~/.git-hooks
```

## Configuração

Ao realizar o primeiro commit sem um arquivo de configuração, o `dont-commit-me` exibirá uma mensagem pedindo para rodar o assistente de configuração.

### Assistente de configuração

```bash
# instalado via pip
dont-commit-me --setup

# sem instalar, a partir do código fonte
pipx run --spec . dont-commit-me --setup
```

O arquivo é salvo em `~/.dont-commit-me.toml` ou `~/.dont-commit-me.json` conforme sua escolha. Para reconfigurar, basta rodar o assistente novamente.

### TOML

```toml
[config]
stop_on_catch = false   # true = bloqueia sem perguntar

[[line_rule]]
extensions = [".sql", ".py", ".xml", ".java", ".js", ".ts", ".kt", ".swift", ".c", ".cpp"]
contains = ["[dont-commit-me]", "[wip]", "[fix-me]", "[remove-me]"]

[[line_rule]]
extensions = [".java", ".js", ".ts", ".kt", ".swift", ".c", ".cpp"]
match = "[\s\/*#](?i)TODO[\s\n\t\r:]"

[[file_rule]]
paths = ["**/important.config", "my-project/**/myfile*"]
no_changes = true

[[file_rule]]
paths = ["**/secrets.properties"]
contains = ["password=", "secret="]
```

### JSON

```json
{
  "config": {
    "stop_on_catch": false
  },
  "line_rule": [
    {
      "extensions": [".sql", ".py", ".xml", ".java", ".js", ".ts", ".kt", ".swift", ".c", ".cpp"],
      "contains": ["[dont-commit-me]", "[wip]", "[fix-me]", "[remove-me]"]
    },
    {
      "extensions": [".java", ".js", ".ts", ".kt", ".swift", ".c", ".cpp"],
      "match": "[\s\/*#](?i)TODO[\s\n\t\r:]"
    }
  ],
  "file_rule": [
    {
      "paths": ["**/important.config"],
      "no_changes": true
    }
  ]
}
```

### Campos — line_rule

| Campo | Obrigatório | Descrição |
|---|---|---|
| `extensions` | sim | Extensões monitoradas pela regra |
| `match` | não* | Regex aplicado na linha |
| `start_with` | não | Filtra apenas linhas que começam com um desses prefixos |
| `contains` | não* | Filtra apenas linhas que contêm um desses textos |

\* `match` ou `contains` são obrigatórios. Se ambos definidos, a linha precisa satisfazer os dois.

### Campos — file_rule

| Campo | Obrigatório | Descrição |
|---|---|---|
| `paths` | sim | Padrões de path (suporta `**`, ex: `**/foo.java`) |
| `no_changes` | não* | Bloqueia qualquer alteração no arquivo |
| `match` | não* | Regex aplicado nas linhas adicionadas |
| `contains` | não* | Texto literal a buscar nas linhas adicionadas |

\* `no_changes`, `match` ou `contains` são obrigatórios. `no_changes=true` ignora `match` e `contains`.

### Campos — config

| Campo | Padrão | Descrição |
|---|---|---|
| `stop_on_catch` | `false` | `true` bloqueia sem perguntar, `false` pergunta ao usuário |

## Uso

```bash
# repositório atual
dont-commit-me

# outro repositório
dont-commit-me --repo /path/to/repo

# configuração
dont-commit-me --setup
```

Pode ser executado diretamente se instalado via pip/pipx, ou via pipx sem instalar:

```bash
# a partir do código fonte, sem instalar
pipx run --spec . dont-commit-me

# outro repositório, sem instalar
pipx run --spec . dont-commit-me --repo /path/to/repo
```

## Comportamento

- Analisa apenas linhas **adicionadas** no stage (`git diff --cached`)
- Exibe regra disparada, arquivo, número da linha e trecho destacado
- Com `stop_on_catch = false`: pergunta se deseja continuar mesmo assim
- Com `stop_on_catch = true`: bloqueia o commit imediatamente