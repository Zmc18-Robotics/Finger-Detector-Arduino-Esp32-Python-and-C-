/*
  ESP32 Hand & Face Detection LED Controller
  
  Koneksi / Connection :
  - LED Finger 1: GPIO 18
  - LED Finger 2: GPIO 19
  - LED Finger 3: GPIO 21
  - LED Finger 4: GPIO 22
  - LED Finger 5: GPIO 23
  - LED Pin 5 (Nod): GPIO 5
  
  Data Format dari Python: "finger_count,nod_status\n"
  - finger_count: 0-5 (jumlah jari yang terdeteksi)
  - nod_status: 0 atau 1 (0=tidak mengangguk, 1=mengangguk terdeteksi)
*/

// Pin definitions
const int fingerLEDs[] = {18, 19, 21, 22, 23};  // LED untuk 5 jari
const int nodLED = 5;  // LED untuk deteksi mengangguk
const int numFingerLEDs = 5;

// Variables
String receivedData = "";
bool dataComplete = false;
int currentFingerCount = 0;
bool nodDetected = false;

void setup() {
  // Initialize serial communication
  Serial.begin(115200);
  
  // Initialize LED pins
  for (int i = 0; i < numFingerLEDs; i++) {
    pinMode(fingerLEDs[i], OUTPUT);
    digitalWrite(fingerLEDs[i], LOW);
  }
  
  pinMode(nodLED, OUTPUT);
  digitalWrite(nodLED, LOW);
  
  // Startup LED test
  testLeds();
  
  Serial.println("ESP32 pendeteksi tangan dan wajah siap!");
  Serial.println("Menunggu untuk data...");
  Serial.println("Data format: finger_count,nod_status");
}

void loop() {
  // Baca data serial
  if (Serial.available() > 0) {
    String receivedData = Serial.readStringUntil('\n');
    receivedData.trim();
    
    // Process data
    processReceivedData(receivedData);
  }
  
  delay(50); // Small delay untuk stabilitas
}

void processReceivedData(String data) {
  // Parse data: "finger_count,nod_status\n"
  int commaIndex = data.indexOf(',');
  
  if (commaIndex > 0) {
    // Parse finger count
    String fingerCountStr = data.substring(0, commaIndex);
    int fingerCount = fingerCountStr.toInt();
    
    // Parse nod status
    String nodStatusStr = data.substring(commaIndex + 1);
    int nodStatus = nodStatusStr.toInt();
    
    // Validasi dan kontrol LED finger
    if (fingerCount >= 0 && fingerCount <= 5) {
      controlLeds(fingerCount);
      Serial.print("Fingers detected: ");
      Serial.println(fingerCount);
    } else {
      Serial.println("Invalid finger count received");
    }
    
    // Kontrol LED nod jika terdeteksi
    if (nodStatus == 1) {
      triggerNodBlink();
    }
    // Code by Zmc18_Robotics, @mc.zminecrafter_18
  } else {
    // Fallback untuk format lama (hanya finger count)
    int fingerCount = data.toInt();
    if (fingerCount >= 0 && fingerCount <= 5) {
      controlLeds(fingerCount);
      Serial.print("Fingers detected: ");
      Serial.println(fingerCount);
    } else {
      Serial.println("Invalid finger count received");
    }
  }
}

void controlLeds(int fingerCount) {
  // Matikan semua LED finger terlebih dahulu
  for (int i = 0; i < numFingerLEDs; i++) {
    digitalWrite(fingerLEDs[i], LOW);
  }
  
  // Nyalakan LED sesuai jumlah jari yang terdeteksi
  for (int i = 0; i < fingerCount && i < numFingerLEDs; i++) {
    digitalWrite(fingerLEDs[i], HIGH);
  }
}

void testLeds() {
  Serial.println("Testing LEDs...");
  
  // Test semua LED finger - nyalakan satu per satu
  for (int i = 0; i < numFingerLEDs; i++) {
    digitalWrite(fingerLEDs[i], HIGH);
    delay(200);
    digitalWrite(fingerLEDs[i], LOW);
  }
  
  // Test LED nod - blink 3 kali
  for (int i = 0; i < 3; i++) {
    digitalWrite(nodLED, HIGH);
    delay(150);
    digitalWrite(nodLED, LOW);
    delay(150);
  }
  
  Serial.println("LED test completed");
}

void triggerNodBlink() {
  // Blink LED pin 5 sebanyak 3 kali dengan cepat
  Serial.println("Nod detected! Blinking LED pin 5...");
  
  // Simpan state LED finger saat ini
  bool fingerStates[numFingerLEDs];
  for (int i = 0; i < numFingerLEDs; i++) {
    fingerStates[i] = digitalRead(fingerLEDs[i]);
  }
  
  // Blink 3 kali
  for (int blink = 0; blink < 3; blink++) {
    digitalWrite(nodLED, HIGH);
    delay(150);  // LED nyala 150ms
    digitalWrite(nodLED, LOW);
    delay(100);  // LED mati 100ms
  }
  
  // Restore state LED finger
  for (int i = 0; i < numFingerLEDs; i++) {
    digitalWrite(fingerLEDs[i], fingerStates[i]);
  }
  
  Serial.println("Nod blink complete!");
}

// Code by Zmc18_Robotics, @mc.zminecrafter_18
// Fungsi tambahan untuk testing manual
void serialEvent() {
  // Fungsi ini dipanggil otomatis ketika ada data serial
  // Bisa digunakan untuk testing manual via Serial Monitor
}
