# Frontend do MVP — Tempo real e Histórico

Interface React + TypeScript com Vite, criada em `D:\FloodSystem\frontend`. O desenho usa as imagens de referência como base: navegação lateral, indicadores, gráficos e registros. A interface não acessa o SQLite, não insere telemetria e não cria calibrações.

## Abrir neste computador

As dependências do frontend já estão instaladas. Mantenha o backend aberto em um PowerShell:

```powershell
Set-Location 'D:\FloodSystem'
& '.\.venv\Scripts\python.exe' -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Se a API já estiver rodando nessa porta, mantenha a instância existente. Em outro terminal:

```powershell
Set-Location 'D:\FloodSystem'
& '.\frontend\start.ps1'
```

Abra **http://127.0.0.1:5173/**. O script procura o Node.js no PATH e, neste computador, pode usar o runtime local instalado pelo aplicativo Codex. Ele não altera o PATH permanentemente. O Vite usa uma porta fixa e não muda silenciosamente se ela estiver ocupada.

Se o frontend já estiver aberto na porta 5173, use o endereço existente. Para encerrar o servidor iniciado por você, pressione Ctrl+C no terminal correspondente. A API e o frontend são processos independentes e precisam permanecer em execução durante o desenvolvimento local. O build de produção é servido pelo Nginx na VM.

Se a política local bloquear scripts PowerShell, é possível iniciar diretamente o Vite usando o Node disponível neste computador:

```powershell
Set-Location 'D:\FloodSystem\frontend'
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" '.\node_modules\vite\bin\vite.js' --host 127.0.0.1
```

## Telas e filtros

**Tempo real** abre em `simulador-01` no desenvolvimento e `esp32-01` no build de produção. A tela consulta o intervalo recente até o horário da API, sem pedir uma data. Os gráficos e a tabela podem mostrar os **últimos 30 minutos** (padrão), **1 hora** ou **24 horas**. A intensidade usa sua própria janela de **1, 5, 10, 15, 30 ou 60 minutos** (padrão: 5), independente do intervalo dos gráficos. Por exemplo, gráficos de 30 minutos podem aparecer com intensidade dos últimos 5 minutos. Se a janela da intensidade ultrapassar o intervalo dos gráficos, o frontend faz uma segunda consulta de resumo à API para calculá-la corretamente; não altera a contagem dos gráficos.

O painel dos ensaios meteorológicos é iniciado separadamente em 5180 com `frontend/start-article.ps1`, usando a API científica 8010. Compara fonte e basculadas por hora, mostra residual e proveniência e exporta o cenário completo. Consulte [ensaios-meteorologicos.md](ensaios-meteorologicos.md).

O cartão de nível informa o horário em que a última leitura foi **medida** e, quando o registro está na página carregada, o horário em que foi **recebida pela API**. Se a última medição tiver mais de cinco minutos, aparece aviso de defasagem. A velocidade recente usa uma consulta separada à API para os **últimos cinco minutos**, com os horários reais das leituras, independentemente do intervalo dos gráficos; não é uma velocidade instantânea. Em Tempo real, o frontend consulta o relógio da API para definir o período recente, evitando excluir eventos quando o relógio do computador diverge do servidor. Verifica as pequenas rotas de última basculada e última leitura de nível a cada 2 segundos; se um novo registro foi gravado, refaz a consulta completa para atualizar indicadores, gráficos e registros. A consulta completa também se repete a cada 15 segundos. As consultas automáticas ocorrem com a aba visível e podem ser desligadas. Ao retornar à aba, o painel consulta imediatamente. **API conectada** não confirma que o ESP32 está ligado.

Ao lado do nível mais recente, um desenho do recipiente mostra a subida da água acima do volume que permanece quando a mangueira inferior para de drenar. Nessa condição, a leitura ultrassônica observada foi de 23,0 cm; ela define o H₀ operacional provisório e o nível zero. A saída inferior fica aproximadamente 1 cm acima da base interna, e o overflow a 20 cm da base: a escala provisória do desenho vai de 0 a 19 cm acima da água residual. O nível da API é H₀ menos a distância, e não a altura total desde a base. As medidas manuais de aproximadamente 5, 10 e 15 cm desde a base e a leitura próxima do overflow ainda têm incerteza; o valor pode ser refinado. A altura só muda quando a API devolve outro nível; a onda em movimento é apenas visual. Valores fora dessa faixa ficam limitados ao topo ou à base do desenho, mas o número em centímetros mantém o valor retornado pela API. Sem nível disponível, o desenho indica ausência de leitura. Após cinco minutos sem medição, ele fica esmaecido. Durante a atualização automática, o valor anterior permanece visível até a nova resposta chegar.

Os cenários existentes têm horários históricos fixos. Por isso, eles não aparecem como medições atuais em Tempo real. A tela pode mostrar estado vazio mesmo que existam dados de simulação no banco. Nenhum dado de demonstração é gerado no navegador.

**Histórico** permite escolher **ano, mês e dia** no controle de data. Ao abrir o site, a data sugerida é o dia atual do computador no horário de Brasília. A consulta usa `[00:00 do dia, 00:00 do dia seguinte)`, convertida para UTC antes de chamar a API. A tela mostra nível no fim do período, chuva acumulada e velocidade média entre as leituras extremas, além dos gráficos e eventos. Os registros já permanecem no mesmo SQLite com seus horários; não há cópia ou arquivamento à meia-noite.

No Histórico também há atalhos para os quatro cenários de simulação e **Intervalo personalizado** para execuções com outro início ou atraso. Os atalhos apenas consultam registros já gravados. Para ver o cenário padrão de chuva, escolha **Histórico → Simulação · chuva em 5 min**; a consulta começa automaticamente. Para consultar um dia inteiro com os exemplos existentes, selecione **08/10/2026**. Um dia pode conter mais de um cenário, e o resumo diário inclui todos os registros daquele dispositivo nesse dia.

O botão **Dispositivo** permite informar outro identificador previamente cadastrado na API. A seleção de intervalo, janela, modo histórico ou data aplica o filtro automaticamente. Ao digitar o identificador do dispositivo, o painel aguarda cerca de meio segundo após a última tecla antes de consultar; datas e horários personalizados também aguardam uma breve pausa. Combinações inválidas mostram uma mensagem e mantêm a consulta anterior até serem corrigidas. Horários personalizados são digitados em Brasília (`America/Sao_Paulo`, UTC−3); a API e o SQLite continuam usando UTC. O botão **Atualizar** refaz a consulta em qualquer tela.

## Indicadores e gráficos

| Elemento | Origem e interpretação |
| --- | --- |
| Nível da água | Último nível do intervalo consultado, retornado por `/api/v1/summary`, com horário da medição. No Tempo real, também mostra o horário de recebimento quando o registro correspondente está carregado. |
| Intensidade no Tempo real | Indicador calculado pelo backend na janela de chuva escolhida, encerrada no instante da consulta. A janela é independente do intervalo dos gráficos. |
| Chuva acumulada no Histórico | Soma do período escolhido, calculada pelo backend usando as calibrações associadas às basculadas. |
| Velocidade | No Tempo real, média entre os extremos dos últimos 5 minutos; no Histórico, entre os extremos do período escolhido. Usa cm/min e não classifica risco. |
| Evolução do nível | Níveis armazenados, posicionados pelos horários das medições. Pontos acessíveis por foco e mouse. Leituras sem nível ou com mudança de versão de calibração interrompem a linha. As linhas apenas conectam observações, sem criar registros intermediários. |
| Chuva acumulada | Valor calculado pelo backend para todo o período. |
| Gráfico de basculadas | Contagem dos eventos carregados em dez intervalos iguais, sem converter a contagem em milímetros no frontend. O detalhe de cada barra informa seu intervalo. |
| Registros | Leituras e basculadas em abas separadas, ordenadas das mais recentes para as mais antigas, com paginação local de sete registros. |

Um traço (`—`) representa indicador indisponível. O frontend traduz os motivos da API, como falta de H₀/K ou insuficiência de leituras. Não transforma `null` em zero. Zero basculadas continua sem comprovar chuva zero, conforme a regra da etapa 4.

O rótulo **Simulação** vem de `origin: simulation`, retornado pelo servidor, e aparece no aviso principal, nas linhas das tabelas e na exportação. Um identificador contendo a palavra simulador, por si só, não é usado como prova da origem.

## Carregamento, erros e atualização

O painel usa placeholders na primeira consulta e após a troca automática de filtros. Na atualização do mesmo filtro, mantém o último valor visível enquanto busca a resposta nova. Se houver erro de conexão, tempo limite, indisponibilidade do backend ou dispositivo inexistente, mostra uma mensagem e o botão **Tentar novamente**. Os valores da consulta anterior são retirados ao trocar filtros para não parecerem dados do novo dispositivo ou período.

As consultas anteriores são canceladas quando os filtros mudam ou o componente é desmontado. Cada requisição tem limite de 15 segundos. Os dados não ficam embutidos no código e não são lidos de um arquivo SQLite pelo navegador.

A indicação **API conectada** significa que a consulta foi concluída. Ela não comprova que o sensor físico está conectado ou que não houve perda de eventos. O MVP continua sem alarmes, previsão ou classificação de risco.

## Paginação e exportação

As listagens da API são percorridas em páginas de até mil itens. Há um limite de dez mil registros por tipo no navegador. Se ele for atingido, um aviso informa que gráficos, tabelas e CSV mostram somente os primeiros registros carregados. Os indicadores do resumo continuam se referindo a todo o período, pois são calculados no backend.

**Exportar dados** gera um CSV dos registros carregados com tipo, dispositivo, ID, horários, distância, nível, origem e versão de calibração. O nome do arquivo inclui a origem e a data. O arquivo usa separador `;` e UTF-8 com BOM para facilitar a abertura no Excel. Nenhum valor é enviado a um serviço externo na exportação.

As três consultas (resumo, leituras e basculadas) são independentes. Novos registros durante a navegação podem produzir diferenças transitórias de contagem. Para exportações de experimentos, prefira um intervalo histórico estabilizado. Não há promessa de uma transação única entre todos os endpoints.

## Comunicação com o backend

Todas as chamadas HTTP do navegador ficam em **`frontend/src/services/api.ts`**:

- `GET /api/v1/summary`;
- `GET /api/v1/level-readings`;
- `GET /api/v1/rain-tips`.

O servidor Vite encaminha `/api` para `http://127.0.0.1:8000`, mantendo as requisições na mesma origem do frontend. Isso evita precisar alterar o CORS do backend para o desenvolvimento local. O preview comum também usa a API local. Para ver dados do ESP32 enviados à VM no preview local, compile o frontend e execute `frontend/preview-production.ps1`; ele serve o build em `127.0.0.1:4173` e encaminha `/api` para `https://floodsystem.duckdns.org`. O site publicado já usa a API da VM sem esse script.

