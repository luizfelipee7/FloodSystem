# Teste manual da báscula com ESP32

Virar a báscula com a mão verifica o caminho **KY-024 → ESP32 → API → SQLite → site**. Não mede precipitação real. A API não consegue distinguir a causa física da virada; por isso, os eventos manuais ficam em `database/manual-esp32-test.db`, separados do banco de desenvolvimento `database/development.db`. Ambos os arquivos são ignorados pelo Git.

## Estado preparado em 10/10/2026

- `database/manual-esp32-test.db` foi criado como ambiente `test`.
- O cadastro explícito `esp32-01`, origem `esp32`, e a calibração física parcial versão 1 foram adicionados **somente a esse banco de teste**: K = 2,17 mm/basculada, H₀ ausente, vigência iniciada em `2026-10-10T05:11:14Z`.
- Nenhuma basculada foi inserida durante a preparação. Na conferência inicial, tanto o banco de teste quanto o de desenvolvimento tinham zero eventos para `esp32-01`.
- A API local foi iniciada em `0.0.0.0:8000` apontando para o banco de teste. O log local fica em `.logs/manual-esp32-api-error.log` e `.logs/manual-esp32-api-out.log`.
- O firmware do ESP32 usa a mesma URL `http://192.168.15.3:8000`; a separação depende do banco selecionado **na API**, não de uma alteração na placa.

O site rotula esses registros como origem `esp32`, pois é a origem do dispositivo físico. **Não use os valores em mm desses ensaios como resultado real de chuva no artigo.** Cada basculada manual pode aparecer como 2,17 mm calculados pela calibração, mas nenhuma chuva foi medida.

## Verificação física passo a passo

1. Com o USB desconectado, confira KY-024 VCC → 3V3, GND → GND e saída DO → GPIO 27. AO pode ficar desconectado; o buzzer é opcional. Consulte [a integração do pluviômetro](esp32-pluviometro.md).
2. Reconecte o ESP32 e abra o Monitor Serial em 115200 baud. Sem mexer na báscula, espere aparecer `Wi-Fi conectado` e `Horario sincronizado com a API (UTC).`. Não devem surgir novas detecções ou avisos de fila cheia.
3. Vire a báscula **uma vez**. O Serial deve mostrar uma mensagem `Basculada N guardada para envio` e depois `Basculada N confirmada pela API`. Se houver mais de uma detecção por uma virada, interrompa o ensaio e investigue sensor, ímã, cabos e `DEBOUNCE_MS` antes de usar o resultado.
4. No site local, abra Tempo real e escolha `esp32-01` em Dispositivo. O filtro é aplicado automaticamente após uma breve pausa; **Atualizar** repete a consulta imediatamente. Para examinar eventos mais antigos, use Histórico na data da virada. O indicador de nível permanecerá indisponível: o HC-SR04 e H₀ ainda não foram integrados.
5. Confira o número de linhas de `rain_tip_events` no SQLite Viewer abrindo **somente** `database/manual-esp32-test.db`. O campo `occurred_at` é o horário estimado de detecção; `received_at` é quando a API gravou. Uma basculada aceita deve criar uma linha. O identificador de evento permite reenvio sem duplicação.

O som do buzzer confirma apenas a detecção local. A confirmação da API no Serial é a evidência de que ela recebeu e gravou aquele evento.

## Reiniciar este modo de teste no futuro

Se a API não estiver rodando, abra um PowerShell em `D:\FloodSystem` e execute:

```powershell
Set-Location 'D:\FloodSystem'
$env:FLOODSYSTEM_ENV = 'test'
$env:FLOODSYSTEM_DB_PATH = 'database/development.db'
$env:FLOODSYSTEM_TEST_DB_PATH = 'database/manual-esp32-test.db'
& '.\.venv\Scripts\python.exe' -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Mantenha esse terminal aberto. O arquivo de teste e os cadastros já existem; não execute `register-device` nem `add-calibration` novamente. A opção 5 do `Simulador.cmd` inicia a API de **desenvolvimento**, portanto não a use para este ensaio se a porta 8000 estiver livre.

Para confirmar que a API responde, abra `http://192.168.15.3:8000/health` no celular conectado ao mesmo roteador. Esse endereço IPv4 pode mudar; se isso ocorrer, atualize o `config.h` local do ESP32 e a regra de firewall restrita à rede local.

## Voltar ao banco de desenvolvimento

Desconecte o ESP32 para impedir o envio de basculadas manuais durante a troca. Encerre a API de teste: use Ctrl+C caso tenha iniciado no PowerShell, ou identifique o processo que escuta na porta 8000 antes de encerrá-lo. Depois inicie a API com:

```powershell
Set-Location 'D:\FloodSystem'
$env:FLOODSYSTEM_ENV = 'development'
$env:FLOODSYSTEM_DB_PATH = 'database/development.db'
Remove-Item Env:FLOODSYSTEM_TEST_DB_PATH -ErrorAction SilentlyContinue
& '.\.venv\Scripts\python.exe' -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Os registros manuais continuam no arquivo de teste e não aparecem no banco de desenvolvimento. Não copie eventos de teste para o banco de desenvolvimento ou produção.
