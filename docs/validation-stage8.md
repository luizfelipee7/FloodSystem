# Conferência da publicação — etapa 8

Execução em 12/10/2026 Brasília / 13/10/2026 UTC. Domínio: https://floodsystem.duckdns.org. As alterações na VM foram apresentadas com os comandos e suas finalidades antes de aplicar.

## Resultado

- Build Vite e verificação TypeScript: aprovados.
- Suíte Python: **37 testes aprovados**, usando bancos temporários. Inclui autenticação HTTPS/token, reenvio sem duplicação e backup/restauração com transações no WAL.
- O teste antigo de rotas foi atualizado para incluir `/api/v1/time`, que já existia para o ESP32.
- Serviços `floodsystem-api`, Nginx e timers de backup/Certbot configurados. API vinculada exclusivamente a `127.0.0.1:8000`.
- SQLite de produção em `/srv/floodsystem/database/production.db`, proprietário floodsystem, arquivo 0600 e diretório 0700. Ambiente privado root:floodsystem 0640 em `/etc/floodsystem/api.env`.
- Certificado HTTPS válido, emitido com o e-mail de contato informado pelo usuário, válido inicialmente até 11/01/2027. `certbot renew --dry-run --no-random-sleep-on-renew`: sucesso. Hook de recarga do Nginx instalado.
- `GET /`: 200 e aplicação React carregada.
- `GET /health`: 200, `status=ok`, `database=ok`.
- `GET /api/v1/time` e resumo para `esp32-01`: 200 via proxy HTTPS.
- POST sem token para dispositivo propositalmente não cadastrado: 401, sem inserção. O envio aceito com token foi validado nos testes isolados, não com telemetria fictícia na produção.
- Tentativas HTTP a `/.env`, `/database/production.db` e `/PrivateKey/test.key`: negadas por 403/404, sem ler chaves reais.
- Portas 8000 e 111: inacessíveis em conexão externa do computador. SSH e HTTP/HTTPS são as portas TCP permitidas pelo firewall IPv4. Não há endereço IPv6 global atribuído à VM nesta conferência; revisar também as regras IPv6 antes de habilitar conectividade IPv6 pública.
- Navegador em HTTPS: “API conectada”, `esp32-01` selecionado, estados vazios corretos e coluna de distância bruta ausente. Atalhos de cenários locais removidos do build de produção; mantidos em desenvolvimento.

## Backup e persistência

- Backup inicial: `/var/backups/floodsystem/production-20261013T022834734511Z.db`.
- Restauração testada em `/var/backups/floodsystem/ensaio-restaurado-stage8.db`, sem substituir o banco ativo.
- Integridade e chaves estrangeiras aprovadas; original e cópia têm 1 dispositivo, 1 calibração, 0 leituras e 0 basculadas.
- Cópia externa salva em `D:\FloodSystem\backups\production-20261013T022834734511Z.db`.
- SHA-256 igual na VM e no computador: `8c6624d1a47e88523f17fed60727e2ded2b838a121ead140abaf6e64a122c780`.
- Timer diário habilitado para 06:00 UTC (03:00 Brasília), com até 5 minutos de variação. A primeira execução manual concluiu com sucesso.
- API reiniciada com systemd; `/health` respondeu e o cadastro/calibração permaneceu. A VM inteira não foi reiniciada nesta entrega.
- Sintaxe dos scripts shell e unidades systemd conferida. A troca do banco ativo por `restore-production.sh` é um procedimento de manutenção documentado; não foi executada sobre produção durante a publicação.

## Pendências físicas e operação contínua

O firmware que está na placa não foi alterado. Falta configurar e gravar o ESP32 com URL HTTPS, token privado e certificado de CA confiável e confirmar uma medição física chegando à VM. H₀ físico ainda não existe; nível/velocidade continuarão indisponíveis sem ele e sem leituras.

O timer copia no disco da VM. A cópia fora da VM foi manual; manter essa rotina ou definir futuramente um destino externo de backup autorizado. Snapshots não são apagados automaticamente; acompanhar espaço em disco.

Procedimentos completos: [publicacao-vm.md](publicacao-vm.md). Captura local: `D:\FloodSystem\frontend\.preview\etapa8-publicado.png`.
