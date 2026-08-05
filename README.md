# Monitor de Tensao das Celulas via Arduino

Aplicativo em Streamlit que le dados da porta serial do Arduino, exibe a
tensao de cada celula em graficos (tempo x tensao), guarda o historico
completo da sessao e permite exportar tudo em CSV. Cada celula possui um
botao liga/desliga que envia um comando para o Arduino.

## Estrutura do projeto

```
app.py             # aplicativo principal do Streamlit
requirements.txt   # dependencias Python
README.md          # este arquivo
```

## Formato de dados esperado do Arduino

O app espera que o Arduino escreva continuamente na serial, no formato:

```
V0: 0.022 V
V1: 0.025 V
V2: 0.032 V
V3: 5.122 V
V4: 12.326 V
```

Cada ciclo completo (V0 a V4) e convertido em uma linha do historico com as
colunas `hora, C1(V), C2(V), C3(V), C4(V), C5(V)`.

## Como o app funciona

- **Leitura serial**: a cada 5 segundos o app le o que estiver disponivel
  no buffer da porta serial, identifica as linhas `V0..V4` e, quando tem os
  5 valores, grava uma nova leitura no historico da sessao.
- **Graficos**: um grafico Plotly por celula (tempo x tensao), atualizado
  automaticamente a cada leitura.
- **Historico e exportacao**: todas as leituras feitas durante o
  funcionamento ficam guardadas e podem ser exportadas em CSV a qualquer
  momento pelo botao **Exportar CSV**.
- **Liga/desliga por celula**: cada celula tem um botao (toggle) que, ao
  ser acionado, envia um comando via serial para o Arduino. Enquanto a
  celula estiver ligada, um aviso fixo informa que ela nao deve ser
  manuseada.

## Protocolo de comando liga/desliga

O app envia pela serial uma string simples terminada em `\n`, no formato
`C<numero da celula>_ON` ou `C<numero da celula>_OFF`:

```
C1_ON
C1_OFF
C2_ON
C2_OFF
C3_ON
C3_OFF
C4_ON
C4_OFF
C5_ON
C5_OFF
```

No sketch do Arduino, e preciso ler a serial e interpretar esses comandos.
Exemplo minimo:

```cpp
void loop() {
  if (Serial.available()) {
    String comando = Serial.readStringUntil('\n');
    comando.trim();

    if (comando == "C1_ON")  { digitalWrite(RELE_C1, HIGH); }
    if (comando == "C1_OFF") { digitalWrite(RELE_C1, LOW);  }
    if (comando == "C2_ON")  { digitalWrite(RELE_C2, HIGH); }
    if (comando == "C2_OFF") { digitalWrite(RELE_C2, LOW);  }
    // ... repetir para C3, C4, C5
  }

  // aqui continua o codigo normal de leitura e impressao de V0..V4
}
```

Adapte `RELE_C1..RELE_C5` para os pinos reais que controlam cada celula
(rele, MOSFET, etc). O importante e que o Arduino reconheca exatamente
essas strings.

## Passo a passo para executar

1. **Instale o Python** (versao 3.9 ou superior) se ainda nao tiver.

2. **Baixe os arquivos** (`app.py`, `requirements.txt` e este `README.md`)
   para uma mesma pasta no seu computador.

3. **Crie um ambiente virtual (recomendado)**:

   ```bash
   python -m venv venv
   source venv/bin/activate      # Linux/Mac
   venv\Scripts\activate         # Windows
   ```

4. **Instale as dependencias**:

   ```bash
   pip install -r requirements.txt
   ```

5. **Grave o sketch no Arduino** garantindo que ele:
   - Imprima continuamente as 5 linhas no formato `V0: 0.022 V` ate
     `V4: 12.326 V`.
   - Leia comandos `C<n>_ON` / `C<n>_OFF` da serial e acione o pino
     correspondente.

6. **Conecte o Arduino via USB** e feche qualquer outro programa que
   esteja usando a porta serial (Arduino IDE, monitor serial, etc). Apenas
   um programa pode usar a porta por vez.

7. **Rode o app**:

   ```bash
   streamlit run app.py
   ```

8. O navegador abre automaticamente (geralmente em
   `http://localhost:8501`). Na barra lateral:
   - Selecione a porta serial (ex: `COM3` no Windows, `/dev/ttyUSB0` ou
     `/dev/ttyACM0` no Linux/Mac).
   - Selecione o baud rate (o mesmo configurado no `Serial.begin(...)` do
     Arduino, normalmente 9600).
   - Clique em **Conectar**.

9. A partir dai os graficos, a tabela e os botoes liga/desliga das
   celulas aparecem e sao atualizados automaticamente a cada 5 segundos.

10. Para exportar os dados, use o botao **Exportar CSV** na parte
    inferior da pagina. Ele baixa todo o historico coletado desde o
    inicio da conexao.

## Observacao sobre permissao de porta no Linux

Se ocorrer erro de permissao ao conectar, adicione seu usuario ao grupo
`dialout`:

```bash
sudo usermod -a -G dialout $USER
```

Depois faca logout e login novamente para a alteracao ter efeito.
