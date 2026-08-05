"""
Monitor de Tensao das Celulas via Arduino - Streamlit App
-----------------------------------------------------------
Le dados da porta serial no formato:
    V0: 0.022 V
    V1: 0.025 V
    V2: 0.032 V
    V3: 5.122 V
    V4: 12.326 V

A cada ciclo de leitura (aproximadamente 5 segundos), monta uma linha com
os 5 valores e guarda no historico da sessao. Os dados podem ser
visualizados em graficos (tempo x tensao), em tabela, e exportados em CSV.

Cada celula possui um botao liga/desliga que envia um comando via serial
para o Arduino. Enquanto a celula estiver ligada, um aviso permanece
visivel informando que ela nao deve ser manuseada.
"""

import time
import re
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import serial
import serial.tools.list_ports
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# ---------------------------------------------------------------------------
# Configuracoes gerais
# ---------------------------------------------------------------------------

NUM_CELLS = 5
CELL_LABELS = [f"C{i+1}" for i in range(NUM_CELLS)]   # C1 ... C5
READ_INTERVAL_SECONDS = 5
LINE_REGEX = re.compile(r"V(\d):\s*(-?\d+\.?\d*)\s*V")

st.set_page_config(
    page_title="Monitor de Celulas",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Estado da sessao
# ---------------------------------------------------------------------------

def init_session_state():
    defaults = {
        "connected": False,
        "ser": None,
        "port_name": None,
        "readings": [],          # lista de dicts: {hora, C1, C2, C3, C4, C5}
        "last_read_time": 0.0,
        "connection_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # estado inicial de cada toggle de celula
    for i in range(1, NUM_CELLS + 1):
        st.session_state.setdefault(f"toggle_{i}", False)


# ---------------------------------------------------------------------------
# Funcoes de conexao serial
# ---------------------------------------------------------------------------

def list_serial_ports():
    ports = serial.tools.list_ports.comports()
    return [p.device for p in ports]


def connect(port: str, baudrate: int):
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)  # tempo para o Arduino reiniciar apos abrir a porta
        ser.reset_input_buffer()
        st.session_state.ser = ser
        st.session_state.connected = True
        st.session_state.port_name = port
        st.session_state.connection_error = None
    except Exception as exc:
        st.session_state.connected = False
        st.session_state.connection_error = str(exc)


def disconnect():
    ser = st.session_state.ser
    if ser is not None:
        try:
            ser.close()
        except Exception:
            pass
    st.session_state.ser = None
    st.session_state.connected = False


# ---------------------------------------------------------------------------
# Leitura e parsing dos dados
# ---------------------------------------------------------------------------

def read_new_data(ser) -> dict:
    """Le todas as linhas disponiveis no buffer serial e retorna o ultimo
    valor visto para cada indice V0..V4."""
    data = {}
    try:
        while ser.in_waiting:
            raw = ser.readline().decode("utf-8", errors="ignore").strip()
            match = LINE_REGEX.match(raw)
            if match:
                idx = int(match.group(1))
                value = float(match.group(2))
                data[idx] = value
    except Exception as exc:
        st.session_state.connection_error = f"Erro de leitura: {exc}"
        st.session_state.connected = False
    return data


def append_reading(data: dict):
    row = {"hora": datetime.now()}
    for i in range(NUM_CELLS):
        row[CELL_LABELS[i]] = data.get(i)
    st.session_state.readings.append(row)


def get_dataframe() -> pd.DataFrame:
    if not st.session_state.readings:
        return pd.DataFrame(columns=["hora"] + CELL_LABELS)
    return pd.DataFrame(st.session_state.readings)


# ---------------------------------------------------------------------------
# Envio de comandos (liga / desliga celula)
# ---------------------------------------------------------------------------

def send_command(cell_index: int, turn_on: bool):
    """Envia para o Arduino o comando de ligar/desligar a celula indicada.

    Protocolo utilizado: "C<numero>_ON\\n" ou "C<numero>_OFF\\n"
    Exemplo: ligar a celula 3  -> "C3_ON\\n"
             desligar a celula 3 -> "C3_OFF\\n"
    """
    ser = st.session_state.ser
    if ser is None or not st.session_state.connected:
        return
    comando = f"C{cell_index}_{'ON' if turn_on else 'OFF'}\n"
    try:
        ser.write(comando.encode("utf-8"))
    except Exception as exc:
        st.session_state.connection_error = f"Erro ao enviar comando: {exc}"


def on_toggle_change(cell_index: int):
    novo_estado = st.session_state[f"toggle_{cell_index}"]
    send_command(cell_index, novo_estado)


# ---------------------------------------------------------------------------
# Graficos
# ---------------------------------------------------------------------------

def plot_cell(df: pd.DataFrame, cell_index: int):
    label = CELL_LABELS[cell_index - 1]
    fig = go.Figure()
    if not df.empty:
        fig.add_trace(
            go.Scatter(
                x=df["hora"],
                y=df[label],
                mode="lines+markers",
                line=dict(width=2),
                marker=dict(size=5),
                name=label,
            )
        )
    fig.update_layout(
        template="plotly_white",
        height=280,
        margin=dict(l=40, r=20, t=30, b=30),
        xaxis_title="Tempo",
        yaxis_title="Tensao (V)",
        showlegend=False,
        title=dict(text=f"Celula {cell_index} ({label})", x=0.0, font=dict(size=15)),
    )
    return fig


# ---------------------------------------------------------------------------
# Interface - Barra lateral (conexao)
# ---------------------------------------------------------------------------

def render_sidebar():
    st.sidebar.header("Conexao com o Arduino")

    if not st.session_state.connected:
        ports = list_serial_ports()
        if ports:
            port = st.sidebar.selectbox("Porta serial", ports)
        else:
            st.sidebar.write("Nenhuma porta encontrada.")
            port = st.sidebar.text_input("Informe a porta manualmente", value="")

        baudrate = st.sidebar.selectbox(
            "Baud rate", [9600, 19200, 38400, 57600, 115200], index=0
        )

        if st.sidebar.button("Conectar", use_container_width=True):
            if port:
                connect(port, baudrate)
                st.rerun()
            else:
                st.sidebar.error("Selecione ou informe uma porta valida.")

        if st.session_state.connection_error:
            st.sidebar.error(st.session_state.connection_error)

    else:
        st.sidebar.success(f"Conectado em {st.session_state.port_name}")
        if st.sidebar.button("Desconectar", use_container_width=True):
            disconnect()
            st.rerun()

    st.sidebar.divider()
    st.sidebar.caption(
        "Os dados sao lidos automaticamente a cada "
        f"{READ_INTERVAL_SECONDS} segundos enquanto a conexao estiver ativa."
    )


# ---------------------------------------------------------------------------
# Interface - Pagina principal
# ---------------------------------------------------------------------------

def render_main():
    st.title("Monitor de Tensao das Celulas")

    if not st.session_state.connected:
        st.info("Conecte-se ao Arduino na barra lateral para iniciar o monitoramento.")
        return

    # autorefresh a cada READ_INTERVAL_SECONDS segundos
    st_autorefresh(interval=READ_INTERVAL_SECONDS * 1000, key="auto_refresh")

    # tenta ler e consolidar uma nova leitura respeitando o intervalo minimo
    ser = st.session_state.ser
    now = time.time()
    data = read_new_data(ser)
    if len(data) == NUM_CELLS and (now - st.session_state.last_read_time) >= (
        READ_INTERVAL_SECONDS - 0.5
    ):
        append_reading(data)
        st.session_state.last_read_time = now

    if st.session_state.connection_error:
        st.error(st.session_state.connection_error)

    df = get_dataframe()

    st.subheader("Graficos por celula")

    for i in range(1, NUM_CELLS + 1):
        col_chart, col_control = st.columns([4, 1])

        with col_chart:
            st.plotly_chart(plot_cell(df, i), use_container_width=True, key=f"chart_{i}")

        with col_control:
            st.write("")
            st.toggle(
                f"Celula {i}",
                key=f"toggle_{i}",
                on_change=on_toggle_change,
                args=(i,),
            )
            if st.session_state[f"toggle_{i}"]:
                st.warning(
                    f"Celula {i} ligada. Nao mexer nesta celula enquanto "
                    "estiver ativa."
                )
            else:
                st.caption("Celula desligada.")

    st.divider()

    st.subheader("Dados registrados")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Exportar dados")
    export_df = df.copy()
    if not export_df.empty:
        export_df = export_df.rename(
            columns={
                "hora": "hora",
                "C1": "C1(V)",
                "C2": "C2(V)",
                "C3": "C3(V)",
                "C4": "C4(V)",
                "C5": "C5(V)",
            }
        )
    csv_bytes = export_df.to_csv(index=False).encode("utf-8")

    col_a, col_b = st.columns([1, 3])
    with col_a:
        st.download_button(
            label="Exportar CSV",
            data=csv_bytes,
            file_name=f"dados_celulas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_b:
        st.caption(f"Total de leituras armazenadas: {len(df)}")


# ---------------------------------------------------------------------------
# Execucao
# ---------------------------------------------------------------------------

def main():
    init_session_state()
    render_sidebar()
    render_main()


if __name__ == "__main__":
    main()
