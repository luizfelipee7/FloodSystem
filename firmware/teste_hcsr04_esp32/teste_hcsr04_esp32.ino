/*
  Teste basico do HC-SR04 com ESP32, sem Wi-Fi.
  Monitor Serial: 115200 baud.

  VCC: alimentacao de 5 V confirmada; GND: comum ao ESP32.
  TRIG: GPIO26 (D26).
  ECHO: resistor de 1 kohm ate GPIO32 (D32).
  Outro resistor, de 2 kohm, liga GPIO32 ao GND.
  Nao conecte o ECHO de 5 V diretamente ao ESP32.

  Mede distancia ate o alvo, sem calibracao de nivel ou leitura do KY-024.
  Salve seu programa atual antes de carregar este teste no ESP32.
*/

#include <Arduino.h>

const int PINO_TRIG = 26;
const int PINO_ECHO = 32;
const unsigned long TEMPO_LIMITE_US = 30000UL;

void setup() {
  Serial.begin(115200);

  pinMode(PINO_TRIG, OUTPUT);
  pinMode(PINO_ECHO, INPUT);
  digitalWrite(PINO_TRIG, LOW);

  delay(1000);
  Serial.println("Teste HC-SR04 iniciado.");
}

void loop() {
  // Envia o pulso que inicia a medicao.
  digitalWrite(PINO_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PINO_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PINO_TRIG, LOW);

  // Mede o tempo do ECHO, em microssegundos.
  unsigned long duracao = pulseIn(PINO_ECHO, HIGH, TEMPO_LIMITE_US);

  if (duracao == 0) {
    Serial.println("Leitura invalida: sem eco completo em 30 ms.");
  } else {
    // Conversao aproximada indicada no datasheet: us / 58 = cm.
    float distanciaCm = duracao / 58.0f;

    if (distanciaCm < 2.0f || distanciaCm > 400.0f) {
      Serial.println("Leitura invalida: fora da faixa nominal de 2 a 400 cm.");
    } else {
      Serial.print("Distancia: ");
      Serial.print(distanciaCm, 1);
      Serial.println(" cm");
    }
  }

  delay(3000);  // Pausa de 3 segundos entre as medicoes.
}

