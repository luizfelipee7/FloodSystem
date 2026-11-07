# Calibração inicial do pluviômetro físico

## Resultado observado

Em 10/10/2026, o conjunto montado foi ensaiado com água pesada em balança de cozinha. Para água, usamos a aproximação de 1 g ≈ 1 mL.

| Água adicionada | Basculadas completas |
| ---: | ---: |
| 300 g | 13 |
| 300 g | 13 |
| 400 g | 18 |
| **Total** | **1.000 g / 44** |

A abertura de coleta foi medida como aproximadamente 115 × 116 mm. Tratando-a como uma elipse, a área estimada é 104,8 cm². O volume médio por basculada é 1.000 mL ÷ 44 ≈ 22,73 mL. Portanto:

`K = 10 × volume_por_basculada_mL ÷ área_cm²`

`K = 10 × 22,73 ÷ 104,8 ≈ 2,17 mm/basculada`

**K físico inicial: aproximadamente 2,17 mm por basculada.** É uma estimativa experimental do conjunto montado, não um valor de fabricante nem uma calibração metrológica certificada.

## Observações do ensaio

- A água dos ensaios informados passou pela mangueira e chegou à báscula; não ficou água no funil ao final e não houve derramamento.
- O funil quase encheu ao adicionar 400 g. O risco de derramamento depende da velocidade de entrada e da vazão de saída pela mangueira; 430 g não foi confirmado como limite seguro.
- O mecanismo não está perfeitamente nivelado. Em alguns ensaios de 400 g foram observadas 17 ou 18 basculadas, sendo 18 o resultado mais frequente. Isso reduz a precisão de K.
- A mangueira PU tem diâmetro interno de 4 mm. O armazenamento temporário no funil e o escoamento pela mangueira podem atrasar o instante em que cada basculada ocorre. O total continua válido se toda a água chegar à báscula; a intensidade em janelas curtas pode refletir esse atraso.
- A área de 104,8 cm² depende da aproximação elíptica da abertura. Se a borda não for aproximadamente elíptica, a área e K devem ser revistos.

## Uso no FloodSystem

Atualização de 18/10/2026: o usuário adotou H₀=23 cm como referência operacional do protótipo. A tabela abaixo documenta a versão 1 parcial, no momento do cadastro inicial; não descreve todas as versões posteriores. A primeira integração meteorológica usa K=2,17/H₀=23 em dispositivos virtuais exclusivos e banco separado, com origem `simulation`; consulte [ensaios-meteorologicos.md](ensaios-meteorologicos.md). O perfil antigo `simulador-01` permanece com K=0,2/H₀=30.

Este K foi cadastrado somente para o dispositivo físico do pluviômetro/ESP32. A calibração não altera `tools/simulator/simulation-profile.json` nem se aplica a `simulador-01`. É parcial: H₀ permanece desconhecido e não foi preenchido com este ensaio.

| Banco | Dispositivo | Origem | Versão | Vigência | H₀ | K |
| --- | --- | --- | ---: | --- | ---: | ---: |
| `database/development.db` | `esp32-01` | `esp32` | 1 | 10/10/2026 02:11:14, horário de Brasília | não cadastrado | 2,17 mm/basculada |
| VM: `/srv/floodsystem/database/production.db` | `esp32-01` | `esp32` | 1 | 10/10/2026 02:11:14, horário de Brasília | não cadastrado | 2,17 mm/basculada |

O cadastro local foi explícito, usando `register-device` e depois `add-calibration`, que registra K e mantém o histórico imutável. Na publicação de 12/10/2026 Brasília, `deploy.initialize_production` cadastrou explicitamente o mesmo dispositivo e a calibração na VM, sem transferir telemetria local. A rotina verifica a calibração existente antes de adicionar, evitando repetir a versão em reexecuções. Não execute novamente `add-calibration` para a mesma implantação: cada execução cria uma nova versão.
