# Cálculos do MVP — etapa 4

Implementação local em `D:\FloodSystem`, usando os registros já armazenados no SQLite. A consulta é somente leitura: não cria dispositivos, calibrações, medições ou basculadas. A etapa 4 não incluiu simulador, frontend, classificação de risco ou integração física. O simulador foi acrescentado na etapa 5; veja `docs/simulator.md`.

## Organização

- `backend/app/services/formulas.py`: conversão de distância em nível, compartilhada pela recepção e pelo resumo.
- `backend/app/services/calculations.py`: chuva acumulada, intensidade, variação, velocidade e motivos de indisponibilidade.
- `backend/app/repositories/analytics.py`: consultas SQL do resumo em uma única transação de leitura.
- `backend/app/schemas/analytics.py`: parâmetros e respostas documentados no OpenAPI.
- `backend/app/api/v1/routes/analytics.py`: `GET /api/v1/summary`.

O esquema do banco continua na versão 1. Os resumos são calculados sob demanda, sem tabelas agregadas ou alteração dos registros brutos. As contagens consideram todos os registros do período, sem o limite de paginação das rotas de telemetria. A transação de leitura mantém uma visão consistente entre as contagens, os extremos de nível e a janela de intensidade.

## Consultar pela API

Reinicie o Uvicorn se ele já estiver aberto sem `--reload`: Ctrl+C no terminal do servidor e execute novamente:

```powershell
Set-Location 'D:\FloodSystem'
& '.\.venv\Scripts\python.exe' -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Abra http://127.0.0.1:8000/docs, seção **Cálculos**, operação **GET /api/v1/summary**. Use **Try it out**, preencha os parâmetros e clique em **Execute**.

| Parâmetro | Significado |
| --- | --- |
| `device_id` | Identificador de um dispositivo já cadastrado. |
| `start` | Início incluído do período, ISO 8601 com fuso. |
| `end` | Fim excluído do período, ISO 8601 com fuso, posterior ao início. |
| `window_minutes` | Duração da janela de intensidade. Padrão 5; maior que zero e até 1440 minutos. Aceita frações com resolução temporal de microssegundos. |

Exemplo de consulta, somente se esse dispositivo já existir:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/summary?device_id=simulador-01&start=2026-10-06T14:00:00Z&end=2026-10-06T14:10:00Z&window_minutes=5' | ConvertTo-Json -Depth 10
```

O exemplo não cadastra nada. Um dispositivo inexistente retorna HTTP 404. Parâmetros inválidos retornam 422. Um dispositivo cadastrado, mas sem observações, retorna 200 com contagens zero e indicadores indisponíveis. A origem (`simulation` ou `esp32`) vem do cadastro.

## Tempo e unidades

Todos os filtros usam **[start, end)**: incluem o instante inicial e excluem o final. Fusos são normalizados para UTC. Leituras usam `measured_at`; basculadas usam `occurred_at`. `received_at` não entra nas fórmulas: atrasos de rede não representam o intervalo físico entre medições.

Resultados não são arredondados para apresentação. O frontend poderá formatá-los posteriormente. Unidades são explícitas: distância, nível e variação em **cm**; chuva em **mm**; intensidade em **mm/h**; velocidade em **cm/min**. Não se compara diretamente mm/h com cm e não se estabelece uma relação fixa entre chuva e subida da água.

### Nível

`nível_cm = H₀_cm − distância_cm`

H₀ é a distância até a referência de nível zero. A mesma função é usada ao armazenar uma leitura e ao calcular os extremos do resumo. Usa-se a versão de calibração vinculada à observação. Não se aplica a calibração mais recente a todas as leituras históricas.

Sem H₀, a distância permanece disponível e o nível é `null`. Um nível negativo é preservado, sem correção silenciosa para zero; os critérios de validade física ainda dependem das medidas do protótipo.

### Chuva acumulada

Com K constante: `chuva_mm = número_de_basculadas × K_mm_por_basculada`.

