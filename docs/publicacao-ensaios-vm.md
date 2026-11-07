# Ensaios meteorológicos na VM

Publicação concluída em 18/10/2026. A aba está em <https://floodsystem.duckdns.org/ensaios/>. O exemplo publicado contém um ensaio de janeiro de 2025, com 14,50 mm da fonte Open-Meteo/ERA5, 6 basculadas simuladas e 1,48 mm residuais. A simulação de nível ainda não foi implementada.

## Separação dos dados

| Componente | Monitoramento físico | Ensaios meteorológicos |
| --- | --- | --- |
| Caminho público | `/api` | `/article-api` (somente GET/HEAD) |
| Processo local | `floodsystem-api`, `127.0.0.1:8000` | `floodsystem-article-api`, `127.0.0.1:8010` |
| Banco | `/srv/floodsystem/database/production.db` | `/srv/floodsystem/article-data/article-simulations.db` |
| Identificação | `esp32-01` | dispositivo virtual `sim-artigo-…` |

O serviço científico é executado como `floodarticle`, tem apenas as rotas de catálogo, detalhe e exportação, e recebe leitura do arquivo SQLite. O Nginx aceita só consultas em `/article-api/v1/experiments`. O serviço físico e o seu arquivo de ambiente não foram substituídos. Não há regra de rede pública para 8000, 8010 ou SQLite.

O modo científico usa `FLOODSYSTEM_ENV=development` porque a configuração da aplicação recusa ensaios em `production`; na VM ele roda em **serviço exclusivo**, sem rotas de gravação e com o SQLite sem permissão de escrita. Isso não altera `FLOODSYSTEM_ENV=production` da API física.

## Arquivos locais de implantação

- `backend/app/article_public.py`: entrada da API de leitura.
- `deploy/systemd/floodsystem-article-api.service`: unidade isolada.
- `deploy/nginx/floodsystem.conf`: roteamento público.
- `deploy/package_article.py`: pacote explícito do código, build e snapshot consistente do SQLite, sem credenciais.
- `deploy/verify_article_db.py` e `deploy/install-article-vm.sh`: verificação e instalação.

O pacote foi gerado em `D:\FloodSystem\.deploy\floodsystem-article-20261018T232054Z.tar.gz` e copiado para `/home/ubuntu/floodsystem-article.tar.gz`. A extração ficou em `/home/ubuntu/floodsystem-article-stage`. O instalador confere hashes, integridade e chaves estrangeiras do SQLite antes de publicar. Se já houver um banco científico diferente na VM, ele recusa substituí-lo.

Antes de qualquer nova alteração na VM, mostrar ao usuário os comandos e explicar seus efeitos, conforme `AGENTS.md`.

## Verificação operacional

```bash
sudo systemctl is-active floodsystem-api floodsystem-article-api nginx
sudo ss -lntp | grep -E ':(8000|8010|443)'
curl --fail https://floodsystem.duckdns.org/health
curl --fail https://floodsystem.duckdns.org/article-api/v1/experiments/status
curl --fail https://floodsystem.duckdns.org/article-api/v1/experiments
```

Na implantação, os três serviços estavam ativos; 8000 e 8010 ouviam apenas em `127.0.0.1`; `/ensaios/`, catálogo e exportação responderam HTTP 200; uma tentativa POST na rota científica retornou HTTP 403. O navegador mostrou o balanço de 14,50 = 13,02 + 1,48 mm e 72 horas no exemplo.

## Cópia e restauração do banco científico

O banco científico publicado é uma fotografia de leitura. O arquivo compactado local e a extração preservam essa fotografia. Antes de qualquer atualização dos ensaios, guarde também uma cópia fora da VM. O backup diário do banco físico **não inclui** este SQLite.

Para obter uma cópia adicional na VM, com nome definido pelo operador:

```bash
sudo install -d -o root -g root -m 0700 /var/backups/floodsystem/article
sudo install -o root -g root -m 0600 /srv/floodsystem/article-data/article-simulations.db /var/backups/floodsystem/article/COLOQUE-UM-NOME.db
```

Para restaurar uma cópia escolhida, após conferir o arquivo e com o serviço científico parado:

```bash
sudo systemctl stop floodsystem-article-api
sudo python3 /home/ubuntu/floodsystem-article-stage/deploy/verify_article_db.py /var/backups/floodsystem/article/COLOQUE-UM-NOME.db
sudo install -o root -g floodarticle -m 0640 /var/backups/floodsystem/article/COLOQUE-UM-NOME.db /srv/floodsystem/article-data/article-simulations.db
sudo systemctl start floodsystem-article-api
curl --fail http://127.0.0.1:8010/health
```

O instalador preservou a versão anterior do site em `/srv/floodsystem/frontend/dist.before-article-20261018T232444Z-105191` e a configuração anterior do Nginx em `/etc/nginx/sites-available/floodsystem.before-article-20261018T232444Z-105191`. Uma reversão deve restaurar **ambos** e testar `nginx -t` antes de recarregar o Nginx. Não apagar nem substituir o banco físico nessa operação.

Para atualizar o conjunto de ensaios futuramente, prepare e confira um novo snapshot local. O instalador atual interrompe a publicação se o banco na VM for diferente; uma atualização de dados exige procedimento explícito de backup, comparação e troca do SQLite científico, preservando a proveniência e sem alterar `production.db`.
