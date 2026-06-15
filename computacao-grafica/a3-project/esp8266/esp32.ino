#include <WiFi.h>
#include <HTTPClient.h>

//=========================
// WiFi
//=========================

const char* ssid = "iPhone (2)";
const char* password = "kayo1234";

//=========================
// Firebase
//=========================

const char* firebaseURL = "https://a3-project-bd5d6-default-rtdb.firebaseio.com/motor/enable.json";

//=========================
// Pinos
//=========================

#define STEP_PIN    25
#define ENABLE_PIN  26
#define DIR_PIN     27

//=========================
// Configuração do motor
//=========================

const int PASSOS = 100;
const int TEMPO_PULSO = 16666;

const int DIR_ABRIR = HIGH;
const int DIR_FECHAR = LOW;

//=========================

// Conecta o ESP à rede WiFi
void conectarWifi()
{
    Serial.println("Conectando ao WiFi...");

    WiFi.begin(ssid, password);

    while (WiFi.status() != WL_CONNECTED)
    {
        delay(500);
        Serial.print(".");
    }

    Serial.println("\nWiFi conectado!");
    Serial.println(WiFi.localIP());
}

// Busca o valor da flag enable no Firebase para determinar se o ciclo de abertura/fechamento deve ser executado
bool lerEnable()
{
    HTTPClient http;
    http.begin(firebaseURL);

    int codigo = http.GET();

    if (codigo == 200)
    {
        String resposta = http.getString();
        resposta.trim();
        http.end();

        return resposta == "true";
    }

    http.end();
    return false;
}

// Atualiza o valor do enable no Firebase para controlar o ciclo de abertura/fechamento
void atualizarEnable(bool valor)
{
    HTTPClient http;

    http.begin(firebaseURL);
    http.addHeader("Content-Type", "application/json");

    String body = valor ? "true" : "false";

    int codigo = http.PUT(body);

    Serial.print("Firebase atualizado: ");
    Serial.println(codigo);

    http.end();
}

// Adicionei essa lógica porque o motor só roda quando está ENABLE, mas se ficar
// ENABLE o tempo todo, ele pode superaquecer.
void moverMotor(int direcao)
{
    // liga driver (ENABLE ativo em LOW)
    digitalWrite(ENABLE_PIN, LOW);
    delay(20);

    digitalWrite(DIR_PIN, direcao);
    delay(50);

    for (int i = 0; i < PASSOS; i++)
    {
        digitalWrite(STEP_PIN, HIGH);
        delayMicroseconds(TEMPO_PULSO);

        digitalWrite(STEP_PIN, LOW);
        delayMicroseconds(TEMPO_PULSO);
    }

    // desliga driver ao final do ciclo
    digitalWrite(ENABLE_PIN, HIGH);
}

void setup()
{
    Serial.begin(115200);

    pinMode(STEP_PIN, OUTPUT);
    pinMode(ENABLE_PIN, OUTPUT);
    pinMode(DIR_PIN, OUTPUT);

    digitalWrite(STEP_PIN, LOW);
    digitalWrite(DIR_PIN, LOW);
    digitalWrite(ENABLE_PIN, HIGH);

    conectarWifi();

    Serial.println("------------------------");
    Serial.println("Sistema iniciado");
    Serial.println("------------------------");
}

void loop()
{
    if (WiFi.status() != WL_CONNECTED)
    {
        conectarWifi();
    }

    bool enable = lerEnable();

    if (enable)
    {
        Serial.println("ABRINDO CANCELA");

        moverMotor(DIR_ABRIR);

        delay(10000);

        Serial.println("FECHANDO CANCELA");

        moverMotor(DIR_FECHAR);

        atualizarEnable(false);

        Serial.println("Ciclo finalizado");
    }

    delay(1000);
}