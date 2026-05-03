# Sistema de ponto com reconhecimento facial

Projeto em Python para cadastro e reconhecimento de rostos pelo navegador, registro de entrada e saida em Cloud Firestore, mini-site em Flask e integração com ESP8266 usando MicroPython.

## O que o sistema faz

- cadastra novos funcionários pelo site Flask usando a camera do navegador
- reconhece funcionários já cadastrados a partir do site Flask
- grava cada registro com regra de entrada e saida
- expõe funcionários e registros em um mini-site local
- envia sinais para um ESP8266 quando o rosto é reconhecido, não reconhecido ou quando o sistema está em modo de cadastro

## Arquitetura

- Aplicação principal: Python 3.11+
- Reconhecimento facial: OpenCV com YuNet e SFace
- Banco de dados: Cloud Firestore
- Mini-site: Flask
- ESP8266: MicroPython com servidor HTTP simples

## Limitação importante sobre o ESP8266

O ESP8266 não executa Python tradicional de desktop. Para manter tudo em Python, este projeto usa MicroPython no ESP8266.

Fluxo esperado:

1. gravar o firmware do MicroPython no ESP8266 pela USB
2. enviar os arquivos [esp8266/boot.py](esp8266/boot.py) e [esp8266/main.py](esp8266/main.py) para a placa
3. deixar o ESP conectado ao Wi-Fi da mesma rede do computador
4. configurar a URL do ESP na aplicação principal

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m scripts.download_models
```

Coloque o JSON da service account do Firebase em `.secrets/firebase-service-account.json`.

## Iniciando o servidor

```bash
source .venv/bin/activate

export FIREBASE_PROJECT_ID="a3-project-bd5d6"
export FIREBASE_CREDENTIALS_PATH=".secrets/firebase-service-account.json"

# opcional: URL do ESP8266 na rede local
export ESP8266_URL="http://IP_DO_ESP"

python3 -m app.cli serve --host 0.0.0.0 --port 8000
```

Depois abra `http://localhost:8000` no navegador.

## Captura no navegador

A camera agora e acessada pelo proprio navegador. Isso elimina a dependencia de abrir a webcam por um executavel local para cadastro ou reconhecimento. Basta subir o Flask e abrir o site em um navegador com permissao de camera.

## Configuração por variáveis de ambiente

```bash
export ESP8266_URL="http://192.168.0.50"
export CAMERA_INDEX="0"
export FACE_MATCH_THRESHOLD="0.363"
export FIREBASE_PROJECT_ID="SEU-PROJETO"
export FIREBASE_CREDENTIALS_PATH="/caminho/para/service-account.json"
```

Variáveis disponíveis:

- `DATA_DIR`: diretório base para dados e fotos
- `ESP8266_URL`: URL base do ESP8266
- `FACE_MATCH_THRESHOLD`: limiar mínimo da similaridade do SFace
- `FIREBASE_PROJECT_ID`: identificador do projeto Firebase/Firestore
- `FIREBASE_CREDENTIALS_PATH`: caminho para o JSON da conta de serviço do Firebase
- `WEB_ENROLLMENT_SAMPLES`: quantidade mínima de capturas para cadastro
- `WEB_SCAN_SAMPLES`: quantidade mínima de capturas para reconhecimento

O navegador e quem escolhe a camera. Em geral, no celular ou notebook, a camera frontal ja sera usada automaticamente.

## Uso

Validar a conexao com o Firebase:

```bash
python3 -m app.cli init-db
```

Subir o mini-site:

```bash
python3 -m app.cli serve --host 0.0.0.0 --port 8000
```

Depois abra `http://localhost:8000`.

## Modelos ONNX usados

- `face_detection_yunet_2023mar.onnx`
- `face_recognition_sface_2021dec.onnx`

O script [scripts/download_models.py](scripts/download_models.py) baixa ambos automaticamente.

## Como o cadastro funciona

1. o usuario abre a camera no site
2. o sistema envia o sinal `registering` para o ESP8266
3. o navegador captura as amostras faciais necessarias
4. o Flask extrai o embedding e salva a credencial no Firebase

## Como o reconhecimento funciona

1. o usuario escolhe se vai registrar entrada ou saida
2. o navegador envia as capturas faciais ao Flask
3. o sistema compara o embedding com as credenciais do Firebase
4. se a pessoa ja estiver dentro, uma nova entrada e bloqueada
5. se a pessoa nao tiver entrada em aberto, a saida e bloqueada

## Sinais enviados ao ESP8266

- `recognized`: funcionário reconhecido
- `unknown`: rosto não cadastrado
- `registering`: modo de cadastro ativo
- `denied`: tentativa de entrada ou saida invalida para o estado atual

## Deploy do ESP8266 com MicroPython

Exemplo com `mpremote` após conectar a placa por USB:

```bash
pip install mpremote
mpremote connect auto fs cp esp8266/boot.py :boot.py
mpremote connect auto fs cp esp8266/main.py :main.py
mpremote connect auto reset
```

Se a placa ainda não estiver com MicroPython, primeiro grave o firmware adequado do ESP8266. Isso depende do modelo exato da sua placa.
