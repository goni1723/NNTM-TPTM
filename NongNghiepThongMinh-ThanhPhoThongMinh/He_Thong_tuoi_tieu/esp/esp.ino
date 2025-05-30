#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

// Kết nối WiFi
const char* ssid = "hello";
const char* password = "12345678";

ESP8266WebServer server(80);

// Biến lưu dữ liệu cảm biến nhận từ Uno
String lastSensorData = "Chưa có dữ liệu";

void handlePump() {
  if (!server.hasArg("volume")) {
    server.send(400, "text/plain", "Thiếu tham số volume");
    return;
  }
  String vol = server.arg("volume");
  Serial.println(vol);  // Gửi qua UART đến Uno

  Serial.print("Gửi volume tới Uno: ");
  Serial.println(vol);
  server.send(200, "text/plain", "Đã gửi lệnh bơm: " + vol + " ml");
}

void handleData() {
  server.send(200, "text/plain", lastSensorData);
}

void setup() {
  Serial.begin(9600);  // Giao tiếp UART với Arduino Uno
  WiFi.begin(ssid, password);

  Serial.print("Đang kết nối WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("Đã kết nối WiFi. IP: ");
  Serial.println(WiFi.localIP());

  // Định nghĩa API endpoint
  server.on("/pump", HTTP_GET, handlePump);   // Gửi lệnh bơm
  server.on("/data", HTTP_GET, handleData);   // Lấy dữ liệu cảm biến

  server.begin();
  Serial.println("Web server đã sẵn sàng");
}

void loop() {
  server.handleClient();

  // Nhận dữ liệu cảm biến từ Arduino Uno qua UART
  if (Serial.available()) {
    String data = Serial.readStringUntil('\n');
    lastSensorData = data;
    Serial.print("Nhận từ Uno: ");
    Serial.println(data);
  }
}