O modelo `frontend/.env.example` documenta:

- `API_PROXY_TARGET`: destino do proxy, utilizado pelo servidor Vite;
- `VITE_API_BASE_URL`: base HTTP opcional, incorporada ao bundle. O padrão vazio usa a mesma origem.

Se configurar outra origem diretamente em `VITE_API_BASE_URL`, essa API precisará permitir CORS. Variáveis prefixadas com `VITE_` são públicas no navegador; não coloque credenciais nelas. O proxy de desenvolvimento é separado do Nginx publicado na VM.

## Aba de ensaios meteorológicos

No frontend local integrado, a navegação inclui **Ensaios meteorológicos**. Inicie a API científica com `tools/start-article-api.ps1` e, em outro terminal, o site com `frontend/start-article.ps1`. Abra `http://127.0.0.1:5180/ensaios/`. O script liga a opção `VITE_EXPERIMENTS_ENABLED=true`; ela não faz parte do build publicado na VM.

Neste modo, Tempo real e Histórico usam `/api`, encaminhado à API publicada, e Ensaios usa `/article-api`, encaminhado à API científica local 8010. A aba identifica a fonte histórica, o período e a hipótese de distribuição uniforme; apresenta o balanço de chuva, a comparação horária selecionável, a tabela, a proveniência e a exportação completa em ZIP. Ela não apresenta um nível de água simulado. O caminho do modo científico e seus limites estão em [ensaios-meteorologicos.md](ensaios-meteorologicos.md).

