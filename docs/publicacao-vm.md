# Publicação e operação do FloodSystem na VM Ubuntu

Este guia corresponde à etapa 8. A execução usa o projeto local `D:\FloodSystem`, a VM `vm-tcc` e o domínio `floodsystem.duckdns.org`. O banco da VM é independente dos bancos locais. A chave SSH é usada pelo cliente SSH para autenticar; seu conteúdo não é copiado para o servidor nem incluído no pacote.

Publicação realizada em 12/10/2026 Brasília (13/10 UTC). Veja os resultados e limites da conferência em [validation-stage8.md](validation-stage8.md). O certificado foi cadastrado com o e-mail fornecido pelo usuário; o exemplo sem e-mail abaixo é apenas uma alternativa documentada.

## Arquitetura e caminhos

```text
ESP32 e navegador → HTTPS :443 → Nginx
                                 ├─ / → frontend/dist (Vite)
                                 ├─ /api/ → 127.0.0.1:8000 → API física → production.db
                                 └─ /article-api/ → 127.0.0.1:8010 → API científica de leitura → article-simulations.db
```

| Caminho na VM | Uso e permissões |
| --- | --- |
| `/srv/floodsystem/backend` | Código da API, pertencente a root; serviço sem permissão de edição. |
| `/srv/floodsystem/.venv` | Ambiente Python da API. |
| `/srv/floodsystem/frontend/dist` | Única raiz pública de arquivos no Nginx. |
| `/srv/floodsystem/database/production.db` | Banco persistente; arquivo 0600 e diretório 0700, usuário floodsystem. |
| `/srv/floodsystem/article-data/article-simulations.db` | Banco científico separado; root:floodarticle, 0640, leitura pelo serviço científico. |
| `/etc/floodsystem/api.env` | Ambiente de produção, root:floodsystem, 0640. Contém token privado. |
| `/etc/systemd/system/floodsystem-api.service` | Inicialização automática e reinício da API em caso de falha. |
| `/etc/systemd/system/floodsystem-article-api.service` | API científica isolada, somente rotas de consulta, em loopback 8010. |
| `/etc/nginx/sites-available/floodsystem` | Site e encaminhamento da API. |
| `/var/backups/floodsystem` | Snapshots SQLite, diretório 0700 e arquivos 0600. |
| `/var/www/letsencrypt` | Desafios HTTP-01 de emissão/renovação do certificado. |

O caminho SQLite é absoluto, fora da pasta pública. Atualizar código ou frontend não deve substituir esse diretório nem o arquivo de ambiente. Apenas `esp32-01` é cadastrado nesta publicação, com K aproximado de 2,17 mm/basculada, vigência física já registrada em 10/10/2026 05:11:14 UTC e H₀ desconhecido. Nenhuma leitura nem basculada é criada no banco de produção durante a instalação.

