#include <Arduino.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <stdlib.h>
#include <time.h>

#include "config.h"

// Existing local config.h files can keep their original three settings.
#ifndef FLOOD_DEVICE_TOKEN
#define FLOOD_DEVICE_TOKEN ""
#endif
#ifndef FLOOD_TLS_CA_CERT
#define FLOOD_TLS_CA_CERT ""
#endif

// KY-024 DO -> GPIO 27; buzzer -> GPIO 25, as in the original prototype.
constexpr uint8_t SENSOR_PIN = 27;
constexpr uint8_t BUZZER_PIN = 25;
constexpr uint8_t DETECTION_LEVEL = LOW;
// HC-SR04: TRIG -> GPIO 26; ECHO -> GPIO 32 through a 1k/2k voltage divider.
constexpr uint8_t LEVEL_TRIG_PIN = 26;
constexpr uint8_t LEVEL_ECHO_PIN = 32;
// PROVISIONAL: echo distance at the retained-water level after the lower
// hose stops draining, in cm. Level is the rise above this reference.
// Replace after the final level calibration. The API calibration must match this
// value before water_level_cm is calculated and displayed by the site.
constexpr float PROVISIONAL_H0_CM = 23.0f;
constexpr uint32_t LEVEL_INTERVAL_MS = 30000;
constexpr uint32_t LEVEL_SEND_RETRY_MS = 5000;
constexpr uint32_t LEVEL_ECHO_TIMEOUT_US = 30000UL;
constexpr uint8_t LEVEL_SAMPLE_COUNT = 5;
constexpr uint32_t DEBOUNCE_MS = 700;
constexpr uint32_t WIFI_RETRY_MS = 10000;
constexpr uint32_t TIME_RETRY_MS = 10000;
constexpr uint32_t TIME_REFRESH_MS = 300000;
constexpr uint32_t SEND_RETRY_MS = 5000;
constexpr uint32_t SEND_NEXT_MS = 250;
constexpr uint8_t RAW_QUEUE_SLOTS = 32;
constexpr uint8_t STORED_QUEUE_SLOTS = 64;

const char *DEVICE_ID = "esp32-01";

struct StoredTip {
  uint64_t sequence;
  int64_t occurredUnixMs;
};

struct StoredLevelReading {
  uint64_t sequence;
  int64_t measuredUnixMs;
  float distanceCm;
};

Preferences preferences;
portMUX_TYPE tipMux = portMUX_INITIALIZER_UNLOCKED;
volatile uint32_t rawTimes[RAW_QUEUE_SLOTS];
volatile uint8_t rawRead = 0;
volatile uint8_t rawWrite = 0;
volatile uint32_t lastEdgeMs = 0;
volatile bool hasLastEdge = false;
volatile uint32_t detectedCount = 0;
volatile uint32_t overflowCount = 0;

uint64_t lastSequence = 0;
uint32_t lastBuzzerCount = 0;
uint32_t buzzerOffAt = 0;
uint32_t lastWifiAttempt = 0;
uint32_t lastTimeAttempt = 0;
uint32_t lastTimeSuccess = 0;
uint32_t lastSendAttempt = 0;
uint32_t sendIntervalMs = SEND_RETRY_MS;
uint32_t lastOverflowReport = 0;
uint32_t lastLevelCapture = 0;
uint32_t lastLevelSendAttempt = 0;
bool buzzerOn = false;
bool clockReady = false;
bool wifiWasConnected = false;
int64_t clockAnchorUnixMs = 0;
uint32_t clockAnchorMillis = 0;

void IRAM_ATTR onTipEdge() {
  const uint32_t now = millis();
  portENTER_CRITICAL_ISR(&tipMux);
  if (!hasLastEdge || static_cast<uint32_t>(now - lastEdgeMs) >= DEBOUNCE_MS) {
    hasLastEdge = true;
    lastEdgeMs = now;
    const uint8_t next = (rawWrite + 1) % RAW_QUEUE_SLOTS;
    if (next == rawRead) {
      overflowCount++;
    } else {
      rawTimes[rawWrite] = now;
      rawWrite = next;
      detectedCount++;
    }
  }
  portEXIT_CRITICAL_ISR(&tipMux);
}

