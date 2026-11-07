# FloodSystem

Sistema experimental de monitoramento de chuva e nível da água com ESP32, pluviômetro de báscula, sensor ultrassônico HC-SR04, API FastAPI, SQLite e painel React/TypeScript. Este repositório reúne o código do protótipo, o simulador e a documentação técnica.

O painel público está em [floodsystem.duckdns.org](https://floodsystem.duckdns.org/). A interface também apresenta ensaios meteorológicos computacionais em `/ensaios/`, separados da telemetria do dispositivo físico.

## Escopo e limites

O ESP32 envia basculadas e leituras de distância para a API; o backend persiste os dados e calcula os indicadores exibidos no painel. O protótipo não foi validado como detector de alagamento residencial nem como sistema de previsão temporal. Os parâmetros físicos H₀ = 23 cm e K ≈ 2,17 mm por basculada são referências operacionais preliminares, não calibração metrológica certificada. Os cenários meteorológicos utilizam dados externos e geram eventos simulados, identificados e armazenados separadamente.

## Estrutura

- `backend/`: API, persistência SQLite, cálculos e testes.
- `frontend/`: painel React com TypeScript e Vite.
- `firmware/`: programa do ESP32 e teste do HC-SR04.
- `tools/simulator/`: cenários sintéticos enviados pela API.
- `tools/weather_simulator/`: importação e conversão de chuva histórica em basculadas simuladas.
- `deploy/`: modelos de configuração para Nginx, systemd e backup da VM.
- `docs/`: arquitetura, operação, cálculos e limites dos ensaios.

## Execução local

Requisitos: Python 3.12, Node.js e pnpm. A partir da raiz do projeto, no PowerShell:

```powershell
python -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r backend/requirements.txt
& '.\.venv\Scripts\python.exe' -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Em outro terminal:

```powershell
Set-Location frontend
pnpm install --frozen-lockfile
pnpm run dev
```

A API local responde em `http://127.0.0.1:8000/health` e o painel em `http://127.0.0.1:5173/`. O banco local inicia vazio; dispositivos e calibrações devem ser cadastrados explicitamente. Consulte [a documentação da API](docs/api.md), [o manual do frontend](docs/frontend.md) e [o simulador](docs/simulator.md) antes de enviar dados.

Para o ESP32, copie `firmware/esp32_pluviometro/config.example.h` para `config.h` e preencha a cópia local. O arquivo real `config.h` é ignorado pelo Git. Consulte [o manual do firmware](docs/esp32-pluviometro.md) para ligações e cuidados elétricos.

## Ensaios científicos

A [documentação dos ensaios meteorológicos](docs/ensaios-meteorologicos.md) descreve fonte, modelo, período, resolução temporal, parâmetro K, residual entre horas e identificação dos eventos simulados. O banco científico é separado da telemetria física. Os dados originais e artefatos gerados não estão incluídos neste repositório; a documentação explica como obtê-los ou reconstruí-los e como distinguir os resultados da simulação de medições físicas.

## Publicação e arquivos privados

O [manual de publicação](docs/publicacao-vm.md) descreve a arquitetura Nginx → API em loopback, os serviços systemd e os procedimentos de backup e restauração. Os arquivos em `deploy/` são modelos; a configuração efetiva da VM e seus dados não são versionados aqui.

O repositório exclui chaves SSH, credenciais, `config.h`, arquivos `.env` reais, bancos SQLite, artefatos gerados, ambientes virtuais, dependências instaladas e documentos de submissão que contenham dados pessoais. Para trabalhar em outro computador, clone o repositório, reinstale as dependências e restaure os arquivos privados somente a partir de backup seguro.
