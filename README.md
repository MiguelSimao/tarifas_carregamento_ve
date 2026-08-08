# tarifas_carregamento_ve

Dataset open-source e especificações para tarifas de carregamento de veículos elétricos (EVs).

---

## Visão Geral

Este repositório contém a definição de tarifários de CPOs (Charge Point Operators) e MSPs (Mobility Service Providers). Os dados são fornecidos em formato **YAML** e validados automaticamente com schemas em **Pydantic**. Os ficheiros são compilados num dataset central consolidado (`data/tariffs_master.json`).

---

## Estrutura do Repositório

```text
tarifas_carregamento_ve/
├── data/
│   ├── tariffs_schema.json    # Schema JSON
│   ├── tariffs_master.json    # Dataset consolidado
│   └── pt/                    # Tarifários (Portugal) em formato YAML
│       ├── continente.yaml
│       ├── galp.yaml
│       └── ...
├── src/
│   └── tarifas/
│       ├── model.py           # Modelos Pydantic
│       ├── validate.py        # Validador de YAMLs
│       ├── compile.py         # Compilador para data/tariffs_master.json
│       ├── generate_schema.py # Gerador de schema JSON
│       └── template.yaml      # Exemplo de referência
└── tests/                     # Conjunto de testes
```

---

## Utilização e Comandos CLI

Pré-requisitos:
- [`uv`](https://github.com/astral-sh/uv)


### 1. Instalar dependências
```bash
uv sync
```

### 2. Validar ficheiros YAML
```bash
uv run tariffs-validate
```

### 3. Compilar dataset
```bash
uv run tariffs-compile
```

### 4. Gerar schema JSON
```bash
uv run tariffs-generate-schema
```

### 5. Executar testes
```bash
uv run pytest
```

---

## Como Contribuir

Consulte o guia detalhado em [CONTRIBUTING.md](CONTRIBUTING.md) para adicionar novos tarifários ou atualizar tarifários existentes.

---

## Licença (Dual License)

- **Código & Ferramentas**: [Licença MIT](LICENSE.md#1-software-code--tooling-mit-license)
- **Datasets YAML & JSON**: [Creative Commons Attribution 4.0 International (CC-BY-4.0)](LICENSE.md#2-dataset-files--specifications-cc-by-40)