bool peekRaw(uint32_t &detectedAt) {
  portENTER_CRITICAL(&tipMux);
  const bool available = rawRead != rawWrite;
  if (available) detectedAt = rawTimes[rawRead];
  portEXIT_CRITICAL(&tipMux);
  return available;
}

void discardRaw() {
  portENTER_CRITICAL(&tipMux);
  if (rawRead != rawWrite) rawRead = (rawRead + 1) % RAW_QUEUE_SLOTS;
  portEXIT_CRITICAL(&tipMux);
}

void slotKey(uint8_t slot, char *key, size_t length) {
  snprintf(key, length, "e%02u", static_cast<unsigned>(slot));
}

bool findFreeSlot(uint8_t &slot) {
  char key[8];
  for (uint8_t i = 0; i < STORED_QUEUE_SLOTS; i++) {
    slotKey(i, key, sizeof(key));
    if (!preferences.isKey(key)) {
      slot = i;
      return true;
    }
  }
  return false;
}

bool readSlot(uint8_t slot, StoredTip &tip) {
  char key[8];
  slotKey(slot, key, sizeof(key));
  if (!preferences.isKey(key)) return false;
  if (preferences.getBytesLength(key) != sizeof(StoredTip)) {
    Serial.printf("Registro flash invalido no slot %u.\n", static_cast<unsigned>(slot));
    return false;
  }
  return preferences.getBytes(key, &tip, sizeof(StoredTip)) == sizeof(StoredTip);
}

bool oldestStoredTip(uint8_t &slot, StoredTip &tip) {
  bool found = false;
  StoredTip candidate;
  for (uint8_t i = 0; i < STORED_QUEUE_SLOTS; i++) {
    if (readSlot(i, candidate) && (!found || candidate.sequence < tip.sequence)) {
      found = true;
      slot = i;
      tip = candidate;
    }
  }
  return found;
}

bool parseServerTime(const String &body, int64_t &unixMs) {
  const int name = body.indexOf("\"unix_ms\"");
  if (name < 0) return false;
  const int colon = body.indexOf(':', name);
  if (colon < 0) return false;
  const char *value = body.c_str() + colon + 1;
  while (*value == ' ' || *value == '\t') value++;
  char *end = nullptr;
  const long long parsed = strtoll(value, &end, 10);
  if (end == value || parsed < 1700000000000LL) return false;
  unixMs = static_cast<int64_t>(parsed);
  return true;
}

String apiUrl(const char *path) {
  String base(FLOOD_API_BASE_URL);
  while (base.endsWith("/")) base.remove(base.length() - 1);
  return base + path;
}

bool apiUsesTls() {
  return String(FLOOD_API_BASE_URL).startsWith("https://");
}

bool beginApiRequest(HTTPClient &http, WiFiClient &plainClient,
                     WiFiClientSecure &secureClient, const char *path) {
  if (apiUsesTls()) {
    secureClient.setCACert(FLOOD_TLS_CA_CERT);
    return http.begin(secureClient, apiUrl(path));
  }
  return http.begin(plainClient, apiUrl(path));
}

bool syncClock() {
  // TLS certificate validation needs a plausible UTC clock before the first API call.
  if (apiUsesTls() && time(nullptr) < 1700000000) {
    Serial.println("Aguardando horario NTP para validar certificado HTTPS.");
    return false;
  }
  WiFiClient plainClient;
  WiFiClientSecure secureClient;
  HTTPClient http;
  const uint32_t before = millis();
  if (!beginApiRequest(http, plainClient, secureClient, "/api/v1/time")) return false;
  http.setTimeout(3500);
  const int code = http.GET();
  const String body = code == 200 ? http.getString() : String();
  const uint32_t after = millis();
  http.end();

  int64_t serverUnixMs = 0;
  if (code != 200 || !parseServerTime(body, serverUnixMs)) {
    Serial.printf("Horario da API indisponivel (HTTP %d).\n", code);
    return false;
  }
  clockAnchorUnixMs = serverUnixMs;
  clockAnchorMillis = before + static_cast<uint32_t>(after - before) / 2;
  clockReady = true;
  lastTimeSuccess = after;
  Serial.println("Horario sincronizado com a API (UTC).");
  return true;
}

