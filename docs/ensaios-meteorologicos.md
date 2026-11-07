# Ensaios meteorológicos — primeira entrega

Implementado em 18/10/2026. Esta entrega usa chuva histórica da Open-Meteo/ERA5 para gerar basculadas simuladas. O nível do recipiente e a integração ANA permanecem para etapas posteriores.

## Resultado do primeiro exemplo

- Local solicitado: ponto de referência no centro de São Paulo, latitude `-23.5505`, longitude `-46.6333`.
- Período: 01 a 03/01/2025, dias completos em `America/Sao_Paulo`; UTC `[2025-01-01T03:00:00Z, 2025-01-04T03:00:00Z)`.
- Fonte: Open-Meteo Historical Weather API, modelo explicitamente `era5`, variável `rain`, resolução de 60 minutos.
- 72 intervalos; chuva da fonte **14,50 mm**.
- K adotado: **2,17 mm/basculada**; residual inicial: **0 mm**.
- Resultado: **6 basculadas**, equivalentes a **13,02 mm**, e **1,48 mm** de residual final.
- H₀ registrado: **23 cm**. Não há geração de leituras de nível nesta etapa.
- Execução: `d72e3d0894e8d2314d50199f`.
- Dispositivo virtual: `sim-artigo-d72e3d0894e8d2314d50199f`.

Este é um exemplo de funcionamento e rastreabilidade, escolhido antes do download. Não representa ensaio residencial, de campo ou validação hidrológica; São Paulo é o contexto geográfico. Se a fonte for baixada novamente, seu conteúdo e identificador poderão mudar. Para reproduzir este resultado, reutilize o snapshot preservado.

## Acesso publicado