A aba [Ensaios meteorológicos](https://floodsystem.duckdns.org/ensaios/) foi acrescentada em 18/10/2026. Ela consulta outro processo e outro SQLite, sem transferir eventos simulados ao banco físico. Procedimento e verificações em [publicacao-ensaios-vm.md](publicacao-ensaios-vm.md).

## Preparação local e transferência

No PowerShell em `D:\FloodSystem`, a suíte usa bancos temporários; o build gera os arquivos estáticos do site:

```powershell
& '.\.venv\Scripts\python.exe' -m unittest discover -s backend/tests -v
Set-Location 'D:\FloodSystem\frontend'
$env:VITE_API_BASE_URL = ''
pnpm run build
Set-Location 'D:\FloodSystem'
& '.\.venv\Scripts\python.exe' deploy/package.py
```

`deploy/package.py` empacota somente fontes Python da aplicação, dependências, migração SQL, scripts de publicação e o frontend compilado. Nunca percorre `PrivateKey`, arquivos privados do firmware ou bancos SQLite. O resultado `.deploy/floodsystem-stage8.tar.gz` é ignorado pelo Git. O frontend usa `/api` na mesma origem e não contém tokens. O build de produção abre com `esp32-01` e omite a coluna de distância bruta; o desenvolvimento local mantém essa coluna.

Use `scp -i CAMINHO_LOCAL_DA_CHAVE .deploy/floodsystem-stage8.tar.gz ubuntu@168.75.66.112:/home/ubuntu/floodsystem-stage8.tar.gz` para enviar somente o pacote. Nunca use `scp` da raiz inteira do projeto. Preserve a validação de identidade do servidor no SSH.

## Instalação na VM

Antes de cada execução, conferir e explicar o script e os comandos. Os comandos abaixo criam a pasta de preparação, extraem o pacote e executam a instalação como administrador:

```bash
mkdir -p /home/ubuntu/floodsystem-stage8
tar -xzf /home/ubuntu/floodsystem-stage8.tar.gz -C /home/ubuntu/floodsystem-stage8
sudo bash /home/ubuntu/floodsystem-stage8/deploy/prepare-vm.sh
```

O script `deploy/prepare-vm.sh` instala Python/venv, Nginx, Certbot e persistência de firewall; cria o usuário sem login `floodsystem`; instala os arquivos; cria o ambiente privado apenas se não existir; inicializa o banco e o cadastro físico explicitamente; instala e habilita os serviços. Em reexecuções, faz backup do banco existente, preserva ambiente/token e recusa divergência na calibração inicial. O cadastro não acontece na inicialização comum da API.

O token é gerado com `secrets.token_urlsafe(48)` diretamente na VM. O script não o imprime. As variáveis documentadas em `deploy/api.env.example` são `FLOODSYSTEM_ENV=production`, `FLOODSYSTEM_DB_PATH` e `FLOODSYSTEM_DEVICE_TOKENS_JSON`. Nunca copie o valor real para documentação ou comandos compartilhados. `VITE_*` é público: não coloque segredos nessas variáveis.

## HTTPS

Primeiro o Nginx usa a configuração HTTP de preparação: ela atende o desafio ACME e retorna 503 para outras rotas. Depois da emissão, ativar o arquivo HTTPS. Sem e-mail de contato, o comando é:

```bash
sudo certbot certonly --webroot -w /var/www/letsencrypt -d floodsystem.duckdns.org --non-interactive --agree-tos --register-unsafely-without-email
sudo install -m 0644 /srv/floodsystem/deploy/nginx/floodsystem.conf /etc/nginx/sites-available/floodsystem
sudo nginx -t
sudo systemctl reload nginx
```

Se houver e-mail escolhido pelo usuário, substituir `--register-unsafely-without-email` por `--email EMAIL`. O primeiro comando solicita certificado ao Let's Encrypt; o segundo instala a configuração; os dois últimos conferem a sintaxe e recarregam o Nginx. A porta 80 passa a redirecionar para HTTPS, mantendo o desafio de renovação.

Instalar um hook em `/etc/letsencrypt/renewal-hooks/deploy/floodsystem-nginx` que execute `nginx -t && systemctl reload nginx` após uma renovação bem-sucedida. Habilitar `certbot.timer` e validar com `sudo certbot renew --dry-run`.

O Nginx encaminha `/api/` preservando a rota e informando o esquema HTTPS. O Uvicorn só confia em cabeçalhos de proxy de `127.0.0.1`. Escritas exigem token do dispositivo; consultas e `/health` são públicas. Não há autenticação de usuários do painel nesta etapa.

## Portas e rede

| Porta | Acesso necessário |
| --- | --- |
| TCP 22 | Administração SSH por chave. Preferir origem limitada ao IP público do administrador, considerando que IP residencial pode mudar. |
| TCP 80 | Desafio ACME e redirecionamento para HTTPS. |
| TCP 443 | Site e API pública por HTTPS. |
| TCP 8000 | Somente loopback na VM; não criar regra pública OCI. |
| SQLite | Arquivo local; não há porta de banco para expor. |

As portas 80/443 já foram adicionadas à Default Security List ligada à sub-rede pública. O Ubuntu também possui firewall iptables, mesmo sem UFW. Preservar regras OCI de metadados e acesso SSH ao ajustar o firewall. O SSH permanece por chave; eventual restrição de origem deve ser conferida em nova conexão antes de encerrar a sessão corrente.

## Backup diário e manual

O timer executa diariamente às 06:00 UTC (03:00 de Brasília), com até cinco minutos de atraso aleatório. `Persistent=true` permite recuperar uma execução perdida após desligamento. O backup usa a API de snapshot do SQLite; não é uma cópia ingênua do arquivo em uso. Depois verifica integridade, chaves estrangeiras e versão de esquema. O arquivo só é publicado após essas verificações. Não há exclusão automática de snapshots nesta primeira versão; acompanhar espaço em disco e arquivar os antigos fora da VM.

```bash
# Criar um backup agora:
sudo systemctl start floodsystem-backup.service
# Conferir agenda e resultado:
systemctl list-timers floodsystem-backup.timer
sudo journalctl -u floodsystem-backup.service -n 20 --no-pager
sudo ls -lh /var/backups/floodsystem
```

Os backups nessa pasta protegem contra alterações acidentais, mas ficam no mesmo disco do banco. Mantenha também cópia fora da VM. Para retirar um snapshot, use `sudo install -o ubuntu -g ubuntu -m 0600 /var/backups/floodsystem/NOME.db /home/ubuntu/floodsystem-backup.db`, baixe esse arquivo via SCP para uma pasta privada local (por exemplo `D:\FloodSystem\backups`) e depois remova somente a cópia temporária de `/home/ubuntu`. Não publique o arquivo no Nginx ou em um repositório.

## Restauração

Primeiro faça um ensaio em arquivo novo, sem tocar no banco em uso:

```bash
sudo python3 /srv/floodsystem/deploy/sqlite_backup.py verify /var/backups/floodsystem/NOME.db
sudo python3 /srv/floodsystem/deploy/sqlite_backup.py restore /var/backups/floodsystem/NOME.db /var/backups/floodsystem/ensaio-restaurado.db
```

Escolha nomes reais e um destino ainda inexistente. O comando recusa sobrescrever arquivos, inclusive o banco ativo.

Para substituir o banco de produção, em manutenção anunciada e após escolher o snapshot correto:

```bash
sudo bash /srv/floodsystem/deploy/restore-production.sh /var/backups/floodsystem/NOME.db --confirm-replace
```

O script valida e prepara a cópia, para a API, faz um backup do estado atual, move banco anterior e eventuais arquivos WAL/SHM/journal para uma pasta `before-restore-*`, coloca o snapshot escolhido no lugar e reinicia a API. Restauração volta ao estado do snapshot: eventos posteriores não aparecem nele. O estado anterior é preservado para recuperação. Não iniciar outros escritores ou comandos administrativos durante esse procedimento.

## Operação e conferência

```bash
systemctl is-active floodsystem-api nginx
systemctl is-enabled floodsystem-api floodsystem-backup.timer certbot.timer
sudo ss -lntp
curl --fail https://floodsystem.duckdns.org/health
sudo journalctl -u floodsystem-api -n 50 --no-pager
```

O painel deve abrir em HTTPS e mostrar ausência de dados até receber telemetria física. Sem H₀, o nível continua indisponível. Um teste manual da báscula não representa chuva real; mantenha os ensaios manuais no banco local isolado já documentado em `teste-manual-esp32.md`.

O ESP32 precisa ser gravado posteriormente com domínio HTTPS, token privado e CA confiável. A publicação do servidor não altera automaticamente o firmware que está na placa. Não copiar o token para o chat e não desativar a validação do certificado.

Fontes técnicas: [SQLite Online Backup API](https://sqlite.org/backup.html) e [Certbot: uso e renovação](https://eff-certbot.readthedocs.io/en/stable/using.html).
