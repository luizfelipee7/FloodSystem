# Pluviômetro físico: ESP32 → API → SQLite → painel

O sketch `firmware/esp32_pluviometro/esp32_pluviometro.ino` adapta o teste do KY-024. Ele mantém GPIO 27 para a saída digital do sensor e GPIO 25 para o buzzer, mas remove a página HTML hospedada pelo ESP32. Cada passagem do ímã aceita gera uma basculada com identificador e horário próprios. No teste local, o ESP32 envia por HTTP; para a VM, o mesmo firmware aceita HTTPS verificado com token. A API grava no SQLite e o painel consulta a API. O buzzer confirma **detecção local**, não gravação no banco.

O dispositivo usado é `esp32-01` e sua origem, cadastrada na API, é `esp32`. O K físico inicial foi estimado em 2,17 mm/basculada; veja [o ensaio](calibracao-pluviometro.md). O cadastro inicial era parcial, sem H₀. Posteriormente, o firmware incorporou o HC-SR04, leituras a cada 30 segundos e referência operacional H₀=23 cm. O nível calculado pela API depende da versão de calibração vinculada a cada leitura; o número provisório impresso no Serial não substitui esse cadastro. Os exemplos de preparação inicial abaixo preservam o contexto histórico.

**Se você vai virar a báscula com a mão**, use primeiro [o banco isolado de teste manual](teste-manual-esp32.md). As instruções de `development.db` abaixo destinam-se ao ambiente normal; viradas manuais nele seriam apresentadas como chuva física.

## 1. Preparar a API no computador

O ESP32 e o computador precisam estar na mesma rede local. A opção de iniciar API do `Simulador.cmd` a prende em `127.0.0.1` e não permite acesso do ESP32. Encerre essa instância antes de executar o comando abaixo; a porta 8000 deve estar livre. Em um PowerShell novo:

```powershell
Set-Location 'D:\FloodSystem'
$env:FLOODSYSTEM_ENV = 'development'
$env:FLOODSYSTEM_DB_PATH = 'database/development.db'
& '.\.venv\Scripts\python.exe' -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Mantenha esse terminal aberto. No navegador do computador, abra `http://127.0.0.1:8000/health` e `http://127.0.0.1:8000/api/v1/time`. A primeira rota deve indicar `status: ok` e `database: ok`; a segunda deve retornar um número `unix_ms`. Se a segunda não existir, reinicie a API para carregar o código novo. O Windows pode pedir autorização de firewall para a rede privada.

Confirme que o banco de desenvolvimento contém o cadastro `esp32-01` e a calibração física descrita acima. **Não** execute `prepare-simulator` para preparar o ESP32. Cadastros feitos em outro arquivo `.db` não aparecem nesta API.

## 2. Configurar o ESP32

Abra `firmware/esp32_pluviometro/esp32_pluviometro.ino` na Arduino IDE. O arquivo `config.h` ao lado do sketch contém Wi-Fi e URL da API: `FLOOD_WIFI_SSID`, `FLOOD_WIFI_PASSWORD` e `FLOOD_API_BASE_URL`. Se `config.h` não existir após copiar o projeto, copie `config.example.h` com o nome `config.h`. Para HTTPS, preencha também `FLOOD_DEVICE_TOKEN` e `FLOOD_TLS_CA_CERT` conforme [o guia da VM](seguranca-esp32-vm.md). Esse arquivo é ignorado pelo Git. Não publique nem envie a senha ou o token.

Descubra o endereço IPv4 do computador na rede com `ipconfig` no PowerShell. Por exemplo, se o computador tiver `192.168.1.50`, configure `FLOOD_API_BASE_URL` como `http://192.168.1.50:8000`. Substitua pelo seu endereço real. `127.0.0.1` no ESP32 aponta para o próprio ESP32 e não alcança o computador.

Selecione a placa e a porta corretas na Arduino IDE, grave o sketch e abra o Monitor Serial em **115200 baud**. O modelo da placa precisa ser confirmado antes da gravação; uma compilação para ESP32 genérico não confirma pinagem ou funcionamento da placa física. O sketch mantém a suposição do teste original: saída digital do KY-024 em GPIO 27, detecção em nível LOW e buzzer em GPIO 25. Ajuste `DETECTION_LEVEL` apenas se o sinal do seu módulo for invertido. O intervalo `DEBOUNCE_MS = 700` descarta novas bordas dentro de 700 ms após uma detecção; se basculadas reais ocorrerem mais rápido, esse valor precisará ser revisto com testes físicos.

## 3. Conferir uma basculada real

Depois que o Serial indicar Wi-Fi conectado e horário sincronizado, mova a báscula **uma vez**. Procure as mensagens de basculada guardada e, em seguida, confirmada pela API. Uma mensagem `Envio pendente` indica que o evento permanece na fila para nova tentativa. Cada evento usa `event_id` no formato `esp32-01-tip-N`, que permite à API reconhecer reenvios sem contar duas vezes.

No site local, abra **Tempo real** e informe `esp32-01` em **Dispositivo**. Após uma breve pausa na digitação, o filtro é aplicado automaticamente. O site verifica novas basculadas a cada 2 segundos com a aba visível e atualiza o painel quando a API confirma uma nova gravação; **Atualizar** consulta imediatamente. Se o evento estiver dentro do período recente selecionado, a chuva acumulada e a intensidade usarão K = 2,17 mm/basculada. Com apenas uma basculada, a chuva acumulada é aproximadamente 2,17 mm para o período que a inclui. Nível e velocidade permanecem indisponíveis enquanto não houver HC-SR04 e H₀.

Para conferir os registros por data, use **Histórico** e escolha o dia da basculada no horário de Brasília. Também é possível consultar `GET /api/v1/rain-tips` no Swagger em `http://127.0.0.1:8000/docs`, com `device_id=esp32-01`, `start` e `end` em UTC. O SQLite Viewer pode abrir `database/development.db`; a tabela de eventos é `rain_tip_events`. Não crie um banco novo ao abrir o visualizador.

## Horário, falta de rede e limites desta versão

- Ao conectar, o ESP32 consulta `GET /api/v1/time` e relaciona o relógio UTC da API com `millis()`. Assim, ele registra aproximadamente o instante de **cada detecção**, mesmo que envie depois. Enquanto a API roda no computador, a referência é o relógio desse computador; após a publicação, será o relógio da VM. A API registra separadamente o instante `received_at` ao gravar o evento. Os horários do site são apresentados em Brasília.
- Depois da primeira sincronização, eventos aguardando rede são guardados na flash do ESP32. A fila comporta até 64 eventos pendentes e os reenvia com os mesmos IDs. Se ela encher, novas detecções podem ser perdidas; confira as mensagens do Serial. Detecções anteriores à **primeira** sincronização ainda ficam apenas na memória temporária e podem ser perdidas se a placa reiniciar antes disso.
- O teste atual usa HTTP **sem token** na rede local. O firmware também suporta HTTPS com CA verificada e token próprio do dispositivo para a futura VM. A configuração e os modelos de publicação estão em [Comunicação segura do ESP32 com a VM](seguranca-esp32-vm.md). Isso ainda não foi ativado na VM.
- O ensaio de K tem incertezas de nivelamento e de escoamento pelo funil/mangueira. A intensidade em janelas curtas corresponde aos instantes das basculadas, que podem ocorrer depois da chuva captada. Não interprete os valores como calibração metrológica certificada.
