# Guia de Contribuição para `tarifas_carregamento_ve`

Agradecemos o seu interesse em contribuir para o dataset de tarifas de carregamento elétrico!

---

## 🚀 Como Adicionar ou Atualizar um Tarifário

1. **Faça Fork do repositório** no GitHub e crie um novo branch para a sua alteração:
   ```bash
   git checkout -b feature/novo-tarifario-cpo
   ```

2. **Consulte o modelo de referência**:
   - Utilize o ficheiro `src/tariffs/template.yaml` como guia estrutural.
   - O ficheiro inclui comentários explicativos sobre cada campo (ex: `price`, `unit`, `start_after`, `tiers`, `time_restrictions`, `cashback`).

3. **Crie ou edite o ficheiro YAML na diretoria do respetivo país**:
   - Para Portugal: `data/pt/<nome_operador>.yaml`

4. **Valide as suas alterações localmente**:
   ```bash
   uv run tariffs-validate
   ```
   Certifique-se de que a validação passa sem erros de esquema.

5. **Testes automatizados**:
   ```bash
   uv run pytest
   ```

6. **Abra um Pull Request**:
   - Descreva sucintamente as alterações efetuadas.
   - O GitHub Actions irá validar automaticamente a estrutura dos ficheiros YAML antes da aprovação.

---

## 📌 Requisitos de Estrutura dos Ficheiros YAML

- Todo o tarifário deve ter pelo menos um `provider` e um `plan`.
- Cada `tariff` dentro de uma `network` deve definir `price` OU `tiers`.
- As unidades suportadas (`unit`) são: `energy` (€/kWh), `time` (€/min), `flat` (€/carregamento) ou `parking` (€/min).
- Tarifas condicionadas a um limite de tempo ou consumo (ex: taxa de inatividade após 60 min) utilizam o campo opcional `start_after` (ex: `unit: parking`, `start_after: 60`).

