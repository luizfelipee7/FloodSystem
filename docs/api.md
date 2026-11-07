# API do MVP — etapas 3 a 5

API local FastAPI com SQLite. Os dois formatos JSON acordados são aceitos diretamente. Cada dispositivo precisa ser cadastrado com uma origem antes de enviar dados. Nenhum dispositivo ou calibração é criado automaticamente na inicialização.

## Iniciar no Windows atual

O ambiente virtual já foi preparado em `D:\FloodSystem\.venv`. Não é necessário ativá-lo nem ter `python` no PATH para executar:

```powershell
Set-Location 'D:\FloodSystem'
$env:FLOODSYSTEM_ENV = 'development'
$env:FLOODSYSTEM_DB_PATH = 'database/development.db'
& '.\.venv\Scripts\python.exe' -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Mantenha o terminal aberto enquanto usa a API. Para encerrar, pressione Ctrl+C. O servidor cria/aplica o esquema SQLite ao iniciar e preserva os dados existentes. Um erro de inicialização do banco impede o início do serviço.

- Saúde: http://127.0.0.1:8000/health
- Documentação interativa Swagger: http://127.0.0.1:8000/docs
- Contrato OpenAPI: http://127.0.0.1:8000/openapi.json

O serviço local permanece disponível e a versão de produção foi publicada na VM com Nginx/HTTPS/systemd; veja publicacao-vm.md. No teste local, a autenticação permanece desligada por padrão. Em produção, envios exigem token por dispositivo e HTTPS; o cadastro local atribui a origem, mas sozinho não comprova a identidade de quem envia o pacote. A configuração privada da API na VM foi aplicada; a gravação da placa com essa credencial permanece pendente.

## Preparar outro ambiente

Para o teste físico em rede local, o ESP32 precisa alcançar a API pelo IPv4 do computador. Veja [docs/esp32-pluviometro.md](esp32-pluviometro.md) para iniciar a API com `--host 0.0.0.0`, configurar a placa e consultar os eventos. `GET /api/v1/time` não grava dados e retorna `{"unix_ms": ...}`. O horário de recebimento continua sendo criado pela rota de telemetria ao armazenar o evento. O código para autenticação do dispositivo e HTTPS já está preparado; a instalação na VM está documentada em publicacao-vm.md; os detalhes da comunicação segura estão em [seguranca-esp32-vm.md](seguranca-esp32-vm.md).

Com Python 3.12 instalado, a partir da raiz do projeto:

```powershell
python -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r backend/requirements-dev.txt
```

Em Linux, os executáveis equivalentes ficam em `.venv/bin/python`. `backend/requirements.txt` contém as dependências da aplicação; `requirements-dev.txt` acrescenta o cliente HTTP usado pelos testes. A `.venv` é local e ignorada pelo Git: recrie-a ao mover o projeto ou usar outro computador.

Variáveis de ambiente: veja `backend/.env.example` e `docs/sqlite.md`. Um arquivo `.env` não é carregado automaticamente. Bancos de testes usam `FLOODSYSTEM_TEST_DB_PATH` e o ambiente `test`; a suíte usa diretórios temporários exclusivos.

## Cadastrar o dispositivo explicitamente

Em outro terminal, com as mesmas variáveis de ambiente do servidor:

```powershell
Set-Location 'D:\FloodSystem'
$env:FLOODSYSTEM_ENV = 'development'
$env:FLOODSYSTEM_DB_PATH = 'database/development.db'
& '.\.venv\Scripts\python.exe' -m backend.app.manage register-device --device-id simulador-01 --name 'Simulador do MVP' --origin simulation
```

Esse comando local cadastra apenas os metadados do dispositivo, sem medições e sem calibração. Só execute se quiser cadastrar o dispositivo de exemplo. A implementação e os testes não o cadastraram no banco de desenvolvimento.

Origens permitidas: `simulation` e `esp32`. A origem é copiada do cadastro para os registros. O JSON de telemetria não aceita um campo `origin` nem valores derivados como `water_level_cm`; esses campos são definidos pelo servidor. O mesmo comando com os mesmos metadados é idempotente. Metadados diferentes com o mesmo identificador resultam em erro.

Na etapa 5, o simulador passou a ter um preparo próprio: `python -m backend.app.manage prepare-simulator`. Esse comando administrativo cadastra explicitamente `simulador-01` e sua calibração fictícia; não insere telemetria. Veja [o manual do simulador](simulator.md) para preparar o mesmo banco usado pela API e executar os quatro cenários por HTTP. O contrato das rotas de telemetria permanece igual.

## Rotas

| Método | Caminho | Função |
| --- | --- | --- |
| GET | `/health` | Confere a disponibilidade da API e o acesso à tabela de dispositivos. |
| GET | `/api/v1/time` | Informa o relógio UTC da API como `unix_ms` para o ESP32 marcar o instante de cada basculada. |
| POST | `/api/v1/level-readings` | Recebe uma distância bruta e persiste a leitura. |
| POST | `/api/v1/rain-tips` | Recebe de 1 a 500 eventos individuais em uma transação. |
| GET | `/api/v1/level-readings` | Consulta leituras pelo horário de medição. |
| GET | `/api/v1/rain-tips` | Consulta basculadas pelo horário do evento. |
| GET | `/api/v1/summary` | Calcula chuva, intensidade, níveis extremos, variação e velocidade por período. |

### Uma leitura de distância

```json
{
  "device_id": "simulador-01",
  "reading_id": "leitura-0001",
  "measured_at": "2026-10-06T14:05:00Z",
  "distance_cm": 17.9
}
```

Exemplo para enviar pelo PowerShell depois de cadastrar o dispositivo e iniciar a API:

```powershell
$leitura = @{
    device_id = 'simulador-01'
    reading_id = 'leitura-0001'
    measured_at = '2026-10-06T14:05:00Z'
    distance_cm = 17.9
} | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/level-readings' -Method Post -ContentType 'application/json' -Body $leitura
```

Resposta: `{ "created": true, "reading": { ... } }`. Dentro de `reading` estão os campos recebidos, `received_at`, `origin`, `calibration_version` e `water_level_cm`.

- Uma leitura nova retorna HTTP 201.
- O mesmo identificador, instante e distância retorna HTTP 200, `created: false` e o registro original.
- Reutilizar o identificador com outro instante ou distância retorna HTTP 409.
- A versão de calibração é selecionada pelo instante da medição, inclusive em envios atrasados. Se H₀ estiver disponível, o nível é `H₀ - distance_cm`; caso contrário, é `null`.
- O servidor gera `received_at` no primeiro armazenamento. Esse horário não muda em um reenvio.

### Lote de basculadas

```json
{
  "device_id": "simulador-01",
  "events": [
    {
      "event_id": "bascula-0001",
      "occurred_at": "2026-10-06T14:03:12Z"
    },
    {
      "event_id": "bascula-0002",
      "occurred_at": "2026-10-06T14:03:48Z"
    }
  ]
}
```

```powershell
$basculadas = @{
    device_id = 'simulador-01'
    events = @(
        @{ event_id = 'bascula-0001'; occurred_at = '2026-10-06T14:03:12Z' }
        @{ event_id = 'bascula-0002'; occurred_at = '2026-10-06T14:03:48Z' }
    )
} | ConvertTo-Json -Depth 4
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/rain-tips' -Method Post -ContentType 'application/json' -Body $basculadas
```

Resposta HTTP 200 com `inserted_count`, `duplicate_count` e `results`, que contém o resultado `{created, event}` de cada item na ordem recebida. Essas contagens descrevem a gravação do pacote, não a análise de intensidade da chuva.

Um lote misto pode conter eventos novos e já armazenados. Repetições idênticas dentro do próprio pacote também são reconhecidas. O horário original de recebimento de um evento existente é mantido.

O lote é atômico: um identificador com horário conflitante causa HTTP 409 e desfaz todas as novas inserções daquele pacote. Um item inválido causa HTTP 422 antes da gravação. Eventos que já estavam no banco continuam intactos. Ao repetir um envio, mantenha os identificadores originais.

### Consultar um período

Parâmetros obrigatórios: `device_id`, `start` e `end`. O intervalo é **[start, end)**: inclui o início e exclui o fim, evitando repetição ao consultar intervalos adjacentes. O filtro usa `measured_at` para nível e `occurred_at` para chuva, não o horário de recebimento.

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/level-readings?device_id=simulador-01&start=2026-10-06T14:00:00Z&end=2026-10-06T14:10:00Z'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/rain-tips?device_id=simulador-01&start=2026-10-06T14:00:00Z&end=2026-10-06T14:10:00Z'
```

