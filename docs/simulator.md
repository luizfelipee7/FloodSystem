# Simulador HTTP do MVP — etapa 5

## Finalidade e separação de responsabilidades

Este manual descreve os quatro exemplos originais, com H₀=30 cm e K=0,2 mm/basculada. A integração Open-Meteo/ERA5 do artigo usa outro gerador, dispositivos virtuais e banco exclusivo, com H₀=23/K=2,17. Consulte [ensaios-meteorologicos.md](ensaios-meteorologicos.md); não modifique `simulation-profile.json` para converter os exemplos antigos.

O simulador em `tools/simulator` produz quatro séries determinísticas para exercitar o fluxo **cliente → API → SQLite → consultas da API**. A aplicação continua responsável pela persistência, pelo horário de recebimento, pela deduplicação e pelos cálculos.

O cliente de telemetria usa apenas a biblioteca padrão do Python, incluindo `urllib.request`. Não usa SQLite nem repositórios do backend. O módulo auxiliar `local_services.py` inicia os servidores somente quando solicitado no menu e passa o caminho do banco de desenvolvimento ao processo da API. Apenas o backend abre esse banco.

| Operação | Responsável |
| --- | --- |
| Cadastro explícito de `simulador-01` e sua calibração fictícia | Comando local do backend `prepare-simulator`. |
| Geração de horários, distâncias e basculadas | `tools/simulator/scenarios.py`. |
| Envio e consulta | Cliente HTTP em `tools/simulator/client.py`. |
| Atribuição de `origin`, cálculo de nível, gravação e reenvios | API existente. |
| Chuva, intensidade e velocidade | Consulta existente `/api/v1/summary`. |

Não há cadastro automático na inicialização da API nem nova rota administrativa. O simulador não executa o comando de preparação por conta própria. Também não há alteração no esquema do banco.

## 1. Preparar o dispositivo e iniciar a API

No PowerShell, use o mesmo banco configurado para a API. O exemplo utiliza o banco de desenvolvimento, onde os dados simulados ficarão armazenados quando você executar os cenários:

```powershell
Set-Location 'D:\FloodSystem'
$env:FLOODSYSTEM_ENV = 'development'
$env:FLOODSYSTEM_DB_PATH = 'database/development.db'
& '.\.venv\Scripts\python.exe' -m backend.app.manage prepare-simulator
```

O comando imprime o caminho efetivo do banco, se criou o dispositivo e se criou a calibração. Ele lê `tools/simulator/simulation-profile.json` e cadastra somente:

- `device_id`: `simulador-01`;
- origem: `simulation`;
- calibração versão 1, com vigência em `2026-01-01T00:00:00Z`;
- **H₀ fictício = 30 cm** e **K fictício = 0,2 mm/basculada**.

Esses valores permitem executar exemplos reproduzíveis. **Não foram medidos e não representam a calibração física do protótipo.** O comando não insere leituras nem basculadas. Repetir a preparação com o mesmo perfil reutiliza o cadastro e a versão existentes.

O cadastro é transacional. Se `simulador-01` tiver origem física, calibração diferente ou registros sem a calibração esperada, a operação informa o conflito e preserva o histórico. O comando recusa o ambiente `production`. Não altera nenhum outro dispositivo.

Se houver conflito com dados anteriores, use explicitamente outro arquivo, por exemplo `$env:FLOODSYSTEM_DB_PATH = 'database/simulation.db'`, e execute tanto a preparação quanto a API com esse mesmo caminho. Esse arquivo também fica ignorado pelo Git. Não apague o banco existente para resolver o conflito.

Depois que a preparação terminar sem erro, inicie a API **no mesmo terminal**, mantendo as variáveis:

