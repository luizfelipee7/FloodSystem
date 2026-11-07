# Ideias futuras do FloodSystem

Este arquivo registra propostas e seu estado atual. A publicação na VM e a integração física permanecem separadas.

## Separar acompanhamento em tempo real e histórico diário

**Status:** divisão implementada no frontend local em 09/10/2026. A integração física com ESP32 permanece futura.

Organizar o site em duas áreas de navegação:

- **Tempo real:** acompanhar os dados recentes recebidos do ESP32, com atualização automática e identificação da última medição recebida.
- **Histórico:** escolher ano, mês e dia e consultar os gráficos, leituras e resumos daquele dia.

Na tela de histórico, a data atual pode ser sugerida pelo computador usando o horário de Brasília. A pessoa poderá selecionar outra data para consultar dias anteriores.

Os dados não precisam ser copiados ou consolidados em um arquivo à meia-noite. Cada leitura e basculada continua sendo gravada no SQLite quando chega à API, com seus timestamps. Para consultar um dia em Brasília, a aplicação monta o intervalo desde 00:00 desse dia até 00:00 do dia seguinte e converte os limites para UTC antes de consultar a API.

Se o dia não tiver registros, a interface informa que não há dados. Quando calibrações físicas estiverem ausentes, os registros brutos podem continuar visíveis; indicadores que dependem de H₀ ou K aparecem como indisponíveis.

### Pontos ainda necessários para uso físico

- Concluir e validar o envio contínuo do ESP32 para a API publicada.
- Confirmar que os relógios do ESP32 e do servidor produzem timestamps corretos; preservar UTC no banco e na API.
- Definir qual dispositivo será consultado e como a interface selecionará seus registros.
- Planejar retenção e capacidade do SQLite para o volume esperado de dados.