Parâmetros opcionais: `limit` (padrão 100, entre 1 e 1000) e `offset` (padrão 0). A resposta contém os parâmetros normalizados, `items` e `has_more`. Enquanto `has_more` for verdadeiro, consulte a página seguinte com `offset + limit`. A ordem é cronológica, com desempate pelo identificador. Como a paginação é por deslocamento, inserções atrasadas durante a navegação podem mudar a posição dos registros; uma exportação consistente deverá usar um período estabilizado ou uma estratégia de snapshot em etapa futura.

Um período sem registros retorna HTTP 200, `items: []` e `has_more: false`. Um dispositivo não cadastrado retorna HTTP 404.

## Validação e erros

- Identificadores: texto de 1 a 128 caracteres, sem espaços nas extremidades.
- Distância: número JSON finito e não negativo; texto numérico, booleano, `NaN` e infinito são rejeitados. Limites físicos do HC-SR04 ainda dependem das medidas reais.
- Horários: texto ISO 8601 com segundos, fuso explícito (`Z` ou deslocamento) e até seis casas de fração de segundo. Datas sem horário, horários sem fuso e timestamps numéricos são rejeitados.
- Entradas com fusos diferentes são normalizadas para UTC. As respostas apresentam horários em UTC com microssegundos.
- Campos desconhecidos são rejeitados. O instante de recebimento e os valores derivados são controlados pelo servidor.
- HTTP 422: campo inválido, lote vazio/grande demais ou período inválido.
- HTTP 404: dispositivo não cadastrado.
- HTTP 409: identificador reutilizado com conteúdo diferente.
- HTTP 503: falha operacional do SQLite, como bloqueio prolongado. O cabeçalho `Retry-After: 5` orienta aguardar antes de reenviar com os mesmos identificadores.

