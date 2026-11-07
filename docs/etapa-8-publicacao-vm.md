# Roteiro da etapa 8 — publicação na VM

Este documento retoma o plano do FloodSystem. As etapas 1 a 7 estão concluídas no projeto local; a etapa 8 foi publicada no servidor em 12/10/2026 Brasília (13/10 UTC). O procedimento e os comandos estão em [publicacao-vm.md](publicacao-vm.md).

## Etapas do projeto

1. **Estrutura do projeto:** organizar pastas, README, instruções e `.gitignore`. — Concluída.
2. **Persistência:** criar o banco SQLite e salvar os registros. — Concluída.
3. **API:** receber e consultar leituras e basculadas pela API. — Concluída.
4. **Cálculos:** calcular nível, chuva, intensidade, velocidade e resumos usando os dados do SQLite. — Concluída.
5. **Simulador:** enviar cenários sintéticos pelas mesmas rotas HTTP da API. — Concluída.
6. **Frontend:** criar o painel React + TypeScript com Vite, consultando a API. — Concluída.
7. **Validação integrada:** verificar fluxo, cálculos, persistência, reenvios e estados da interface. — Concluída.
8. **Publicação na VM Ubuntu:** frontend/API com domínio, Nginx, HTTPS, SQLite persistente e backup. — Concluída no servidor; configuração física da placa pendente.

## Etapa 8 — situação atual

### Feito

- Criado o endereço DuckDNS `floodsystem.duckdns.org` e apontado para o IP público da VM.
- Adicionadas regras de entrada TCP para as portas 80 e 443 na Security List associada à sub-rede pública da VM. Não abrir a porta 8000 para a internet.
- Instalado e habilitado o Nginx na VM Ubuntu.
- Identificado o firewall local do Ubuntu: ele aceitava SSH na porta 22 e rejeitava as outras conexões de entrada.
- Liberadas as portas TCP 80 e 443 no firewall local e salvas as regras com `iptables-persistent`/`netfilter-persistent`, habilitando a restauração no boot.
- Confirmado no Windows que `Test-NetConnection floodsystem.duckdns.org -Port 80` retorna `TcpTestSucceeded: True`.
- Confirmado no navegador que `http://floodsystem.duckdns.org` abre a página padrão do Nginx.

### Também concluído na publicação

1. Código e build transferidos por pacote com lista explícita de arquivos; nenhuma chave ou banco local foi enviado.
2. Ambiente Python e SQLite de produção criados na VM, com diretório privado persistente.
3. Cadastro explícito de `esp32-01` e K físico 2,17; H₀ permanece desconhecido. Banco com zero telemetria.
4. Token gerado na VM e guardado em `/etc/floodsystem/api.env` protegido, sem exibição no chat.
5. API ativa e habilitada em systemd, escutando somente em `127.0.0.1:8000`.
6. Frontend compilado servido pelo Nginx e `/api/` encaminhado à API. Produção abre em `esp32-01`, sem coluna de distância bruta ou atalhos de simulação local.
7. HTTPS ativo; certificado inicial válido até 11/01/2027, timer de renovação habilitado e ensaio de renovação aprovado.
8. Backup diário, ensaio de restauração em arquivo separado e cópia local em `D:\FloodSystem\backups`, com hash conferido.
9. Reinício da API conferido com preservação de cadastro/calibração. Não foi necessário reiniciar a VM inteira.

O site está em **https://floodsystem.duckdns.org** e já substituiu a página padrão do Nginx. O ESP32 ainda precisa receber URL HTTPS, token privado e CA confiável por gravação do firmware. Esse passo físico e uma medição física na VM ainda não foram executados.

## Próximos passos após a publicação

1. Preparar a configuração privada do ESP32 para HTTPS e gravar a placa com a Arduino IDE.
2. Conferir uma medição física e a confirmação da API, sem confundir viradas manuais com chuva real.
3. Manter cópias periódicas dos backups fora da VM. O timer atual guarda snapshots no próprio disco da VM; a primeira cópia externa foi feita manualmente.

Cada operação que altera o estado da VM deve ser conferida antes de avançar. A API deve permanecer inacessível diretamente pela internet na porta 8000; o acesso público deve passar pelo Nginx em HTTPS.

## Prompt original da etapa 8

```text
Execute somente a etapa 8: prepare a publicação do FloodSystem na VM Ubuntu da Oracle Cloud.

Documente e configure, após conferir a aplicação:
- backend como serviço systemd;
- frontend compilado pelo Vite e servido pelo Nginx;
- encaminhamento das chamadas /api para o backend;
- caminho persistente para o arquivo SQLite;
- variáveis de ambiente sem segredos no repositório;
- procedimento de backup e restauração do SQLite;
- portas e regras de rede estritamente necessárias.

Não exponha o banco diretamente à internet. Não publique a chave SSH. Antes de aplicar qualquer mudança na VM, mostre os comandos e explique o que cada um fará.
```

## Referências do projeto

- `docs/seguranca-esp32-vm.md` — modelo de autenticação, HTTPS, Nginx, systemd e configuração do ESP32.
- `docs/api.md` — rotas e formato dos dados.
- `docs/sqlite.md` — esquema e comportamento do SQLite.
- `docs/calibracao-pluviometro.md` — calibração física estimada do pluviômetro.
- `docs/esp32-pluviometro.md` — integração física e envio local pelo ESP32.
