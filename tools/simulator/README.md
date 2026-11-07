# Simulador do FloodSystem

Cliente HTTP de dados **sintéticos**, exclusivo de `simulador-01`. Não abre o SQLite, não importa o backend e não calcula indicadores destinados à API. Envia distância e horário para `/api/v1/level-readings`, e eventos individuais em lotes para `/api/v1/rain-tips`, nos mesmos contratos previstos para o ESP32.

Manual completo, incluindo preparação, todos os cenários e consultas: [docs/simulator.md](../../docs/simulator.md).

## Menu interativo

No Windows, abra **`D:\FloodSystem\Simulador.cmd`** com dois cliques, ou execute na raiz:

```powershell
.\Simulador.cmd
```

Na seção **SIMULAÇÃO DE DADOS**, escolha 1 a 4 para enviar um cenário. Enter mantém o horário padrão. O cenário com atraso pergunta o número de segundos. O programa envia pela API e mostra um resumo com instruções para localizar os dados no site.

Na seção separada **SERVIÇOS LOCAIS**, use **5** para ligar a API, **6** para ligar o site, **7** para atualizar o status e **8** para abrir o site no navegador. O menu verifica as respostas HTTP antes de considerar um serviço ligado e não inicia outra cópia se a porta estiver ocupada. O site precisa da API para mostrar dados.

O mesmo menu pode ser aberto com `python -m tools.simulator menu` ou simplesmente `python -m tools.simulator`. As datas aparecem e são solicitadas no horário de Brasília (`America/Sao_Paulo`, normalmente UTC−3); ao digitar outro horário, use o fuso, por exemplo `2026-10-09T20:27:00-03:00`. Use `--dry-run` para uma prévia sem rede: nesse modo, as opções de serviços ficam desabilitadas. O dispositivo deve ser preparado explicitamente; o menu não escreve diretamente no banco nem cadastra calibrações. A API guarda e recebe os instantes em UTC.

A inicialização exige seleção explícita e ocorre em segundo plano. Fechar o menu mantém os serviços ligados. A API iniciada pelo menu usa o banco de desenvolvimento `database/development.db`; logs ficam em `.logs/api-menu.log` e `.logs/site-menu.log`. Com `--base-url` remoto ou porta diferente, o menu não tenta ligar essa API. O status e o site continuam referentes aos serviços locais nas portas 8000 e 5173.

## Comandos diretos

Na raiz `D:\FloodSystem`, após preparar o backend conforme o manual:

```powershell
& '.\.venv\Scripts\python.exe' -m tools.simulator sem-chuva
& '.\.venv\Scripts\python.exe' -m tools.simulator chuva-5min
& '.\.venv\Scripts\python.exe' -m tools.simulator sobe-desce
& '.\.venv\Scripts\python.exe' -m tools.simulator chuva-atraso --delay-seconds 120
```

Acrescente `--dry-run` para mostrar os pacotes sem acessar a API. `--start` aceita ISO 8601 com fuso; `--base-url` seleciona a API, com padrão `http://127.0.0.1:8000`. Só é necessário Python, sem dependências extras para o simulador.

O arquivo `simulation-profile.json` contém a calibração fictícia. Seus números **não são valores medidos no protótipo**. A preparação desse cadastro pertence ao comando administrativo do backend, nunca ao cliente simulador.
