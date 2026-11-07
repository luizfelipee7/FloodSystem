# Persistência SQLite — etapa 2

Esta documentação descreve a camada SQLite criada na etapa 2, que utiliza apenas a biblioteca padrão do Python (3.10 ou mais recente). A etapa 3 acrescentou FastAPI e testes HTTP ao projeto; consulte `docs/api.md` para instalar as dependências e iniciar o servidor. A persistência permanece em `sqlite3`.

## Arquivos

- `backend/app/core/config.py`: seleção do ambiente e do arquivo de banco.
- `backend/app/core/database.py`: conexões e aplicação transacional das migrações.
- `backend/app/repositories/telemetry.py`: cadastro de dispositivos, calibrações e persistência das observações.
- `database/migrations/001_initial.sql`: esquema inicial, índices e restrições.
- `backend/.env.example`: referência das variáveis, sem valores físicos de calibração.
- `backend/tests/test_persistence.py`: testes com arquivos temporários independentes.

## Configuração e inicialização

Execute na raiz `D:\FloodSystem` no PowerShell, usando uma instalação Python disponível no computador:

```powershell
Set-Location 'D:\FloodSystem'
$env:FLOODSYSTEM_ENV = 'development'
$env:FLOODSYSTEM_DB_PATH = 'database/development.db'
python -m backend.app.core.database
```

Se `python` não estiver disponível no PATH, use o caminho do interpretador com `& 'caminho\python.exe' -m backend.app.core.database`. O ambiente Python instalado na VM é independente do ambiente Windows.

Neste computador, a implementação foi conferida com o Python disponibilizado pelo aplicativo Codex. Para repetir os comandos com esse interpretador:

```powershell
Set-Location 'D:\FloodSystem'
$floodPython = 'C:\Users\Usuario\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $floodPython -m backend.app.core.database
& $floodPython -m unittest discover -s backend/tests -p test_persistence.py -v
```

Esse caminho pertence ao aplicativo e pode mudar com atualizações. O projeto também funciona com uma instalação independente de Python 3.10 ou mais recente.

Na VM Linux, quando esta etapa for transferida para ela:

```bash
FLOODSYSTEM_ENV=development FLOODSYSTEM_DB_PATH=database/development.db python3 -m backend.app.core.database
```

| Variável | Uso |
| --- | --- |
| `FLOODSYSTEM_ENV` | `development` (padrão), `test` ou `production`. |
| `FLOODSYSTEM_DB_PATH` | Banco da aplicação. Padrão de desenvolvimento: `database/development.db`. Em produção, o valor explícito é obrigatório. |
| `FLOODSYSTEM_TEST_DB_PATH` | Banco exclusivo de testes. Padrão: `database/test.db`. |

Os caminhos relativos são resolvidos pela raiz do projeto, independentemente da pasta do terminal. O ambiente `test` usa exclusivamente `FLOODSYSTEM_TEST_DB_PATH`, mesmo que `FLOODSYSTEM_DB_PATH` esteja definido. Caminhos iguais ao banco configurado da aplicação ou aos padrões de desenvolvimento/produção são rejeitados. O arquivo `.env` não é carregado automaticamente nesta etapa: configure as variáveis no processo/terminal. `.env.example` é apenas um modelo documental.

A inicialização cria o arquivo e as tabelas, sem dispositivos, medições ou calibrações. A migração 001 contém as quatro tabelas de telemetria; a 002 acrescenta as estruturas de proveniência dos ensaios meteorológicos. Sua utilização exige o modo científico e um banco exclusivo, conforme [ensaios-meteorologicos.md](ensaios-meteorologicos.md). Executar a inicialização novamente preserva os dados. `PRAGMA user_version` registra a versão do esquema; alterações futuras devem adicionar migrações, sem modificar uma migração já aplicada. Uma falha durante uma migração desfaz toda a alteração de esquema daquela inicialização.

## Estrutura e regras

| Tabela | Dados principais |
| --- | --- |
| `devices` | `device_id`, `name`, `origin`, `created_at`. |
| `calibrations` | `device_id`, `version`, `valid_from`, `received_at`, `h0_cm`, `k_mm_per_tip`. |
| `level_readings` | `device_id`, `reading_id`, `measured_at`, `received_at`, `distance_cm`, `water_level_cm`, `origin`, `calibration_version`. |
| `rain_tip_events` | `device_id`, `event_id`, `occurred_at`, `received_at`, `origin`, `calibration_version`. |

`origin` aceita `simulation` ou `esp32` e pertence ao cadastro do dispositivo. O repositório copia essa origem para suas observações; uma chave estrangeira composta impede associar uma origem diferente. Dispositivos de simulação devem usar identificadores próprios. O rótulo registra a origem declarada; autenticação e verificação do remetente pertencem à etapa de API/publicação.

Cada conexão habilita as chaves estrangeiras. Escritas usam transações `BEGIN IMMEDIATE` e aguardam até cinco segundos por um bloqueio. O SQLite permanece com seu journal de rollback padrão; não há otimização de desempenho ou benchmark nesta etapa. Índices por dispositivo e horário apoiam as futuras consultas temporais.