## Arquivos principais

```text
frontend/
  package.json
  pnpm-lock.yaml
  index.html
  tsconfig.json
  vite.config.ts
  start.ps1
  .env.example
  public/favicon.svg
  src/
    main.tsx
    App.tsx
    styles.css
    types.ts
    format.ts
    components/Charts.tsx
    components/Records.tsx
    components/WaterTank.tsx
    services/api.ts
```

As fontes DM Sans são incluídas no pacote, sem depender de um serviço remoto para renderizar o painel. Os ícones vêm de `lucide-react`. O layout se adapta a telas menores, com menu lateral recolhido, cartões empilhados e rolagem horizontal nas tabelas.

## Instalar em outro ambiente e gerar o build

Com Node.js compatível com o Vite instalado e pnpm disponível:

```powershell
Set-Location 'D:\FloodSystem\frontend'
pnpm install --frozen-lockfile
pnpm run dev
```

Neste computador, se pnpm não estiver no PATH:

```powershell
Set-Location 'D:\FloodSystem\frontend'
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd" install --frozen-lockfile
```

Para compilar:

```powershell
pnpm run build
```

Esse comando verifica os tipos TypeScript e gera os arquivos estáticos em `frontend/dist`, ignorados pelo Git. `pnpm run preview` serve esse build localmente na porta 4173. A instalação desta entrega utilizou Node 24.19.0 e pnpm 11.25.0; as versões exatas de React, Vite e demais dependências estão no `package.json` e no lockfile.

Referências de configuração: [Vite — Getting Started](https://vite.dev/guide/) e [React — Build a React app from Scratch](https://react.dev/learn/build-a-react-app-from-scratch).

## Conferência desta entrega

Após a separação das telas, o build de produção e a verificação de tipos passaram. A validação integrada registrada na etapa 7 ocorreu antes desta reorganização visual; o script de validação foi ajustado para navegar por Histórico, mas não foi executado novamente naquela alteração. Na etapa 8, o build foi publicado em HTTPS na VM e a interface foi conferida no navegador com banco de produção vazio. Veja [validation-stage8.md](validation-stage8.md). O build publicado seleciona `esp32-01`, omite distância bruta e atalhos de cenários locais. A placa ainda precisa ser gravada para enviar ao servidor HTTPS.