Abra [https://floodsystem.duckdns.org/ensaios/](https://floodsystem.duckdns.org/ensaios/). A publicação de 18/10/2026 usa a API científica de leitura em `/article-api`, com SQLite próprio na VM. A telemetria física continua em `/api` e no banco de produção separado. O exemplo publicado tem 1 ensaio e 6 basculadas simuladas. Consulte [publicacao-ensaios-vm.md](publicacao-ensaios-vm.md) para caminhos, verificações e cópias de segurança.

## Como abrir a versão local

São dois serviços locais exclusivos. Em um PowerShell:

```powershell
Set-Location 'D:\FloodSystem'
& '.\tools\start-article-api.ps1'
```

Em outro PowerShell:

```powershell
Set-Location 'D:\FloodSystem'
& '.\frontend\start-article.ps1'
```

Abra **http://127.0.0.1:5180/ensaios/**. O mesmo frontend contém as abas Tempo real e Histórico em **http://127.0.0.1:5180/**; seus dados vêm da API publicada via proxy local. A API científica fica em **http://127.0.0.1:8010** e recebe apenas as chamadas de `/article-api`. Se os serviços já estiverem ligados, basta abrir o endereço; não inicie uma segunda cópia nas mesmas portas. `Ctrl+C` no terminal correspondente encerra cada serviço iniciado dessa forma.

O banco é `D:\FloodSystem\database\article-simulations.db`. Os scripts definem `FLOODSYSTEM_ENV=development`, esse caminho e `FLOODSYSTEM_ENABLE_ARTICLE_SIMULATIONS=true`. O modo científico exige banco separado dos caminhos padrão e é recusado em produção. O servidor aceita acesso apenas por loopback.

O painel local 4173 e o domínio público continuam sendo ambientes distintos. A aba científica local só aparece quando o frontend é iniciado com `VITE_EXPERIMENTS_ENABLED=true`; no domínio público, ela está incluída no build publicado. Não use `Simulador.cmd` para iniciar o banco científico: sua opção de API continua apontando para o desenvolvimento normal.

## Preparar ou reenviar o exemplo

Dependência adicional para os fusos IANA no Windows:

```powershell
Set-Location 'D:\FloodSystem'
& '.\.venv\Scripts\python.exe' -m pip install -r tools/weather_simulator/requirements.txt
```

Preparação explícita, com a API parada ou ligada no mesmo banco:

```powershell
& '.\tools\prepare-article-example.ps1'
```

O script reutiliza o snapshot escolhido em `experiments/artifacts/example.json`. Na primeira execução, obtém a resposta da fonte. `-DownloadNew` solicita outro download, preservando os snapshots anteriores.

Com a API 8010 ligada:

```powershell
& '.\tools\send-article-example.ps1'
```

O envio usa exclusivamente HTTP e os endpoints existentes de basculadas. Repetir o envio com o mesmo snapshot e residual reutiliza IDs; as respostas informam novos registros e duplicados. Nenhuma leitura de nível é gerada. O comando recusa destinos que não sejam locais e verifica a identidade da API científica antes do primeiro POST.

## Outros períodos

O downloader aceita até 31 dias. A data final é incluída e ambas as datas são interpretadas em Brasília pela base IANA, convertidas para UTC. Ele solicita uma margem de horas suficiente para o recorte.

```powershell
& '.\.venv\Scripts\python.exe' -m tools.weather_simulator download --latitude -23.5505 --longitude -46.6333 --start-day '2025-01-01' --end-day '2025-01-03'
```

O comando informa a pasta do snapshot. Use essa pasta no lugar de `<PASTA_DO_SNAPSHOT>`:

```powershell
$env:FLOODSYSTEM_ENV = 'development'
$env:FLOODSYSTEM_DB_PATH = 'D:\FloodSystem\database\article-simulations.db'
$env:FLOODSYSTEM_ENABLE_ARTICLE_SIMULATIONS = 'true'
& '.\.venv\Scripts\python.exe' -m backend.app.manage prepare-weather-experiment --snapshot '<PASTA_DO_SNAPSHOT>'
& '.\.venv\Scripts\python.exe' -m tools.weather_simulator send --snapshot '<PASTA_DO_SNAPSHOT>' --base-url 'http://127.0.0.1:8010'
```

Para ver os eventos planejados sem acessar rede nem banco:

```powershell
& '.\.venv\Scripts\python.exe' -m tools.weather_simulator send --snapshot '<PASTA_DO_SNAPSHOT>' --dry-run
```

Também existe o comando `preview --snapshot ...`. `download` é uma operação separada e explicitamente acessa a fonte. O gerador nunca baixa dados durante a prévia ou durante o envio. Para comparar condições iniciais, `--initial-residual-mm` deve ser usado com o mesmo valor na preparação e no envio. Ele aceita de zero até um valor menor que K, gera outro run_id e outro dispositivo virtual.

## Fonte, tempo e conservação

A resposta original e um manifesto são preservados em uma pasta identificada pelo conteúdo dentro de `experiments/artifacts/open-meteo/`. O banco recebe os mesmos bytes originais, seu SHA-256, manifesto e série normalizada. O manifesto inclui URL, parâmetros, modelo, variável, unidade, datas, coordenadas solicitadas, horário de download, versão do importador e atribuição. A execução registra também as coordenadas/elevação da célula retornada.

Uma marca de origem às 14h informa a soma da hora anterior. Ela é normalizada como intervalo `[13h,14h)`, mantendo a marca original em `source_time`. Não tratamos o valor como chuva iniciada às 14h. Lacunas, nulos, negativos, unidades inesperadas e horários duplicados impedem a geração. Horas conhecidas com valor zero permanecem zero.

Para cada intervalo, com aritmética `Decimal`:

```text
disponível = residual anterior + chuva
basculadas = floor(disponível / K)
residual final = disponível − basculadas × K
```

O residual é contínuo entre horas e dias, inclusive em horas secas. A identidade global é `residual inicial + fonte = basculadas × K + residual final`. Uma nova execução é independente; a continuidade entre arquivos deve ser explícita pelo residual inicial. Não se reinicia a báscula a cada hora.

Os horários dos eventos são gerados por cruzamento de limiares na chuva acumulada, assumindo distribuição uniforme por hora. São arredondados a microssegundos. Um cruzamento exatamente no fim da hora é representado pelo último microssegundo dessa hora, deslocamento de no máximo 1 µs, explicitado no perfil para preservar a consulta `[start,end)`. Esses horários são simulados, não instantes observados pela fonte nem pelo ESP32.

`occurred_at` representa a linha do tempo simulada; `received_at` representa a gravação real na API. O envio é acelerado, sem esperar os três dias transcorrerem. Gerador `hourly-rain-v1`, snapshot e perfil determinam os IDs.

## Persistência e contratos

Migração aditiva: `database/migrations/002_weather_experiments.sql`, registrada em `backend/app/core/database.py`. Não altera a migração 001 nem os registros antigos. A migração será aplicada quando uma API com o código atualizado iniciar; nesta entrega, só o banco científico novo foi preparado.

| Tabela | Conteúdo |
| --- | --- |
| `weather_datasets` | Resposta original BLOB, manifesto, hash e importação. |
| `weather_intervals` | Horas normalizadas, marca original e chuva decimal em texto. |
| `simulation_runs` | Fonte, dispositivo exclusivo, período, perfil e totais esperados. |
| `simulation_steps` | Residual antes/depois, contagens esperadas e acumulados por hora. |
| `simulation_expected_tips` | Eventos previstos com vínculo ao intervalo que completou a virada. |

`devices`, `calibrations` e `rain_tip_events` são reutilizadas. A origem permanece `simulation`. O comando administrativo prepara fonte, ledger, dispositivo e calibração em uma transação, sem inserir telemetria. A API recebe a telemetria em lotes de no máximo 500, com atomicidade por lote. O conjunto de lotes não é uma transação única; a contagem recebida define `pending` ou `complete`, e a exportação final exige completude.

No modo científico, a API recusa eventos não previstos ou horários diferentes do manifesto, novas calibrações pelo comando genérico e leituras de nível. O gerador antigo e `simulador-01` conservam seus parâmetros H₀=30/K=0,2 e não são preparados neste banco.

Rotas de leitura:

- `GET /api/v1/experiments/status`: identificação do ambiente científico.
- `GET /api/v1/experiments`: catálogo.
- `GET /api/v1/experiments/{run_id}`: proveniência, perfil, ledger, contagens recebidas e comparação horária.
- `GET /api/v1/experiments/{run_id}/export`: pacote ZIP completo.

Nenhuma rota administrativa de importação foi exposta. O cadastro continua sendo comando local do backend. Fora do modo científico, essas rotas retornam 404.

## Painel e exportação

O script `frontend/start-article.ps1` ativa `VITE_EXPERIMENTS_ENABLED=true` e abre o frontend integrado em 5180. Tempo real e Histórico consultam `/api`, encaminhado à API publicada; Ensaios meteorológicos consulta `/article-api`, encaminhado somente à API científica local 8010. As chamadas continuam exclusivamente em `frontend/src/services/api.ts`. A opção de tema é preservada ao navegar entre as abas. O menu mostra as três áreas, e cada coluna do gráfico horário pode ser selecionada por toque, clique ou teclado para revelar seus valores.

A comparação horária usa resultados calculados pelo backend. A chuva da fonte e a chuva representada são duas séries distintas. A intensidade em 60 minutos tem o mesmo valor numérico do acumulado dessa hora, com unidade mm/h. Janelas sub-horárias não são tratadas como observações meteorológicas. A tabela mostra 24 horas por página; a exportação inclui tudo.

O ZIP contém:

- `source-response.json`: bytes originais da fonte.
- `source-manifest.json`: consulta e atribuição.
- `experiment.json`: parâmetros, proveniência, ledger e estado completo.
- `hourly-comparison.csv`: chuva, intensidade em 60 minutos e residual por hora.
- `simulated-events.csv`: todos os eventos recebidos, seus horários e vínculos.
- `README.txt`: hipóteses e limites de interpretação.

O limite de 10 mil registros da exportação antiga não se aplica a este pacote. A geração admite até 100 mil eventos e 31 dias por execução. Para fazer backup do ensaio, preserve o SQLite científico e/ou seu pacote exportado junto dos snapshots.

Zero basculadas na tabela científica é conhecido a partir do cenário completo. As regras dos resumos físicos existentes não foram alteradas: ausência de eventos físicos continua sem provar chuva zero. Um intervalo simulado com chuva menor que K pode mostrar fonte positiva e zero basculadas.

## Conferências realizadas nesta entrega

- Checagem de tipos TypeScript concluída (`pnpm exec tsc --noEmit`).
- Build do painel científico concluído em `frontend/dist-article/`.
- Download da série real da fonte, preparação do banco exclusivo e envio HTTP do exemplo: 6 eventos confirmados, execução completa.
- Painel aberto no navegador: 72 horas, origem identificada e balanço 14,50 = 13,02 + 1,48 mm.
- Frontend integrado em 5180: navegação entre Tempo real, Histórico e Ensaios; consulta real pela API publicada, consulta científica pelo banco local e seleção de uma hora no gráfico conferidas no navegador.
- Build integrado concluído em `frontend/dist-article/` com `VITE_EXPERIMENTS_ENABLED=true`.
- Exportação pela API concluída: `experiments/artifacts/floodsystem-ensaio-d72e3d0894e8d2314d50199f.zip`; os seis arquivos previstos foram conferidos no pacote.
- Não foi executada suíte automatizada de testes nesta entrega.

Antes de ampliar o uso, a validação automatizada planejada deve cobrir nulos/lacunas, chuva zero, residual atravessando dias, fronteiras horárias, reenvios, conflitos atômicos, isolamento, exportação integral e regressão dos cenários antigos, sempre em bancos temporários.

## Próximas etapas e artigo

### Análise complementar reproduzível para a submissão

O módulo `tools/weather_simulator/article_analysis.py` gera, **offline e sem escrever em qualquer SQLite**, uma auditoria da condição-base e oito casos computacionais: ERA5 original, K ilustrativo −10% e +10%, chuva de cada hora hipoteticamente no primeiro ou último quarto de hora, e séries totalmente sintéticas seca, leve contínua (0,5 mm/h nas primeiras 29 horas) e concentrada (14,5 mm em uma hora). Os dois cenários chuvosos idealizados preservam o total de 14,5 mm do exemplo, mas **não são novos dados ERA5**. Os valores alternativos de K não constituem limites de incerteza física. A análise calcula quantidade de eventos, chuva representada, residual, timestamps e pico de intensidade sintética em cinco minutos; não cria leituras de nível ou classificações de risco.

Para reproduzir em **uma pasta nova**, instale a dependência adicional de gráficos e execute da raiz:

```powershell
& '.\.venv\Scripts\python.exe' -m pip install -r tools/weather_simulator/requirements-analysis.txt
& '.\.venv\Scripts\python.exe' -m tools.weather_simulator.article_analysis `
  --snapshot 'experiments/artifacts/open-meteo/b3add20b15451feebc17952572139d6f0bd707814c14e9fdedd465c1884a1994' `
  --output 'experiments/artifacts/minha-reproducao-artigo' `
  --published-export 'experiments/artifacts/floodsystem-ensaio-d72e3d0894e8d2314d50199f.zip' `
  --scientific-db 'database/article-simulations.db'
```

Os dois últimos argumentos são opcionais. O ZIP é comparado com a resposta original, o manifesto, as 72 linhas horárias e os seis eventos gerados; o banco científico é aberto em modo somente leitura e seus eventos/fonte são confrontados com a condição-base. **Não há reenvio pela API nem acesso à VM.** A saída não pode existir antes da execução, para preservar resultados anteriores. A execução concluída nesta base está em `experiments/artifacts/article-analysis-final-d72e3d0894e8d2314d50199f/`: `report.md`, três CSVs, três figuras em PNG e SVG, `audit.json` e `manifest.json` com hashes. O material de `experiments/artifacts/` é ignorado pelo Git; preserve uma cópia ao preparar o suplemento da submissão. O texto do artigo deve distinguir a condição ERA5 das séries idealizadas e da telemetria física.

O pacote `artigo/FloodSystem_RICSS_Suplemento_Computacional_2026-10-18.zip` reúne o snapshot original, os resultados finais, o ZIP publicado anteriormente, uma cópia do SQLite científico local e o código utilizado. Foi conferido que esse banco contém somente o dispositivo virtual e nenhuma leitura de nível. O pacote pode ser reconstruído com `python -m tools.weather_simulator.package_article_supplement`, fornecendo `--snapshot`, `--analysis`, `--published-export`, `--scientific-db` e uma nova pasta/arquivo em `--output`. Antes de enviar o pacote à RICSS, conferir anonimização e regras para material suplementar.

### Figuras derivadas do ensaio e da implementação

O módulo `tools/weather_simulator/article_figures.py` gera quatro figuras para os espaços reservados do manuscrito: fluxograma real do algoritmo, arquitetura física/científica, chuva horária com os seis instantes sintéticos e os 72 resíduos horários retirados do SQLite científico. Os diagramas têm fonte Mermaid editável; as quatro figuras têm SVG com texto editável e PNG. Os três CSVs usados, legendas e hashes ficam em `artigo/figuras-ricss-ensaio-computacional/`. A figura de residual liga os pontos horários apenas para facilitar a leitura: não interpola observações diárias nem representa nível de água.

```powershell
& '.\.venv\Scripts\python.exe' -m tools.weather_simulator.article_figures `
  --export 'experiments/artifacts/floodsystem-ensaio-d72e3d0894e8d2314d50199f.zip' `
  --scientific-db 'database/article-simulations.db' `
  --output 'artigo/figuras-ricss-ensaio-computacional'
```

O comando confere 72 linhas horárias, seis eventos, continuidade e balanço do residual e a concordância entre ZIP e SQLite. O banco é aberto somente para leitura; não há acesso ao banco físico ou à VM. Se a pasta existir, o gerador só renova arquivos que ainda coincidem com os hashes do seu próprio manifesto; uma edição manual exige escolher outra pasta para preservá-la.

O modelo de nível precisa representar o segundo funil, entrada, armazenamento, drenagem e overflow. H₀=23 cm é a referência operacional de conversão; não determina geometria nem vazão. As dimensões informadas são internas: 87×128×264 mm, saída inferior a 10 mm e overflow a 200 mm da base. Ainda é necessário confirmar a orientação/seção, área do segundo funil, água residual e curva de vazão das mangueiras. Nenhuma relação fixa chuva→nível foi implementada.

No artigo, separar série meteorológica externa de reanálise, eventos produzidos pela simulação e medições físicas. K=2,17 é estimativa experimental inicial. Esta execução demonstra o processamento do sistema, com comparação principal horária; não valida previsões de alagamento nem representa ensaio de campo. A integração ANA é posterior à autorização e deve preservar metadados de estação, qualidade e resolução próprios.

Fontes:

- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api).
- [ERA5 / Copernicus](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview).
- [Termos e atribuição Open-Meteo](https://open-meteo.com/en/terms).
- [Manual HidroWebservice ANA](https://www.gov.br/ana/pt-br/assuntos/monitoramento-e-eventos-criticos/monitoramento-hidrologico/orientacoes-manuais/manuais/manual-hidrowebservice_publica.pdf).