Se houver várias versões de K, o resultado é `Σ (basculadas_da_versão × K_da_versão)`. O resumo informa as contagens e K de cada versão, permitindo rastrear o cálculo. Reenvios não aumentam a contagem, pois a persistência já impede repetir a mesma chave `(device_id, event_id)`.

Se qualquer basculada do período não tiver K, a contagem continua disponível, mas a chuva total fica indisponível. Não se apresenta a soma parcial das basculadas calibradas como se fosse o total.

**Zero eventos não comprova ausência de chuva.** Ainda não existe confirmação de cobertura de coleta ou comunicação contínua. Por isso, um período sem basculadas retorna `tip_count: 0`, mas precipitação e intensidade indisponíveis (`no_rain_events`). Mesmo com eventos, os resultados descrevem os registros recebidos; eventos perdidos ou ainda não enviados podem causar subestimação.

### Intensidade

A janela termina em `end`: **[end − window_minutes, end)**. Por exemplo, para um resumo das 14:00 às 14:10 com janela de 5 minutos, a chuva acumulada cobre todo o período e a intensidade usa apenas as basculadas das 14:05 às 14:10.

`intensidade_mm_h = chuva_da_janela_mm / duração_real_da_janela_em_segundos × 3600`

Equivalente a `chuva_da_janela_mm × 60 / T_minutos`. A duração vem dos limites temporais da janela, não do intervalo entre a primeira e a última basculada. Esta é a intensidade média da janela, não uma previsão nem uma medida instantânea.

Se o período solicitado for menor que a janela, a intensidade fica indisponível (`period_shorter_than_window`). A janela não é encurtada automaticamente e não utiliza eventos anteriores ao período solicitado. Nesse caso, `intensity.rain` é `null`; o acumulado do período continua sendo calculado quando possível. Para uma janela menor, informe `window_minutes` explicitamente.

A disponibilidade da intensidade é independente do acumulado: uma basculada sem K fora da janela pode impedir o acumulado total, sem impedir a intensidade da janela cujas basculadas estejam todas calibradas.

### Variação e velocidade do nível

O nível inicial corresponde à primeira medição do período; o final, à última. Os respectivos horários são devolvidos, pois podem não coincidir com `start` e `end`. Não há interpolação nem preenchimento de intervalos sem leituras.

`variação_cm = nível_final_cm − nível_inicial_cm`

`tempo_segundos = horário_da_última_medição − horário_da_primeira_medição`

`velocidade_cm_min = variação_cm / tempo_segundos × 60`

A velocidade é a média entre os extremos, podendo esconder subidas e descidas intermediárias. Valor positivo significa subida; negativo, descida; zero indica níveis extremos iguais. Não se pressupõe uma leitura por minuto.

Condições conservadoras deste MVP:

- Pelo menos duas leituras e um intervalo temporal positivo são necessários para variação e velocidade.
- Se alguma leitura do período não tiver H₀, ambos os indicadores ficam indisponíveis. Níveis extremos individualmente calibrados ainda podem ser mostrados.
- Se as leituras usarem valores diferentes de H₀, variação e velocidade ficam indisponíveis (`h0_changed`), evitando confundir mudança de referência com movimento da água. Versões diferentes com o mesmo H₀ não impedem o cálculo.
- Se no instante inicial ou final houver leituras com distâncias ou referências de calibração diferentes, o extremo é ambíguo. Seu nível e identificação ficam indisponíveis, assim como variação e velocidade. Não se escolhe um valor pela ordem do identificador.
- Não há um limite inventado para lacunas entre medições. O intervalo efetivo é informado em `elapsed_seconds`.

## Estrutura da resposta

