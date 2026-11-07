# Instruções do projeto FloodSystem

## Base principal

O diretório ativo do projeto é `D:\FloodSystem`, escolhido pelo usuário em 06/10/2026. Execute comandos e crie ou altere arquivos nessa base. A pasta anterior em `C:\Users\Usuario\Documento\FloodSystem` é apenas um backup da transferência e não deve receber desenvolvimento novo. O diretório de trabalho inicial da conversa pode apontar para outra pasta; defina explicitamente `D:\FloodSystem` como diretório de trabalho ao operar no projeto.

## Escopo e organização

Este é um TCC de Engenharia da Computação para monitorar chuva, nível da água e velocidade de subida/descida. O hardware previsto é ESP32, pluviômetro de báscula e HC-SR04.

Trabalhe somente na etapa solicitada pelo usuário. Preserve arquivos existentes, examine a estrutura antes de editar e atualize o README quando uma etapa for efetivamente concluída. Ao encerrar, explique as alterações, como conferi-las e o que permanece pendente.

As etapas 1 a 7 estão concluídas: pastas, SQLite, API, cálculos, simulador, frontend React + TypeScript com Vite e validação integrada. A etapa 8 foi publicada no servidor em 12/10/2026 Brasília (13/10 UTC): https://floodsystem.duckdns.org, API systemd em loopback, frontend Nginx, HTTPS e backup diário. Consulte `docs/publicacao-vm.md` e `docs/etapa-8-publicacao-vm.md`, além dos manuais anteriores. O usuário posteriormente confirmou envios do ESP32 com HTTPS/token/CA e registros no painel da VM; isso confirma integração, não calibração metrológica. Antes de qualquer alteração na VM, mostrar os comandos ao usuário e explicar seus efeitos, conforme solicitação vigente.

O ambiente local está em `.venv`; no Windows, use `.venv\Scripts\python.exe`. Dependências estão em `backend/requirements.txt` e `backend/requirements-dev.txt`. A API exige dispositivo cadastrado explicitamente via comando local `python -m backend.app.manage register-device`. Não cadastrar dispositivos nem calibrações automaticamente na inicialização. As consultas HTTP usam intervalos [start, end), UTC e paginação. Conflitos em lotes de basculadas devem desfazer todas as novas inserções do lote.

O comando administrativo `python -m backend.app.manage prepare-simulator` prepara exclusivamente simulador-01 e sua calibração sintética versão 1, lendo `tools/simulator/simulation-profile.json`. É explícito, idempotente para o mesmo perfil e recusa conflitos sem alterar o histórico. Não executá-lo automaticamente. O cliente `python -m tools.simulator` usa apenas HTTP, com IDs determinísticos e `--dry-run` sem rede. Horários padrão dos quatro cenários ficam separados; alterações de parâmetros devem usar períodos distintos. Nunca reutilizar a calibração sintética no dispositivo físico.

