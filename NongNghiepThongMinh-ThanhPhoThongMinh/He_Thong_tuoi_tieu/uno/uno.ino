#include <SoftwareSerial.h>
#include <DHT.h>

#define RELAY_PIN 7
#define DHTPIN 9
#define DHTTYPE DHT22

#define FLOW_SENSOR_PIN 2
#define SOIL_SENSOR_PIN A0

const float THRESHOLD = 5.0; // ml

SoftwareSerial espSerial(5, 6);  // RX=5, TX=6
DHT dht(DHTPIN, DHTTYPE);

volatile int flowPulseCount = 0;
unsigned long lastSensorRead = 0;
unsigned long lastFlowMeasureTime = 0;
float flowRate = 0.0;

// ISR cho cảm biến lưu lượng
void flowPulseISR() {
  flowPulseCount++;
}

void setup() {
  Serial.begin(9600);
  espSerial.begin(9600);
  dht.begin();

  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);

  pinMode(FLOW_SENSOR_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(FLOW_SENSOR_PIN), flowPulseISR, FALLING);
}

void loop() {
  // Nhận dữ liệu từ ESP để điều khiển bơm
  if (espSerial.available()) {
    String volStr = espSerial.readStringUntil('\n');
    float vol = volStr.toFloat();
    Serial.print("Received volume: ");
    Serial.println(vol);

    if (vol > THRESHOLD) {
      unsigned long duration = (unsigned long)(vol * 1000); // 1 ml = 1s giả định
      digitalWrite(RELAY_PIN, HIGH);
      delay(duration);
      digitalWrite(RELAY_PIN, LOW); // Tắt bơm sau khi bơm xong
      Serial.print("Pumped ");
      Serial.print(vol);
      Serial.println(" ml");
    } else {
      digitalWrite(RELAY_PIN, LOW); // Đảm bảo relay luôn ở trạng thái tắt
      Serial.print("Volume ");
      Serial.print(vol);
      Serial.println(" ml is below threshold. Pump not activated.");
    }
  }



  // Đọc cảm biến định kỳ mỗi 5s
  if (millis() - lastSensorRead >= 5000) {
    lastSensorRead = millis();

    float temp = dht.readTemperature();
    float humid = dht.readHumidity();
    int soil = analogRead(SOIL_SENSOR_PIN);

    noInterrupts();
    int pulseCount = flowPulseCount;
    flowPulseCount = 0;
    interrupts();

    flowRate = pulseCount * 2.25;  // điều chỉnh tùy loại cảm biến

    // Gửi dữ liệu đến ESP8266
    String data = String(temp, 1) + "," + String(humid, 1) + "," + String(soil) + "," + String(flowRate, 2);
    espSerial.println(data);
    Serial.print("Đã gửi đến ESP8266: ");
    Serial.println(data);
  }
}