A versão 0.4.0 acrescenta `GET /api/v1/summary`, com `device_id`, `start`, `end` e `window_minutes` (padrão 5). Consulte [Cálculos do MVP](calculations.md) para fórmulas, unidades, regras de disponibilidade e exemplos de consulta. Indicadores indisponíveis retornam `value: null` com motivo. Não há previsão de chuva, telas ou integração com placa. Nenhuma calibração física foi preenchida.

Se o servidor já estava aberto, reinicie-o para carregar a nova rota. Esta entrega não executou testes funcionais da etapa 4; os resultados abaixo se referem à etapa 3.

## Testes

```powershell
Set-Location 'D:\FloodSystem'
& '.\.venv\Scripts\python.exe' -m unittest discover -s backend/tests -v
& '.\.venv\Scripts\python.exe' -m pip check
```

Os testes HTTP usam TestClient e arquivos SQLite temporários, incluindo gravação real, UTC, consultas por período, paginação, reenvios, rollback de lote, erros de validação e reabertura da aplicação. As fixtures de calibração são sintéticas e restritas aos testes. O teste não inicia um servidor permanente e não preenche o banco de desenvolvimento.

### Validação da entrega em 07/10/2026

- 34 testes aprovados: 16 da persistência/configuração e 18 da API.
- `pip check` sem conflitos de dependências.
- Uvicorn iniciado temporariamente em localhost: cadastro via comando local, `/health`, POST com HTTP 201 e consulta por período confirmados por HTTP real, usando um banco temporário.
- O processo de conferência foi encerrado depois do teste; use o comando de inicialização para abrir a API novamente.
- Banco de desenvolvimento conferido em modo somente leitura: as quatro tabelas permanecem vazias.
- Nenhuma alteração foi aplicada na VM ou nos arquivos da chave privada.

## Referências técnicas

- [FastAPI: inicialização com lifespan](https://fastapi.tiangolo.com/advanced/events/).
- [FastAPI: testes com TestClient](https://fastapi.tiangolo.com/tutorial/testing/).
- [Pydantic: tipos e validação](https://docs.pydantic.dev/latest/api/standard_library_types/).

Consultadas em 07/10/2026. As versões diretamente utilizadas estão registradas nos arquivos de dependências do backend.