```powershell
& '.\.venv\Scripts\python.exe' -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Se o servidor já estiver aberto, não inicie outro na mesma porta. Use Ctrl+C no terminal original antes de reiniciá-lo com a configuração desejada. Mantenha o terminal do servidor aberto.

Abra http://127.0.0.1:8000/docs para ver as rotas. Em outro terminal você executará o simulador.

## 2. Executar os quatro cenários

### Opção mais simples: menu no terminal

Abra **`D:\FloodSystem\Simulador.cmd`** com dois cliques no Explorador. Você também pode executá-lo no PowerShell:

```powershell
Set-Location 'D:\FloodSystem'
.\Simulador.cmd
```

O menu apresenta:

```text
SIMULAÇÃO DE DADOS

  1 - Sem chuva e nível estável
  2 - Dez basculadas em cinco minutos
  3 - Nível subindo e descendo
  4 - Chuva seguida de alteração do nível

SERVIÇOS LOCAIS

  5 - Ligar a API local (backend)
  6 - Ligar o site local (frontend / localhost)
  7 - Atualizar status da API e do site
  8 - Abrir o site no navegador

VALIDAÇÃO

  9 - Validar o fluxo completo (banco temporário)
  0 - Sair
```

Para simular dados, escolha 1 a 4. Para iniciar ou consultar os serviços, use as opções 5 a 8, que ficam em seção separada no menu. A opção 9 repete a validação da etapa 7. Para sair, escolha 0. Após cada escolha, o menu limpa a tela e mostra só a operação atual; o resultado fica visível até você pressionar Enter para retornar ao menu.

1. Digite o número do cenário e pressione Enter.
2. Pressione Enter novamente para manter o horário padrão, ou informe outro horário com fuso no formato indicado.
3. Na opção 4, informe o atraso em segundos; Enter mantém 120 segundos.
4. O programa envia o cenário pela API e mostra quantos registros são novos ou já existiam.
5. Ele informa o filtro do site correspondente; para outro início ou atraso, mostra os limites que devem ser usados no período personalizado.
6. Pressione Enter para voltar ao menu e escolher outro cenário.

A seleção de cenário inicia o envio depois das perguntas. Faça a preparação do dispositivo descrita na seção 1. Se a conexão falhar, o menu informa o erro e permite voltar. Registros já enviados permanecem no SQLite; os mesmos parâmetros permitem repetir sem duplicações.

#### Ligar a API e o site pelo menu

1. Se a API estiver desligada, escolha **5**. O menu aguarda a resposta de `/health` e verifica a identidade da API pelo `/openapi.json`.
2. Escolha **6** para ligar o frontend e aguarde a página do FloodSystem responder.
3. Escolha **8** para abrir **http://127.0.0.1:5173/** no navegador padrão.
4. Escolha **1 a 4** para enviar dados; no site, aplique o filtro indicado ao terminar.

O status é consultado ao retornar ao menu; **7** permite consultar novamente. **LIGADO** significa que o serviço esperado respondeu. **DESLIGADO** significa conexão recusada na porta. **PORTA OCUPADA** indica que existe um serviço, mas ele ainda está iniciando, apresentou falha ou não foi identificado como FloodSystem; nessa condição, nenhum processo adicional é iniciado. Se não for possível verificar a porta, o status é indeterminado e o menu também evita iniciar outra cópia. API e frontend são avaliados separadamente; frontend ligado não comprova que a API está saudável.

Os servidores ficam em segundo plano, com logs em `D:\FloodSystem\.logs\api-menu.log` e `D:\FloodSystem\.logs\site-menu.log`. O PID é mostrado ao iniciar. Fechar o menu não encerra os serviços; reiniciar o computador os encerra, e depois será necessário ligá-los novamente. Para encerrar manualmente um serviço iniciado pelo menu, use o Gerenciador de Tarefas, aba Detalhes, identificando o PID exibido.

A API iniciada pela opção 5 usa explicitamente `development` e `D:\FloodSystem\database\development.db`, sem alterar os arquivos existentes nem preparar o simulador. A inicialização normal do backend pode criar o esquema vazio se o banco ainda não existir. Para um banco personalizado, use a inicialização manual da seção 1; se essa API já estiver respondendo, o menu apenas a reutiliza, sem mudar sua configuração. A opção 6 encaminha o frontend para a API local na porta 8000. Com `--base-url` remoto ou porta diferente, a opção 5 não inicia essa API; o painel local continua apontando para 8000. O status não informa qual banco uma API já existente usa.

Essas opções ligam o ambiente de desenvolvimento neste computador. Não há publicação na VM nem inicialização automática junto com o Windows. O menu não abre o banco nem cadastra calibrações.

#### Validar o fluxo completo pelo menu

Escolha **9** para executar `backend/tests/validate_stage7.py`. O teste inicia sua própria API e seu próprio frontend em portas locais temporárias, envia cenários sintéticos, confere as consultas e a interface, reinicia a API e encerra esses processos no final. Usa um **SQLite temporário separado** e o descarta ao terminar. Não acrescenta dados ao banco de desenvolvimento e não muda os números exibidos no site local normal. O relatório detalhado está em [validation-stage7.md](validation-stage7.md). O menu espera a validação terminar e deixa o resultado na tela até você pressionar Enter.

Para usar o menu sem enviar nada:

```powershell
.\Simulador.cmd --dry-run
```

Nesse modo, o terminal mostra os pacotes e não acessa a API. As opções 5 a 9 e as consultas de status ficam desabilitadas: nenhum servidor é iniciado e nenhum teste é executado. Uma API em outro endereço pode ser selecionada com `--base-url`. A alternativa multiplataforma é `python -m tools.simulator menu`, usando o Python do ambiente virtual. Sem informar cenário, `python -m tools.simulator` também abre o menu.

O menu foi acrescentado em 09/10/2026. Os comandos diretos abaixo continuam disponíveis.

### Alternativa: escolher pelo comando

No segundo PowerShell:

```powershell
Set-Location 'D:\FloodSystem'
```

Os instantes padrão ficam fixos em UTC para que os cenários não se misturem nas consultas. O menu os apresenta e pede novos horários em Brasília (`America/Sao_Paulo`, UTC−3). Ao digitar outro horário, use o fuso explicitamente, por exemplo `2026-10-09T20:27:00-03:00`. A API converte tudo para UTC ao gravar. Os pacotes são enviados em sequência sem esperar os minutos simulados passarem. `measured_at` e `occurred_at` representam a linha do tempo fictícia; `received_at` representa o momento real em que a API salvou cada registro.

### A. Sem chuva e nível estável

```powershell
& '.\.venv\Scripts\python.exe' -m tools.simulator sem-chuva
```

- Período: **09:00:00 até 09:05:00 em Brasília em 08/10/2026**, fim excluído.
- Seis leituras, nos segundos 0, 60, 125, 190, 250 e 299.
- Distância constante de 20 cm; com H₀ fictício de 30 cm, nível de 10 cm.
- Nenhuma basculada e nenhum POST de lote vazio.
- Variação e velocidade esperadas: zero.

Na regra atual da etapa 4, zero basculadas armazenadas não comprova chuva zero. Assim, a contagem será 0, mas os indicadores de chuva/intensidade estarão indisponíveis com `no_rain_events`. O cenário sabe que não gerou chuva; a API ainda não recebe um sinal de cobertura contínua da coleta. Essa diferença é intencional e não foi alterada nesta etapa.

### B. Basculadas em cinco minutos

```powershell
& '.\.venv\Scripts\python.exe' -m tools.simulator chuva-5min
```

- Período: **10:00:00 até 10:05:00 em Brasília em 08/10/2026**.
- Mesmas seis leituras estáveis, sem impor subida em consequência da chuva.
- Dez basculadas, nos segundos 15, 45, 75, 105, 135, 165, 195, 225, 255 e 285.
- Basculadas enviadas em um único pacote, cada uma com ID e horário próprios.
- Valores matemáticos esperados com o perfil fictício: **2 mm acumulados** e **24 mm/h** na janela de cinco minutos.

### C. Nível subindo e descendo

```powershell
& '.\.venv\Scripts\python.exe' -m tools.simulator sobe-desce
```

- Período: **11:00:00 até 11:10:01 em Brasília em 08/10/2026**.
- Nove leituras; nenhuma basculada.
- Níveis fictícios: 10, 11, 13, 16, 20, 18, 15, 12 e 10 cm.
- Instantes relativos: 0, 47, 123, 205, 300, 376, 449, 527 e 600 segundos.
- A última leitura entra na consulta porque o fim exclusivo fica um segundo depois dela.

O resumo do período completo mostra velocidade média zero, pois o nível final retorna ao inicial. Para observar os dois movimentos separadamente, consulte:

- Subida: 08/10/2026 11:00:00–11:05:01 em Brasília → 10 cm em 300 s, **+2 cm/min**.
- Descida: 08/10/2026 11:05:00–11:10:01 em Brasília → −10 cm em 300 s, **−2 cm/min**.

Os valores são expectativas matemáticas dos exemplos, não resultados de ensaio do protótipo. A velocidade do resumo usa os horários reais dos extremos, mesmo com intervalos irregulares intermediários.

### D. Chuva seguida de alteração de nível com atraso

```powershell
& '.\.venv\Scripts\python.exe' -m tools.simulator chuva-atraso --delay-seconds 120
```

- Início padrão: **12:00:00 em Brasília em 08/10/2026**.
- Dez basculadas nos primeiros cinco minutos, nos mesmos deslocamentos do cenário B.
- O atraso é medido **a partir do fim da janela de chuva**, às 12:05:00, e não da última basculada (12:04:45).
- Com 120 segundos de atraso, a primeira leitura alterada ocorre às **12:07:00**, com nível fictício de 12 cm.
- Até esse instante, as leituras permanecem em 10 cm. A partir da alteração, os níveis seguem 12, 14, 16, 18, 20, 18, 14 e 10 cm, espaçados por 60 segundos.
- O período termina às **12:14:01 em Brasília**, incluindo a leitura final das 12:14:00.

O parâmetro aceita de 0 a 3600 segundos. Para executar outra configuração sem misturar com os dados anteriores, escolha outro início:

```powershell
& '.\.venv\Scripts\python.exe' -m tools.simulator chuva-atraso --delay-seconds 300 --start '2026-10-09T15:00:00Z'
```

Não existe fórmula que converta os milímetros de chuva em centímetros de nível. A curva de nível é uma sequência fictícia definida separadamente; o atraso apenas posiciona essa sequência na linha do tempo. Geometria, escoamento e resposta física ainda não foram modelados ou medidos.

O resumo completo desse cenário usa a janela de intensidade encerrada no final do período, quando já não há basculadas. Para consultar a intensidade calculada pela **API** durante a chuva, use apenas **12:00:00–12:05:00 em Brasília** do dia escolhido; nesse recorte, a expectativa é 24 mm/h com o perfil fornecido. No site, o Histórico mostra a chuva acumulada e as basculadas desse recorte.

## 3. Prévia, repetição e retomada

Para inspecionar todos os pacotes e o perfil sem acessar API ou SQLite:

```powershell
& '.\.venv\Scripts\python.exe' -m tools.simulator chuva-5min --dry-run
```

Também é possível selecionar uma API explicitamente:

```powershell
& '.\.venv\Scripts\python.exe' -m tools.simulator sem-chuva --base-url 'http://127.0.0.1:8000'
```

Os IDs são derivados da versão do gerador, cenário, início UTC, perfil e atraso aplicável. **O mesmo comando gera os mesmos horários, valores e IDs.** Um reenvio deve retornar registros já existentes, preservando seus horários originais de recebimento. Alterar o início ou os parâmetros gera outro conjunto de IDs.

Antes de enviar, o cliente consulta a origem do dispositivo e os registros do período. Recusa uma origem diferente de `simulation` e dados de outro cenário ou com parâmetros diferentes no mesmo intervalo. A verificação usa paginação para examinar os registros existentes. Não execute dois cenários simultaneamente sobre o mesmo período: a consulta preventiva e os envios são requisições separadas.

O envio não é uma transação única do cenário inteiro. Cada leitura é uma requisição, e as basculadas formam um lote atômico. Se a conexão cair, parte do cenário pode já estar gravada. Reexecute o mesmo comando: os identificadores permitem retomar sem duplicar. O cliente também repete até três tentativas em falhas transitórias, sempre com o mesmo corpo e IDs.

HTTP 404 normalmente significa que `simulador-01` ainda não foi preparado no banco usado pelo servidor. Uma calibração divergente exige conferir a preparação; o cliente verifica as respostas, mas uma requisição recebida antes de detectar o problema pode já ter sido persistida. Ele não apaga ou corrige dados automaticamente.

Ao terminar, o programa imprime contagens de novos registros e duplicados, o perfil utilizado, o resumo recebido do backend e URLs de consulta. A mensagem **DADOS SINTÉTICOS** identifica explicitamente o resultado.

## 4. Consultar os dados gravados no SQLite pela API

A API lê o arquivo SQLite configurado no terminal do servidor. Consultar essas rotas permite visualizar o que foi persistido sem dar acesso ao banco ao simulador.

Exemplo para o cenário de chuva de cinco minutos:

```powershell
$periodo = 'device_id=simulador-01&start=2026-10-08T13:00:00Z&end=2026-10-08T13:05:00Z'
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/level-readings?$periodo" | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/rain-tips?$periodo" | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/summary?$periodo&window_minutes=5" | ConvertTo-Json -Depth 10
```

Confira `origin: "simulation"`, `device_id: "simulador-01"`, `calibration_version: 1` e os horários. As rotas de listagem têm paginação; para esses exemplos, a página padrão de 100 itens comporta cada cenário. Se acumular mais registros e `has_more` for verdadeiro, avance `offset` pelo valor de `limit`.

Você também pode usar **Try it out** nas mesmas rotas em http://127.0.0.1:8000/docs. Para outro cenário, use os limites indicados acima ou as URLs impressas pelo simulador.

## 5. Inspeção opcional do arquivo SQLite

No SQLite Viewer do editor, abra o arquivo apontado por `FLOODSYSTEM_DB_PATH`, normalmente `D:\FloodSystem\database\development.db`. Atualize a visualização após enviar os cenários.

- `devices`: o cadastro de `simulador-01` com origem `simulation`;
- `calibrations`: H₀ e K fictícios na versão 1 desse dispositivo;
- `level_readings`: distâncias, horários e níveis calculados pelo servidor;
- `rain_tip_events`: cada basculada individual com ID e horário.

Se utilizar uma ferramenta que aceite SQL de consulta, estes comandos são somente leitura:

```sql
SELECT * FROM devices WHERE device_id = 'simulador-01';
SELECT * FROM calibrations WHERE device_id = 'simulador-01';
SELECT reading_id, measured_at, received_at, distance_cm, water_level_cm,
       origin, calibration_version