int64_t eventUnixMs(uint32_t detectedAt) {
  // Signed subtraction also handles tips detected just before the first sync.
  const int32_t elapsedMs = static_cast<int32_t>(detectedAt - clockAnchorMillis);
  return clockAnchorUnixMs + elapsedMs;
}

bool storeTip(uint32_t detectedAt) {
  uint8_t slot = 0;
  if (!findFreeSlot(slot)) return false;
  if (lastSequence == UINT64_MAX) return false;

  const uint64_t sequence = lastSequence + 1;
  // Reserve the ID before storing the event. A restart may skip an ID, never reuse it.
  if (preferences.putULong64("lastseq", sequence) != sizeof(sequence)) return false;
  lastSequence = sequence;

  const StoredTip tip{sequence, eventUnixMs(detectedAt)};
  char key[8];
  slotKey(slot, key, sizeof(key));
  if (preferences.putBytes(key, &tip, sizeof(tip)) != sizeof(tip)) return false;

  Serial.printf("Basculada %llu guardada para envio.\n",
                static_cast<unsigned long long>(sequence));
  return true;
}

void persistDetectedTips() {
  if (!clockReady) return;
  uint32_t detectedAt = 0;
  while (peekRaw(detectedAt)) {
    if (!storeTip(detectedAt)) {
      if (static_cast<uint32_t>(millis() - lastOverflowReport) >= 5000) {
        Serial.println("Fila flash cheia ou indisponivel; aguarde a API voltar.");
        lastOverflowReport = millis();
      }
      return;
    }
    discardRaw();
  }
}

bool formatUtc(int64_t unixMs, char *buffer, size_t length) {
  if (unixMs < 0) return false;
  const time_t seconds = static_cast<time_t>(unixMs / 1000);
  const unsigned milliseconds = static_cast<unsigned>(unixMs % 1000);
  struct tm utc;
  if (gmtime_r(&seconds, &utc) == nullptr) return false;
  const int written = snprintf(buffer, length, "%04d-%02d-%02dT%02d:%02d:%02d.%03uZ",
                               utc.tm_year + 1900, utc.tm_mon + 1, utc.tm_mday,
                               utc.tm_hour, utc.tm_min, utc.tm_sec, milliseconds);
  return written > 0 && static_cast<size_t>(written) < length;
}

bool sendOldestTip() {
  uint8_t slot = 0;
  StoredTip tip;
  if (!oldestStoredTip(slot, tip)) return false;

  char eventId[64];
  snprintf(eventId, sizeof(eventId), "%s-tip-%llu", DEVICE_ID,
           static_cast<unsigned long long>(tip.sequence));
  char occurredAt[32];
  if (!formatUtc(tip.occurredUnixMs, occurredAt, sizeof(occurredAt))) {
    Serial.println("Horario de basculada invalido; evento mantido na fila.");
    return false;
  }

  String payload = String("{\"device_id\":\"") + DEVICE_ID +
                   "\",\"events\":[{\"event_id\":\"" + eventId +
                   "\",\"occurred_at\":\"" + occurredAt + "\"}]}";

  WiFiClient plainClient;
  WiFiClientSecure secureClient;
  HTTPClient http;
  if (!beginApiRequest(http, plainClient, secureClient, "/api/v1/rain-tips")) return false;
  http.setTimeout(3500);
  http.addHeader("Content-Type", "application/json");
  if (strlen(FLOOD_DEVICE_TOKEN) > 0) {
    http.addHeader("Authorization", String("Bearer ") + FLOOD_DEVICE_TOKEN);
  }
  const int code = http.POST(payload);
  const String body = code == 200 ? http.getString() : String();
  http.end();

  if (code == 200 && body.indexOf("\"results\"") >= 0 &&
      body.indexOf(eventId) >= 0) {
    char key[8];
    slotKey(slot, key, sizeof(key));
    if (preferences.remove(key)) {
      Serial.printf("Basculada %llu confirmada pela API.\n",
                    static_cast<unsigned long long>(tip.sequence));
      return true;
    } else {
      Serial.println("API confirmou, mas a fila flash manteve o evento para reenvio.");
    }
  } else {
    Serial.printf("Envio pendente: HTTP %d; evento mantido para reenvio.\n", code);
  }
  return false;
}