Os horários de entrada precisam incluir fuso e são normalizados para UTC com microssegundos, por exemplo `2026-10-06T13:00:00.000000Z`. O horário de recebimento é gerado pelo servidor no primeiro armazenamento. Futuramente o ESP32 deve informar o instante do evento, mesmo quando o envio ocorrer mais tarde.

## Calibrações e ausência de valores físicos

Nenhuma calibração é criada automaticamente. `add_calibration` aceita apenas parâmetros explicitamente fornecidos, positivos e finitos. Pode-se cadastrar somente H₀ ou somente K; o parâmetro desconhecido fica `NULL`. Uma versão inteiramente vazia é rejeitada, pois a ausência de calibração já é representada pela inexistência de uma versão.

As versões são numeradas por dispositivo e seu início de vigência deve avançar no tempo. Cada versão representa um conjunto completo de parâmetros conhecidos; ao criar uma nova versão, repita os parâmetros que continuam válidos. Um campo omitido fica desconhecido nessa versão, sem herdar silenciosamente um valor anterior.

O registro seleciona a versão com maior `valid_from` menor ou igual ao horário da observação, permitindo chegada fora de ordem. A versão escolhida é persistida com a leitura ou basculada. A alteração e a exclusão de versões são bloqueadas no banco por triggers.

- Sem versão aplicável: `calibration_version` é `NULL` e a leitura bruta é preservada.
- Sem H₀ conhecido: `water_level_cm` é `NULL`, nunca zero como substituto.
- Com H₀: a conversão elementar `H₀ - distance_cm` é gravada junto da leitura. Intensidade, velocidade e resumos são calculados sob demanda pela etapa 4, sem alterar os registros; veja `docs/calculations.md`.
- Sem K conhecido: as basculadas continuam armazenadas; não se atribui precipitação fictícia a elas.

O comando local `python -m backend.app.manage add-calibration` aceita H₀, K ou ambos, sempre vinculados a um dispositivo e a um início de vigência explícitos. Para a estimativa física atual do pluviômetro e o comando para cadastrá-la sem H₀, consulte [calibracao-pluviometro.md](calibracao-pluviometro.md). O comando não cria o dispositivo automaticamente e não substitui a calibração de `simulador-01`.

Não há recálculo retroativo automático. Uma calibração adicionada depois não altera registros já recebidos, inclusive quando o identificador é reenviado. Um eventual recálculo histórico deverá ser implementado como operação explícita e rastreável. Também não se força um nível negativo a zero: a distância original e a conversão são preservadas; limites físicos e critérios de qualidade serão definidos com as medidas reais.

## Reenvios e conflitos

As chaves primárias são `(device_id, reading_id)` e `(device_id, event_id)`. O mesmo identificador pode existir em dispositivos diferentes.

- Reenvio com o mesmo conteúdo bruto: retorna `SaveResult(created=False, record=registro_original)` e mantém o primeiro horário de recebimento.
- Mesmo identificador com distância ou horário diferente: gera `DuplicateConflict` e mantém o registro original.
- Registro novo: retorna `created=True`.

As restrições existem no SQLite, além da conferência do repositório. Horários equivalentes em fusos diferentes são comparados após a normalização. Todos os valores externos são passados ao SQL por parâmetros.

## Conferência automatizada

```powershell
Set-Location 'D:\FloodSystem'
& '.\.venv\Scripts\python.exe' -m unittest discover -s backend/tests -v
```

A suíte usa bancos em diretórios temporários e os remove ao terminar. Ela não grava dispositivos, calibrações ou leituras no banco de desenvolvimento. Valores numéricos usados nas fixtures são explicitamente sintéticos, sem relação com a calibração do protótipo.

Os testes cobrem persistência após reabertura, ausência de calibração, UTC, reenvios idênticos e conflitantes, identificadores por dispositivo, calibração parcial e versionada, chegada atrasada, imutabilidade, entrada inválida, chaves estrangeiras, reenvios concorrentes, isolamento de configuração e recuperação de falha de migração.

A etapa 3 conectou o repositório à API e adicionou testes HTTP. A etapa 5 acrescentou o simulador HTTP e o comando administrativo explícito `prepare-simulator` para cadastrar sua calibração sintética; consulte `docs/simulator.md`. Os testes de persistência continuam exercitando essa camada diretamente; as consultas do repositório aceitam período [start, end), limite (padrão 100) e deslocamento.

## Resultado da entrega em 06/10/2026

- 16 testes concluídos com sucesso no Windows, usando Python 3.12.14 e SQLite 3.53.1.
- Banco `D:\FloodSystem\database\development.db` inicializado com as quatro tabelas vazias.
- `PRAGMA integrity_check`: `ok`; nenhuma violação de chave estrangeira.
- Dados sintéticos e calibrações dos testes ficaram exclusivamente nos arquivos temporários da suíte.
- A VM não foi alterada nesta etapa.