| Campo | Conteúdo |
| --- | --- |
| `device_id`, `origin`, `start`, `end` | Dispositivo, origem e limites UTC. |
| `rain.tip_count` | Número de basculadas armazenadas no período. |
| `rain.uncalibrated_tip_count` | Basculadas sem K na versão vinculada. |
| `rain.calibrations` | Grupos com versão, K e contagem. |
| `rain.accumulated_rainfall` | Indicador de chuva acumulada em mm. |
| `intensity.start`, `intensity.end`, `intensity.window_minutes` | Limites e duração da janela. |
| `intensity.rain` | Contagem e chuva apenas da janela, ou null se ela ultrapassar o início do período. |
| `intensity.intensity` | Indicador de intensidade em mm/h. |
| `level.reading_count`, `level.uncalibrated_reading_count` | Contagens de leituras e leituras sem H₀. |
| `level.initial`, `level.final` | ID, horário, distância, H₀, versão e indicador de nível; null se não houver leituras. |
| `level.elapsed_seconds` | Tempo real entre os extremos; null sem leituras. |
| `level.level_change`, `level.velocity` | Indicadores de variação e velocidade média. |

Cada indicador segue este formato (exemplo de indisponibilidade):

```json
{
  "value": null,
  "unit": "mm",
  "status": "unavailable",
  "reason": "missing_k"
}
```

Um resultado disponível possui valor numérico, `status: "available"` e `reason: null`. Nunca interpretar `null` como zero.

| Motivo | Significado |
| --- | --- |
| `no_rain_events` | Nenhuma basculada registrada no intervalo; cobertura desconhecida. |
| `missing_k` | Pelo menos uma basculada sem K. |
| `missing_h0` | H₀ ausente em leitura necessária ao cálculo. |
| `insufficient_level_readings` | Menos de duas leituras. |
| `h0_changed` | Mudança de H₀ nas leituras do período. |
| `ambiguous_endpoint` | Leituras conflitantes no instante inicial ou final. |
| `nonpositive_elapsed_time` | Sem intervalo positivo entre os extremos. |
| `period_shorter_than_window` | Período menor que a janela solicitada. |
| `numeric_overflow` | Resultado excede a representação numérica finita. |

Quando várias condições impedem um indicador, a resposta informa um motivo principal; contagens e extremos ajudam a identificar as demais condições.

## Exemplo matemático, sem cadastro no banco

Valores exclusivamente didáticos, **não são calibrações do protótipo**:

- Período 14:00–14:05 UTC; H₀ = 30 cm; K = 0,2 mm/basculada.
- Três basculadas no período: chuva = 3 × 0,2 = 0,6 mm.
- Janela de cinco minutos: intensidade = 0,6 × 60 / 5 = 7,2 mm/h.
- Primeira leitura às 14:01:10, distância 20 cm: nível = 10 cm.
- Última leitura às 14:04:40, distância 13 cm: nível = 17 cm.
- Intervalo real = 210 segundos = 3,5 minutos; variação = 7 cm; velocidade = 2 cm/min.

Os cinco minutos da janela de chuva e os 3,5 minutos entre as medições de nível têm funções diferentes. Nenhum desses valores foi inserido no SQLite por esta implementação.

## Calibração e limites da entrega

Calibrações continuam sendo cadastradas explicitamente pelo repositório, sem rota nova de administração. Uma versão é um conjunto completo: parâmetros omitidos permanecem desconhecidos. A referência gravada em cada observação é preservada, inclusive quando uma calibração é cadastrada depois com vigência anterior à observação. Não há recálculo retroativo que altere essas referências.

O resumo usa os mesmos registros enviados pelo simulador da etapa 5 e previstos para o ESP32. O perfil do simulador identifica seus parâmetros como sintéticos. Nenhuma calibração física foi inventada e nenhum dado foi inserido na implementação da etapa 4.

Conferência em 08/10/2026: `python -m compileall -q backend/app` concluiu sem erros de sintaxe. A implementação não executou testes funcionais dos cálculos. Os resultados de testes das etapas anteriores, documentados em `api.md` e `sqlite.md`, não constituem validação desta etapa.
