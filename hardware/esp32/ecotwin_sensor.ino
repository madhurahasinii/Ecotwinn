#include <WiFi.h>
#include <HTTPClient.h>
#include "HX711.h"

// ===== Wi-Fi configuration =====
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Replace with your computer's LAN IP address.
// Do not use localhost: the ESP32 is a separate device.
const char* API_URL = "http://YOUR_COMPUTER_IP:8000/api/sensor/readings";

// ===== Hardware pins =====
#define HX711_DOUT 4
#define HX711_SCK  5

HX711 scale;

// Replace with your calibration factor after calibration.
float calibrationFactor = 1.0;

unsigned long lastSendTime = 0;
const unsigned long SEND_INTERVAL = 5000;

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Connecting to Wi-Fi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("Wi-Fi connected");
  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("EcoTwin sensor starting");

  scale.begin(HX711_DOUT, HX711_SCK);

  connectWiFi();

  if (scale.is_ready()) {
    Serial.println("HX711 detected");
  } else {
    Serial.println("WARNING: HX711 not detected");
  }
}

void sendReading(float weightGrams) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected; reading not sent");
    return;
  }

  HTTPClient http;
  http.begin(API_URL);
  http.addHeader("Content-Type", "application/json");

  String payload = "{";
  payload += "\"device_id\":\"ET-SOL-02\",";
  payload += "\"weight_grams\":" + String(weightGrams, 2) + ",";
  payload += "\"timestamp_ms\":" + String(millis());
  payload += "}";

  int responseCode = http.POST(payload);

  Serial.print("Backend HTTP status: ");
  Serial.println(responseCode);

  if (responseCode > 0) {
    Serial.println(http.getString());
  }

  http.end();
}

void loop() {
  if (millis() - lastSendTime >= SEND_INTERVAL) {
    lastSendTime = millis();

    if (!scale.is_ready()) {
      Serial.println("HX711 not ready");
      return;
    }

    float weightGrams = scale.get_units(5) * 1000.0;

    Serial.print("Weight: ");
    Serial.print(weightGrams);
    Serial.println(" g");

    sendReading(weightGrams);
  }
}
