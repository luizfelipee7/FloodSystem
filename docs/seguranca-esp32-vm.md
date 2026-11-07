# Comunicação segura do ESP32 com a VM

Autenticação de escrita e HTTPS estão ativos na VM em **https://floodsystem.duckdns.org**, desde 12/10/2026 Brasília (13/10 UTC). O servidor foi publicado conforme [publicacao-vm.md](publicacao-vm.md). O firmware tem suporte a HTTPS, mas a gravação da placa com a URL, token privado e CA ainda está pendente. O teste local por HTTP continua separado.

## O que muda

- `POST /api/v1/rain-tips` e `POST /api/v1/level-readings` exigem `Authorization: Bearer <token>` quando `FLOODSYSTEM_REQUIRE_DEVICE_AUTH=true`. Em `FLOODSYSTEM_ENV=production`, a exigência é automática e não pode ser desligada pela variável.
- Em produção, o backend também recusa POSTs cujo esquema recebido do proxy não seja HTTPS. O Nginx recebe TLS; o Uvicorn aceita cabeçalhos de proxy apenas de `127.0.0.1`.
- O token configurado para `esp32-01` só autoriza esse `device_id`. Tokens exclusivos por dispositivo são comparados sem expor o valor no erro. Falta de token ou token incorreto retorna HTTP 401 sem gravar telemetria.
- `GET /api/v1/time`, consultas, `/health` e o painel continuam públicos nesta fase; não há autenticação de usuário. Não publique dados sensíveis nessas rotas.
- O ESP32 aceita HTTPS somente com uma CA confiável configurada em `config.h`; ele não desativa a validação do certificado. A URL deve corresponder ao nome ou IP coberto pelo certificado. Antes da primeira chamada HTTPS, a placa obtém hora UTC via NTP para validar a vigência do certificado. Depois, sincroniza o horário dos eventos com `/api/v1/time` como antes.
- Se a API ou a rede falhar, a fila local e os IDs de basculada continuam a permitir reenvio sem duplicação. HTTP local só funciona sem token; o firmware recusa enviar credenciais em texto claro.

## Configuração privada no servidor

O caminho recomendado é usar um nome de host apontado para o IP público da VM, inclusive um subdomínio gratuito de DNS dinâmico, e emitir um certificado TLS válido para esse nome. Não é obrigatório comprar um domínio. A Let's Encrypt também emite certificados para IP público, mas eles duram aproximadamente seis dias e exigem renovação automática mais frequente; os modelos deste projeto foram preparados para um nome de host. Gere um token aleatório de **pelo menos 32 caracteres** para `esp32-01`. Gere e guarde o valor fora do Git; não o coloque em comandos ou capturas compartilhadas. O arquivo privado `/etc/floodsystem/api.env` deve ficar legível apenas pelo administrador e pelo serviço, e seguir este formato (substitua todos os marcadores):

```ini
FLOODSYSTEM_ENV=production
FLOODSYSTEM_DB_PATH=/srv/floodsystem/database/production.db
FLOODSYSTEM_DEVICE_TOKENS_JSON='{"esp32-01":"TOKEN_ALEATORIO_DE_PELO_MENOS_32_CARACTERES"}'
```

O formato JSON permite adicionar outro dispositivo com token diferente. Em produção, a API recusa iniciar se não houver token configurado. Não reutilize o token para `simulador-01`. O cadastro físico e a calibração K precisam ser preparados no banco de produção separadamente; o banco local não é copiado automaticamente.

O modelo `deploy/systemd/floodsystem-api.service.example` mantém o Uvicorn em `127.0.0.1:8000`, inacessível diretamente pela internet. O modelo `deploy/nginx/floodsystem.conf.example` serve o site em HTTPS e encaminha `/api/` ao Uvicorn. Substitua `DOMAIN.example`, obtenha o certificado para esse domínio e ajuste os caminhos/usuário do serviço antes de ativar esses arquivos. Libere externamente apenas 80/443; não exponha 8000. Renove o certificado antes de vencer.

## Configuração privada no ESP32

Atualize e grave `firmware/esp32_pluviometro/config.h` na Arduino IDE após a VM estar pronta:

```cpp
#define FLOOD_WIFI_SSID "NOME_DA_REDE"
#define FLOOD_WIFI_PASSWORD "SENHA_DA_REDE"
#define FLOOD_API_BASE_URL "https://DOMAIN.example"
#define FLOOD_DEVICE_TOKEN "MESMO_TOKEN_PRIVADO_DO_SERVIDOR"
#define FLOOD_TLS_CA_CERT R"CERT(-----BEGIN CERTIFICATE-----
CERTIFICADO_DA_CA_CONFIAVEL_EM_PEM
-----END CERTIFICATE-----)CERT"
```

O `config.h` é ignorado pelo Git. Configure o certificado **da CA confiável que assina o certificado do domínio**, não uma chave privada. A cadeia e o domínio precisam corresponder ao certificado servido pelo Nginx. A placa precisa alcançar um servidor NTP na rede; se o Serial ficar aguardando horário NTP, resolva a conectividade antes de testar o HTTPS. Nunca use `setInsecure()`.

Ao usar o ponto de acesso do celular, altere SSID e senha em `config.h` e grave novamente. Se a API estiver na VM com domínio fixo, a URL não depende do IP local do computador. O computador usado para abrir o site pode estar em outra rede; o ESP32 e o navegador precisam de acesso à internet.

## Conferência antes de publicar

1. Confirme que o domínio responde em HTTPS com certificado válido e que a API só escuta em `127.0.0.1:8000` na VM.
2. Com autenticação habilitada em um ambiente isolado, faça um POST sem token e confirme HTTP 401; com token de outro dispositivo, confirme HTTP 401; com o token correto, confirme a gravação. Não use o banco de produção para ensaios destrutivos.
3. Grave o ESP32 com URL, CA e token privados. No Serial, confirme Wi-Fi, sincronização de horário e `Basculada ... confirmada pela API` ao mover uma vez a báscula. Erro de certificado, NTP ou HTTP 401 deixa o evento pendente para reenvio.
4. Confira no site o evento de `esp32-01` e seu horário; se reenviar o mesmo ID, ele não pode aparecer duas vezes.

O servidor público já está ativo. Foram verificados HTTPS, rejeição de escrita sem token, consulta de dados, backup/restauração em cópia e reinício da API. O fluxo ESP32 físico → VM ainda não foi validado. O fluxo local em `http://192.168.x.x:8000` permanece restrito à rede de testes.

Referências: [Duck DNS: DNS dinâmico gratuito](https://www.duckdns.org/) e [Let's Encrypt: certificados para IP com duração curta](https://letsencrypt.org/2026/03/11/shorter-certs-certbot/).