O simulador também possui menu em `tools/simulator/interactive.py`, aberto por `Simulador.cmd` na raiz ou `python -m tools.simulator menu` (padrão quando não há cenário). Preserve os comandos diretos existentes. O menu usa o mesmo gerador e cliente HTTP; não deve escrever diretamente no SQLite nem preparar cadastros. A pedido do usuário, as opções explícitas 5/6 iniciam API/site locais em segundo plano via `local_services.py`; 7 atualiza status, 8 abre o navegador e 9 executa a validação da etapa 7 em banco temporário isolado. Detectar serviços por respostas HTTP e impedir nova inicialização em portas ocupadas. A API iniciada pelo menu usa development e database/development.db; logs em .logs/*.log. Fechar o menu não encerra os servidores. Nunca iniciá-los automaticamente ao abrir o menu ou escolher cenário. --dry-run permanece sem rede, sem validação e sem inicialização de processos. A tela do menu é limpa antes de mostrar uma ação e ao retornar, preservando a saída da ação até o usuário pressionar Enter.

O frontend está em `frontend/`, usa pnpm com lockfile e pode ser iniciado por `frontend/start.ps1`. As chamadas HTTP ficam exclusivamente em `frontend/src/services/api.ts`; nenhuma ligação com SQLite. Vite local em 5173 encaminha `/api` para 8000. O preview comum em 4173 também usa a API local; `frontend/preview-production.ps1` encaminha o preview à API publicada da VM. No desenvolvimento, o painel abre em Tempo real para `simulador-01`, inicialmente sem dados recentes; no build de produção abre em `esp32-01`, sem distância bruta ou atalhos de cenários locais; os cenários antigos estão em Histórico. Tempo real usa intervalos de 30 minutos, 1 hora ou 24 horas para gráficos, janela independente de 1 a 60 minutos para intensidade e consulta separada dos últimos 5 minutos para velocidade. Histórico aceita um dia completo de Brasília (00:00 até 00:00 do dia seguinte), cenários padrão ou intervalo personalizado. A data inicial vem do relógio do computador em Brasília. O site identifica origem retornada pela API, mostra horários em America/Sao_Paulo e nunca inventa dados. Filtros personalizados são digitados em Brasília e convertidos para UTC; backend e SQLite permanecem UTC. O período de Tempo real usa o relógio da API, verifica novas basculadas e leituras de nível a cada 2 segundos e faz uma consulta completa a cada 15 segundos enquanto a aba está visível; API conectada não prova sensor conectado. Build: `pnpm run build`. A pasta `frontend/.preview/` guarda capturas locais ignoradas pelo Git.

## Decisões vigentes

- Ensaios meteorológicos do artigo implementados e publicados em 18/10/2026: leia `docs/ensaios-meteorologicos.md` e `docs/publicacao-ensaios-vm.md`. O ambiente local usa `database/article-simulations.db`, API 8010 e frontend 5180. Na VM, o site oferece `/ensaios/`, com `/article-api` encaminhado à API científica de leitura em loopback 8010 e SQLite separado em `/srv/floodsystem/article-data/article-simulations.db`; `/api` continua no backend físico 8000. O modo científico exige `FLOODSYSTEM_ENABLE_ARTICLE_SIMULATIONS=true`, ambiente `development` e banco separado dos caminhos padrão; a VM usa um serviço isolado com somente rotas de leitura e arquivo SQLite sem permissão de escrita para esse serviço. Não misturar com `simulador-01` nem com o ESP32 físico.
- A primeira entrega usa snapshots imutáveis Open-Meteo/ERA5, chuva líquida horária, H₀=23 cm, K=2,17 mm/basculada, distribuição uniforme por hora e residual contínuo. Gera somente basculadas; o modelo do nível e a integração ANA continuam pendentes. Não inventar nível para preencher o painel.
- `python -m backend.app.manage prepare-weather-experiment --snapshot ...` prepara explicitamente fonte, dispositivo virtual, calibração e ledger; `python -m tools.weather_simulator send --snapshot ...` envia somente por HTTP. IDs determinísticos, limites de 31 dias/100 mil eventos, lotes até 500 e `--dry-run` sem rede. Exportação científica completa em ZIP pelo backend; fonte, método e eventos devem permanecer distinguíveis.

- Backend Python com FastAPI, banco SQLite, frontend React + TypeScript/TSX com Vite.
- SQLite é a escolha atual do usuário, substituindo a proposta inicial de Oracle Database. A Oracle Cloud hospeda a VM Ubuntu.
- O simulador e, posteriormente, o ESP32 enviam dados pela mesma API. O frontend consulta essa API; nenhum desses clientes acessa diretamente o banco.
- Os dados simulados são gravados no SQLite e identificados como simulação. Desenvolvimento, testes e produção usam bancos separados.
- Dados brutos são preservados. O backend é responsável pelos cálculos apresentados na aplicação.
- Não implementar notificações, classificação de risco ou autenticação de usuário sem solicitação. Requisitos de proteção da API deverão ser definidos antes da exposição pública.

## Dados e validade científica

- Preservar cada basculada com identificador e horário; não é necessário guardar o lado do tombamento.
- Preservar a distância consolidada em centímetros e o nível calculado quando houver calibração. O firmware atual programa uma leitura de nível a cada 30 segundos; recebimento depende de conectividade e fila.
- Usar timestamps UTC, distinguindo o instante de medição do instante de recebimento.
- Prever reenvios sem duplicar eventos e leituras.
- H₀=23 cm é a referência operacional fixa adotada pelo usuário para o protótipo, acima da água residual; não é uma certificação metrológica. K do pluviômetro físico foi estimado em aproximadamente 2,17 mm/basculada em 10/10/2026 e cadastrado como versão 1 de `esp32-01` no banco de desenvolvimento; é uma estimativa do conjunto montado, com leve inclinação observada e variação de 17/18 viradas em alguns ensaios de 400 g. Ver `docs/calibracao-pluviometro.md`. Não associar este K a `simulador-01`; novos ensaios do artigo usam perfil e dispositivo virtual próprios. Calibrações devem permitir rastrear a versão utilizada. A calibração física versão 1 também foi cadastrada explicitamente no SQLite de produção da VM durante a etapa 8; nenhum evento local foi transferido. O registro inicial sem H₀ continua sendo histórico; não alterar retroativamente calibrações ou medições antigas.
- Calcular nível como H₀ menos distância; chuva acumulada como N × K; intensidade como N × K × 60/T; velocidade com o intervalo real entre medições. A janela inicial de chuva é de cinco minutos.
- Sem calibração ou dados suficientes, guardar os dados brutos e informar indisponibilidade dos indicadores dependentes.
- O resumo preserva a calibração vinculada ao registro. K variável exige somar as contribuições por versão; mudança de H₀ impede velocidade/variação. Sem eventos não há comprovação de chuva zero, pois ainda não existe confirmação de cobertura. A intensidade usa a janela terminada em end e exige que ela caiba no período solicitado. Ver `docs/calculations.md`.
- Não inferir uma relação fixa entre intensidade da chuva e elevação do nível. Limiares de risco e de subida rápida dependem dos experimentos.

## Arquivos privados

Nunca ler, exibir, copiar, enviar ou versionar o conteúdo de `PrivateKey/` ou chaves privadas. Não incluir segredos em código, documentação ou arquivos de exemplo. Respeitar o `.gitignore` e não sobrescrever arquivos locais de configuração ou bancos existentes.

## Validação

Executar verificações relevantes ao trabalho solicitado e registrar os resultados; não declarar como concluídas implementações ou validações que ainda não ocorreram. A suíte de persistência e API usa arquivos SQLite temporários e pode ser executada com `& '.\.venv\Scripts\python.exe' -m unittest discover -s backend/tests -v` na raiz (PowerShell). Nunca usar o banco de desenvolvimento ou produção como alvo de testes destrutivos. Não inserir dados sintéticos nem calibrações de exemplo nos bancos reais por padrão.
