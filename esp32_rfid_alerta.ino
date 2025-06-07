#include <WiFi.h>
#include <HTTPClient.h>
#include <MFRC522.h>
#include <SPI.h>
#include <Servo.h>

// Credenciais Wi-Fi
const char* ssid = "SEU_WIFI";
const char* password = "SENHA_WIFI";

// Endpoint do Flask
const char* servidor_flask = "http://192.168.1.100:5000/alerta";  // use o IP do seu servidor Flask

// Pinos RFID
#define SS_PIN  21
#define RST_PIN 22
MFRC522 mfrc522(SS_PIN, RST_PIN);

// Servo
Servo trava;
const int servoPin = 13;

// LEDs
const int ledVerde = 26;
const int ledVermelho = 27;

// UIDs autorizados
String cartoesAutorizados[] = {
  "AB12CD34",  // Enfermeira Ana
  "EF56GH78"   // Enfermeiro João
};

void setup() {
  Serial.begin(115200);

  // Servo e LEDs
  trava.attach(servoPin);
  trava.write(0);  // posição fechada
  pinMode(ledVerde, OUTPUT);
  pinMode(ledVermelho, OUTPUT);

  // Inicializa SPI e RFID
  SPI.begin();
  mfrc522.PCD_Init();
  delay(1000);

  // Conecta ao Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("Conectando ao Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWi-Fi conectado!");
  Serial.println(WiFi.localIP());
}

void loop() {
  if (!mfrc522.PICC_IsNewCardPresent()) return;
  if (!mfrc522.PICC_ReadCardSerial()) return;

  String uid = getUID();
  Serial.println("Cartão lido: " + uid);

  if (isAutorizado(uid)) {
    abrirCarrinho();
    enviarAlerta(uid);
  } else {
    acessoNegado();
  }

  delay(2000); // Evita múltiplas leituras seguidas
  mfrc522.PICC_HaltA();
}

String getUID() {
  String uid = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    uid += String(mfrc522.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  return uid;
}

bool isAutorizado(String uid) {
  for (String autorizado : cartoesAutorizados) {
    if (uid == autorizado) return true;
  }
  return false;
}

void abrirCarrinho() {
  Serial.println("Cartão autorizado. Abrindo carrinho...");
  digitalWrite(ledVerde, HIGH);
  digitalWrite(ledVermelho, LOW);
  trava.write(90);  // abre
  delay(3000);
  trava.write(0);   // fecha de novo
  digitalWrite(ledVerde, LOW);
}

void acessoNegado() {
  Serial.println("Cartão não autorizado!");
  digitalWrite(ledVerde, LOW);
  digitalWrite(ledVermelho, HIGH);
  delay(2000);
  digitalWrite(ledVermelho, LOW);
}

void enviarAlerta(String uid) {
  if ((WiFi.status() == WL_CONNECTED)) {
    HTTPClient http;
    http.begin(servidor_flask);
    http.addHeader("Content-Type", "application/json");

    String json = "{\"uid\":\"" + uid + "\"}";
    int httpResponseCode = http.POST(json);

    if (httpResponseCode > 0) {
      Serial.println("Alerta enviado ao servidor!");
    } else {
      Serial.print("Erro ao enviar alerta: ");
      Serial.println(httpResponseCode);
    }

    http.end();
  }
}