FROM level_readings WHERE device_id = 'simulador-01'
ORDER BY measured_at, reading_id;
SELECT event_id, occurred_at, received_at, origin, calibration_version
FROM rain_tip_events WHERE device_id = 'simulador-01'
ORDER BY occurred_at, event_id;
```

Essa inspeção é manual. O programa em `tools/simulator` continua usando somente HTTP.

## 6. Integração futura e limites

O ESP32 usará as mesmas rotas e campos de telemetria. Deverá ter outro identificador de dispositivo, origem `esp32` e calibrações obtidas experimentalmente. Não reutilize o perfil sintético nem o cadastro `simulador-01` para a placa física.

O campo `origin` não vai no JSON enviado, porque o contrato da etapa 3 atribui a origem a partir do cadastro no servidor. Todos os registros desses cenários recebem `simulation` por essa associação. O `profile_id` e a configuração do gerador ficam no arquivo versionado e na saída do comando; as observações guardam a referência à calibração do dispositivo no SQLite.

O simulador e o preparo explícito do cadastro foram implementados na etapa 5. A validação integrada posterior está documentada em [validation-stage7.md](validation-stage7.md). A publicação na VM permanece para uma etapa seguinte.

Conferência em 08/10/2026 da etapa 5: `python -m compileall -q tools/simulator backend/app/manage.py backend/app/repositories/simulation_setup.py` terminou sem erros. A revisão dos arquivos Python em `tools/simulator` não encontrou importação do backend, uso de `sqlite3` ou configuração de caminho de banco. Os testes integrados posteriores estão registrados no relatório da etapa 7.