bool readLevelDistance(float &distanceCm) {
  float samples[LEVEL_SAMPLE_COUNT];
  uint8_t validCount = 0;

  for (uint8_t i = 0; i < LEVEL_SAMPLE_COUNT; i++) {
    digitalWrite(LEVEL_TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(LEVEL_TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(LEVEL_TRIG_PIN, LOW);

    const unsigned long duration = pulseIn(LEVEL_ECHO_PIN, HIGH, LEVEL_ECHO_TIMEOUT_US);
    if (duration > 0) {
      const float sample = duration / 58.0f;
      if (sample >= 2.0f && sample <= 400.0f) samples[validCount++] = sample;
    }
    if (i + 1 < LEVEL_SAMPLE_COUNT) delay(60);
  }

  if (validCount < 3) return false;

  // Insertion sort so one HC-SR04 echo outlier does not dominate the result.
  for (uint8_t i = 1; i < validCount; i++) {
    const float value = samples[i];
    int j = static_cast<int>(i) - 1;
    while (j >= 0 && samples[j] > value) {
      samples[j + 1] = samples[j];
      j--;
    }
    samples[j + 1] = value;
  }

  if (validCount % 2 == 1) {
    distanceCm = samples[validCount / 2];
  } else {
    distanceCm = (samples[validCount / 2 - 1] + samples[validCount / 2]) / 2.0f;
  }
  return true;
}

bool readPendingLevel(StoredLevelReading &reading) {
  if (!preferences.isKey("lvlpend")) return false;
  if (preferences.getBytesLength("lvlpend") != sizeof(StoredLevelReading) ||
      preferences.getBytes("lvlpend", &reading, sizeof(reading)) != sizeof(reading)) {
    Serial.println("Leitura de nivel pendente invalida; removendo registro corrompido.");
    preferences.remove("lvlpend");
    return false;
  }
  return true;
}

bool storeLevelReading(uint32_t measuredAt, float distanceCm) {
  StoredLevelReading existing;
  if (readPendingLevel(existing)) return false;

  const uint64_t lastLevelSequence = preferences.getULong64("lastlvl", 0);
  if (lastLevelSequence == UINT64_MAX) return false;
  const uint64_t sequence = lastLevelSequence + 1;
  if (preferences.putULong64("lastlvl", sequence) != sizeof(sequence)) return false;

  const uint32_t now = millis();
  const int32_t elapsedMs = static_cast<int32_t>(measuredAt - now);
  const int64_t measuredUnixMs = eventUnixMs(now) + elapsedMs;
  const StoredLevelReading reading{sequence, measuredUnixMs, distanceCm};
  if (preferences.putBytes("lvlpend", &reading, sizeof(reading)) != sizeof(reading)) {
    Serial.println("Falha ao guardar leitura de nivel na memoria flash.");
    return false;
  }

  const float provisionalLevelCm = PROVISIONAL_H0_CM - distanceCm;
  Serial.printf("Nivel medido: distancia %.1f cm; subida provisoria %.1f cm; aguardando envio.\n",
                distanceCm, provisionalLevelCm);
  return true;
}

bool sendPendingLevel() {
  StoredLevelReading reading;
  if (!readPendingLevel(reading)) return false;

  char readingId[64];
  snprintf(readingId, sizeof(readingId), "%s-level-%llu", DEVICE_ID,
           static_cast<unsigned long long>(reading.sequence));
  char measuredAt[32];
  if (!formatUtc(reading.measuredUnixMs, measuredAt, sizeof(measuredAt))) {
    Serial.println("Horario da leitura de nivel invalido; registro mantido para reenvio.");
    return false;
  }

  char distanceText[24];
  snprintf(distanceText, sizeof(distanceText), "%.2f", reading.distanceCm);
  String payload = String("{\"device_id\":\"") + DEVICE_ID +
                   "\",\"reading_id\":\"" + readingId +
                   "\",\"measured_at\":\"" + measuredAt +
                   "\",\"distance_cm\":" + distanceText + "}";

  WiFiClient plainClient;
  WiFiClientSecure secureClient;
  HTTPClient http;
  if (!beginApiRequest(http, plainClient, secureClient, "/api/v1/level-readings")) return false;
  http.setTimeout(3500);
  http.addHeader("Content-Type", "application/json");
  if (strlen(FLOOD_DEVICE_TOKEN) > 0) {
    http.addHeader("Authorization", String("Bearer ") + FLOOD_DEVICE_TOKEN);
  }
  const int code = http.POST(payload);
  const String body = (code == 200 || code == 201) ? http.getString() : String();
  http.end();

  if ((code == 200 || code == 201) && body.indexOf(readingId) >= 0) {
    if (preferences.remove("lvlpend")) {
      Serial.printf("Leitura de nivel %llu confirmada pela API.\n",
                    static_cast<unsigned long long>(reading.sequence));
      return true;
    }
    Serial.println("API confirmou o nivel, mas a memoria flash manteve a leitura para reenvio.");
  } else {
    Serial.printf("Leitura de nivel pendente: HTTP %d; mantida para reenvio.\n", code);
  }
  return false;
}

void updateLevelSensor() {
  if (!clockReady) return;

  StoredLevelReading pending;
  if (!readPendingLevel(pending) &&
      (lastLevelCapture == 0 ||
       static_cast<uint32_t>(millis() - lastLevelCapture) >= LEVEL_INTERVAL_MS)) {
    lastLevelCapture = millis();
    float distanceCm = 0.0f;
    if (readLevelDistance(distanceCm)) {
      storeLevelReading(millis(), distanceCm);
    } else {
      Serial.println("Leitura HC-SR04 invalida; nova tentativa no proximo intervalo.");
    }
  }

  if (WiFi.status() == WL_CONNECTED &&
      (!apiUsesTls() || time(nullptr) >= 1700000000) &&
      readPendingLevel(pending) &&
      (lastLevelSendAttempt == 0 ||
       static_cast<uint32_t>(millis() - lastLevelSendAttempt) >= LEVEL_SEND_RETRY_MS)) {
    lastLevelSendAttempt = millis();
    sendPendingLevel();
  }
}

void updateBuzzer() {
  uint32_t count = 0;
  uint32_t lost = 0;
  portENTER_CRITICAL(&tipMux);
  count = detectedCount;
  lost = overflowCount;
  portEXIT_CRITICAL(&tipMux);

  const uint32_t now = millis();
  if (count != lastBuzzerCount) {
    lastBuzzerCount = count;
    tone(BUZZER_PIN, 2000);
    buzzerOffAt = now + 100;
    buzzerOn = true;
  } else if (buzzerOn && static_cast<int32_t>(now - buzzerOffAt) >= 0) {
    noTone(BUZZER_PIN);
    buzzerOn = false;
  }
  if (lost > 0 && static_cast<uint32_t>(now - lastOverflowReport) >= 5000) {
    Serial.printf("ATENCAO: %lu pulsos perdidos por fila temporaria cheia.\n",
                  static_cast<unsigned long>(lost));
    lastOverflowReport = now;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(SENSOR_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LEVEL_TRIG_PIN, OUTPUT);
  pinMode(LEVEL_ECHO_PIN, INPUT);
  noTone(BUZZER_PIN);
  digitalWrite(LEVEL_TRIG_PIN, LOW);

  if (!preferences.begin("floodrain", false)) {
    Serial.println("Falha na memoria flash; envio interrompido para evitar duplicacoes.");
    while (true) delay(1000);
  }
  lastSequence = preferences.getULong64("lastseq", 0);
  StoredTip stored;
  for (uint8_t i = 0; i < STORED_QUEUE_SLOTS; i++) {
    if (readSlot(i, stored) && stored.sequence > lastSequence) lastSequence = stored.sequence;
  }

  attachInterrupt(digitalPinToInterrupt(SENSOR_PIN), onTipEdge,
                  DETECTION_LEVEL == LOW ? FALLING : RISING);

  if (strlen(FLOOD_WIFI_SSID) == 0 || strlen(FLOOD_API_BASE_URL) == 0) {
    Serial.println("Preencha Wi-Fi e endereco da API em config.h.");
    return;
  }
  const bool https = apiUsesTls();
  if (!https && !String(FLOOD_API_BASE_URL).startsWith("http://")) {
    Serial.println("Endereco da API deve comecar com http:// ou https://.");
    return;
  }
  if (https && (strlen(FLOOD_TLS_CA_CERT) == 0 || strlen(FLOOD_DEVICE_TOKEN) < 32)) {
    Serial.println("HTTPS exige CA confiavel e token de pelo menos 32 caracteres em config.h.");
    return;
  }
  if (!https && strlen(FLOOD_DEVICE_TOKEN) > 0) {
    Serial.println("Token nao pode ser enviado por HTTP. Use HTTPS ou remova o token local.");
    return;
  }
  WiFi.mode(WIFI_STA);
  WiFi.begin(FLOOD_WIFI_SSID, FLOOD_WIFI_PASSWORD);
  lastWifiAttempt = millis();
  Serial.printf("Pluviometro e HC-SR04 iniciados; H0 provisoria: %.1f cm.\n",
                PROVISIONAL_H0_CM);
  Serial.println("Aguardando Wi-Fi e horario da API.");
}

void loop() {
  updateBuzzer();
  const uint32_t now = millis();

  if (WiFi.status() != WL_CONNECTED) {
    if (wifiWasConnected) Serial.println("Wi-Fi desconectado; eventos serao reenviados.");
    wifiWasConnected = false;
    if (strlen(FLOOD_WIFI_SSID) != 0 &&
        static_cast<uint32_t>(now - lastWifiAttempt) >= WIFI_RETRY_MS) {
      WiFi.reconnect();
      lastWifiAttempt = now;
    }
  } else {
    if (!wifiWasConnected) {
      wifiWasConnected = true;
      Serial.print("Wi-Fi conectado. IP do ESP32: ");
      Serial.println(WiFi.localIP());
      if (apiUsesTls()) configTime(0, 0, "pool.ntp.org", "time.google.com");
    }
    const uint32_t interval = clockReady ? TIME_REFRESH_MS : TIME_RETRY_MS;
    if (lastTimeAttempt == 0 || static_cast<uint32_t>(now - lastTimeAttempt) >= interval) {
      lastTimeAttempt = now;
      syncClock();
    }
  }

  persistDetectedTips();
  updateLevelSensor();
  if (WiFi.status() == WL_CONNECTED &&
      (!apiUsesTls() || time(nullptr) >= 1700000000) &&
      static_cast<uint32_t>(millis() - lastSendAttempt) >= sendIntervalMs) {
    lastSendAttempt = millis();
    sendIntervalMs = sendOldestTip() ? SEND_NEXT_MS : SEND_RETRY_MS;
  }
  delay(5);
}
