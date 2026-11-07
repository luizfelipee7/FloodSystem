# Validação integrada — etapa 7

Em 09/10/2026, o fluxo **simulador → API → SQLite → API → frontend** foi validado no computador local. A execução usou `FLOODSYSTEM_ENV=test`, um arquivo SQLite criado em pasta temporária, portas locais livres e o dispositivo `simulador-01`. Nenhum registro foi inserido no banco de desenvolvimento ou de produção. O teste encerra os processos que inicia e descarta o banco temporário ao terminar. **Essa execução antecedeu a posterior separação visual entre Tempo real e Histórico.** O script de navegação foi atualizado para a nova interface, mas ainda não foi executado após a mudança.

## Repetir a validação

Na raiz `D:\FloodSystem`, execute:

```powershell
& '.\.venv\Scripts\python.exe' -m unittest discover -s backend/tests -v
& 'C:\Users\Usuario\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd' --dir frontend run build
& '.\.venv\Scripts\python.exe' backend/tests/validate_stage7.py
```

O último comando usa Chrome e Playwright instalados neste computador para conferir o frontend em navegador. Para repetir em outro ambiente, ajuste os caminhos de Node, Playwright e Chrome em `backend/tests/validate_stage7.py`. O teste do fluxo usa apenas a calibração **sintética** do perfil `tools/simulator/simulation-profile.json` (H₀=30 cm, K=0,2 mm/basculada), que não representa o protótipo físico.

## Resultado observado

| Verificação | Resultado |
| --- | --- |
| Suíte existente do backend | 34 testes passaram. |
| Build do frontend | TypeScript e Vite concluíram sem erro. |
| Cenário de chuva em 5 min enviado por HTTP | 6 leituras novas e 10 basculadas novas; cada basculada foi consultada com ID próprio e origem `simulation`. |
| Nível | H₀ 30 cm − distância bruta 20 cm = 10 cm. |
| Chuva acumulada e intensidade | 10 × K 0,2 mm = 2 mm; em 5 min = 24 mm/h. |
| Velocidade | O período estável usou 299 s entre extremos e retornou 0 cm/min. Em outro cenário, subida de 10 cm em 300 s retornou +2 cm/min e descida de 10 cm em 300 s retornou −2 cm/min. |
| Sem calibração | Distância bruta 17,9 cm e basculada sintéticas foram salvas. Nível, chuva acumulada e intensidade ficaram indisponíveis; com uma única leitura, velocidade também ficou indisponível. |
| Período vazio | Sem registros, as métricas dependentes retornaram indisponíveis; o sistema não tratou a falta de eventos como comprovação de chuva zero. |
| Campos inválidos | Distância negativa e horário sem fuso retornaram HTTP 422. A suíte existente também cobre lote inválido, conflitos e limites. |
| Reenvio | Mesmo cenário retornou 6 leituras e 10 eventos como duplicados, sem novos registros. Reenvio de leitura individual retornou HTTP 200. |
| Reinício da API | Após encerrar e iniciar novamente sobre o mesmo SQLite temporário, leituras, eventos e resumo continuaram idênticos. |
| Interface na versão validada | Navegador mostrou aviso de dados sintéticos, nível 10 cm, chuva 2 mm, intensidade 24 mm/h e 10 basculadas. Ao consultar período vazio, mostrou estado vazio sem preencher métricas. Dispositivo inexistente e API desligada produziram estado de erro. A tela foi reorganizada depois desta execução. |

O teste integrado está em `backend/tests/validate_stage7.py`; o teste do navegador está em `frontend/tests/validate_stage7.cjs`. Os testes reproduzem horários históricos de simulação sem aguardar cinco minutos em tempo real. A publicação na VM e a medição/calibração física continuam fora desta etapa.
