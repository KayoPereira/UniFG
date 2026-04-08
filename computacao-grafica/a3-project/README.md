# Sistema de ponto com reconhecimento facial

Projeto em Python para cadastro e reconhecimento de rostos com OpenCV, registro de ponto em SQLite, mini-site de exibição em Flask e integração com ESP8266 usando MicroPython.

## O que o sistema faz

- cadastra novos funcionários com webcam
- reconhece funcionários já cadastrados
- grava cada batida de ponto com data e hora
- expõe funcionários e registros em um mini-site local
- envia sinais para um ESP8266 quando o rosto é reconhecido, não reconhecido ou quando o sistema está em modo de cadastro

## Arquitetura

- Aplicação principal: Python 3.11+
- Reconhecimento facial: OpenCV com YuNet e SFace
- Banco de dados: SQLite
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
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.download_models
python -m app.cli init-db
```

## Webcam no WSL

No WSL2, webcams normalmente nao aparecem como `/dev/video0`, mesmo estando acessiveis no Windows. Para esse caso, o projeto inclui um launcher que executa apenas os comandos que dependem da webcam com o Python do Windows, mantendo o mesmo codigo e o mesmo banco do projeto.

Exemplo de uso a partir do WSL:

```bash
bash scripts/run_windows_cli.sh enroll --code FUNC001 --name "Maria Silva" --department "Financeiro"
bash scripts/run_windows_cli.sh recognize
```

Na primeira execucao, o script cria um ambiente virtual no Windows e instala as dependencias automaticamente. Se o Windows ainda nao tiver Python instalado, instale com:

```powershell
winget install -e --id Python.Python.3.11 --scope user
```

Para rodar o mini-site e outros comandos no WSL lendo o mesmo banco usado pelo launcher do Windows, use:

```bash
bash scripts/run_wsl_cli.sh init-db
bash scripts/run_wsl_cli.sh serve --host 0.0.0.0 --port 8000
```

## Configuração por variáveis de ambiente

```bash
export ESP8266_URL="http://192.168.0.50"
export CAMERA_INDEX="0"
export FACE_MATCH_THRESHOLD="0.363"
```

Variáveis disponíveis:

- `DATA_DIR`: diretório base para dados e fotos
- `ESP8266_URL`: URL base do ESP8266
- `CAMERA_INDEX`: índice da webcam
- `FACE_MATCH_THRESHOLD`: limiar mínimo da similaridade do SFace
- `FACES_DIR`: diretório onde as fotos de referência serão salvas
- `DATABASE_PATH`: caminho opcional do SQLite

Se a sua webcam nao estiver no indice padrao `0`, descubra o indice com `python -m app.cli list-cameras` e depois exporte `CAMERA_INDEX` com o valor correto.

## Uso

Inicializar o banco:

```bash
python -m app.cli init-db
```

Cadastrar um novo funcionário:

```bash
python -m app.cli enroll --code FUNC001 --name "Maria Silva" --department "Financeiro"
```

Reconhecer um rosto e registrar ponto:

```bash
python -m app.cli recognize
```

Listar cameras disponiveis no OpenCV:

```bash
python -m app.cli list-cameras
```

Subir o mini-site:

```bash
python -m app.cli serve --host 0.0.0.0 --port 8000
```

Depois abra `http://localhost:8000`.

## Modelos ONNX usados

- `face_detection_yunet_2023mar.onnx`
- `face_recognition_sface_2021dec.onnx`

O script [scripts/download_models.py](scripts/download_models.py) baixa ambos automaticamente.

## Como o cadastro funciona

1. o sistema envia o sinal `registering` para o ESP8266
2. a webcam abre
3. posicione apenas um rosto na tela
4. pressione `C` sete vezes para coletar sete amostras faciais
5. o sistema salva o embedding e uma foto de referência do funcionário

## Como o reconhecimento funciona

1. a webcam abre
2. o sistema tenta encontrar o rosto principal do quadro
3. se a similaridade ultrapassar o limiar configurado, registra a batida de ponto
4. se o rosto permanecer como desconhecido por alguns quadros, envia o sinal de desconhecido ao ESP8266

## Sinais enviados ao ESP8266

- `recognized`: funcionário reconhecido
- `unknown`: rosto não cadastrado
- `registering`: modo de cadastro ativo

## Deploy do ESP8266 com MicroPython

Exemplo com `mpremote` após conectar a placa por USB:

```bash
pip install mpremote
mpremote connect auto fs cp esp8266/boot.py :boot.py
mpremote connect auto fs cp esp8266/main.py :main.py
mpremote connect auto reset
```

Se a placa ainda não estiver com MicroPython, primeiro grave o firmware adequado do ESP8266. Isso depende do modelo exato da sua placa.
