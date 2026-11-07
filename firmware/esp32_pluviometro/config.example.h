#pragma once

// Copie este arquivo para config.h e preencha os valores somente na copia local.
// Use o IPv4 do computador que esta executando a API na rede Wi-Fi local.
// 127.0.0.1 aponta para o proprio ESP32 e nao acessa o computador.
#define FLOOD_WIFI_SSID ""
#define FLOOD_WIFI_PASSWORD ""
#define FLOOD_API_BASE_URL "http://192.168.1.100:8000"

// Para a VM: use https://seu-dominio, token exclusivo e CA que assinou o certificado.
// Preencha apenas em config.h. Nunca use setInsecure() nem envie token por HTTP.
#define FLOOD_DEVICE_TOKEN ""
#define FLOOD_TLS_CA_CERT ""
