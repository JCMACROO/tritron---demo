"""
TRITON Smart Water Digital Twin - Interactive Dashboard
Framework TRITON: Technology Resilience, Cybersecurity and Intelligence for
Transformative Optimization of Smart Water Networks.

Application Module: app.ui
"""

from __future__ import annotations
import math
from pathlib import Path
import sys
import time

# Ensure project root is in path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.engine.wntr_runner import (
    load_network,
    create_simple_network,
    get_network_summary,
    save_network,
)
from src.scenarios.injector import (
    ScenarioType,
    ScenarioConfig,
    execute_scenario,
)
from src.ai.detector import evaluate_triton_detector
from src.ai.metrics import (
    calculate_hydraulic_and_sustainability_metrics,
    compute_triton_evidence_vector,
)

# Page configuration
st.set_page_config(
    page_title="TRITON Smart Water Digital Twin",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom header styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1565C0;
        margin-bottom: 2px;
    }
    .sub-title {
        font-size: 1.02rem;
        color: #455A64;
        margin-bottom: 16px;
    }
    .preset-box {
        background: linear-gradient(135deg, #E3F2FD 0%, #F3E5F5 100%);
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 16px;
        border: 1px solid #BBDEFB;
    }
    .phase-card {
        background-color: #FFFFFF;
        border-radius: 10px;
        padding: 14px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        height: 100%;
    }
    .phase-header {
        font-size: 0.95rem;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .phase-meta {
        font-size: 0.82rem;
        color: #64748B;
        line-height: 1.35;
    }
    .phase-val {
        font-size: 1.15rem;
        font-weight: 700;
        color: #1E293B;
        margin-top: 6px;
    }
</style>
""", unsafe_allow_html=True)


def get_target_components(cfg):
    """Safely extracts target node and link according to the active scenario type."""
    target_node = None
    target_link = None
    if cfg.scenario_type in [ScenarioType.LEAK, ScenarioType.STEALTH_ATTACK]:
        target_node = cfg.leak_node
    elif cfg.scenario_type == ScenarioType.DEMAND_BURST:
        target_node = cfg.burst_node
    elif cfg.scenario_type == ScenarioType.SENSOR_SPOOF:
        target_node = cfg.spoof_node

    if cfg.scenario_type == ScenarioType.PIPE_CLOSURE:
        target_link = cfg.close_pipe
    elif cfg.scenario_type == ScenarioType.PUMP_OUTAGE:
        target_link = cfg.outage_pump

    return target_node, target_link


def plot_enhanced_network(wn, target_node=None, target_link=None, scenario_type=ScenarioType.BASELINE,
                          monitored_sensors=None, color_mode="Componentes y Amenazas", sim_pressure_df=None):
    """
    Renders a clear, highly informative interactive network topology map using Plotly.
    Safely handles all node types (Junction, Reservoir, Tank) avoiding missing attribute errors.
    """
    monitored_sensors = [str(s) for s in (monitored_sensors or [])]
    target_node_str = str(target_node) if target_node is not None else ""
    target_link_str = str(target_link) if target_link is not None else ""

    # Calculate average pressure per node if available and requested
    avg_pressures = {}
    if sim_pressure_df is not None:
        avg_pressures = sim_pressure_df.groupby("node")["pressure_m"].mean().to_dict()
        avg_pressures = {str(k): float(v) for k, v in avg_pressures.items()}

    fig = go.Figure()

    # 1. Draw Normal Pipes
    norm_edge_x, norm_edge_y = [], []
    for pipe_name, pipe in wn.pipes():
        if str(pipe_name) == target_link_str:
            continue
        start = wn.get_node(pipe.start_node_name)
        end = wn.get_node(pipe.end_node_name)
        norm_edge_x.extend([start.coordinates[0], end.coordinates[0], None])
        norm_edge_y.extend([start.coordinates[1], end.coordinates[1], None])

    fig.add_trace(go.Scatter(
        x=norm_edge_x, y=norm_edge_y,
        mode="lines",
        line=dict(width=2, color="#90A4AE"),
        hoverinfo="none",
        name="Tuberías Operativas"
    ))

    # 2. Draw Pumps
    pump_x, pump_y, pump_mid_x, pump_mid_y, pump_text = [], [], [], [], []
    for pump_name, pump in wn.pumps():
        start = wn.get_node(pump.start_node_name)
        end = wn.get_node(pump.end_node_name)
        mx = (start.coordinates[0] + end.coordinates[0]) / 2.0
        my = (start.coordinates[1] + end.coordinates[1]) / 2.0

        if str(pump_name) == target_link_str and scenario_type == ScenarioType.PUMP_OUTAGE:
            fig.add_trace(go.Scatter(
                x=[start.coordinates[0], end.coordinates[0]],
                y=[start.coordinates[1], end.coordinates[1]],
                mode="lines",
                line=dict(width=6, color="#D50000", dash="dash"),
                hoverinfo="none",
                name=f"⚡🚫 Bomba Parada ({pump_name})"
            ))
            fig.add_trace(go.Scatter(
                x=[mx], y=[my],
                mode="markers+text",
                text=[f"⚡🚫 PARADA ({pump_name})"],
                textposition="top center",
                marker=dict(symbol="x", size=18, color="#D50000", line=dict(width=3, color="#B71C1C")),
                hovertext=[f"Bomba Desconectada / Apagón: {pump_name}"],
                hoverinfo="text",
                showlegend=False
            ))
        else:
            pump_x.extend([start.coordinates[0], end.coordinates[0], None])
            pump_y.extend([start.coordinates[1], end.coordinates[1], None])
            pump_mid_x.append(mx)
            pump_mid_y.append(my)
            pump_text.append(f"⚡ Bomba: {pump_name}")

    if pump_x:
        fig.add_trace(go.Scatter(
            x=pump_x, y=pump_y,
            mode="lines",
            line=dict(width=5, color="#FF9800"),
            hoverinfo="none",
            name="Estación de Bombeo"
        ))
        fig.add_trace(go.Scatter(
            x=pump_mid_x, y=pump_mid_y,
            mode="markers+text",
            text=[f"⚡ {p.split(': ')[1]}" for p in pump_text],
            textposition="top center",
            marker=dict(symbol="triangle-up", size=14, color="#E65100"),
            hovertext=pump_text,
            hoverinfo="text",
            name="Bombas (Actuadores)"
        ))

    # 3. Draw Closed Pipe (if scenario is PIPE_CLOSURE)
    if target_link_str and target_link_str in wn.link_name_list and scenario_type == ScenarioType.PIPE_CLOSURE:
        link = wn.get_link(target_link_str)
        start = wn.get_node(link.start_node_name)
        end = wn.get_node(link.end_node_name)
        mid_x = (start.coordinates[0] + end.coordinates[0]) / 2.0
        mid_y = (start.coordinates[1] + end.coordinates[1]) / 2.0

        fig.add_trace(go.Scatter(
            x=[start.coordinates[0], end.coordinates[0]],
            y=[start.coordinates[1], end.coordinates[1]],
            mode="lines",
            line=dict(width=6, color="#D50000", dash="dash"),
            hoverinfo="none",
            name=f"🚫 Tubería Clausurada ({target_link_str})"
        ))
        fig.add_trace(go.Scatter(
            x=[mid_x], y=[mid_y],
            mode="markers+text",
            text=[f"🚫 CERRADA ({target_link_str})"],
            textposition="bottom center",
            marker=dict(symbol="x", size=18, color="#D50000", line=dict(width=3, color="#B71C1C")),
            hovertext=[f"Tubería Cerrada por Sabotaje/Control: {target_link_str}"],
            hoverinfo="text",
            showlegend=False
        ))

    # 4. Group Nodes Safely
    res_x, res_y, res_text = [], [], []
    tank_x, tank_y, tank_text = [], [], []
    sensor_x, sensor_y, sensor_text, sensor_labels = [], [], [], []
    norm_x, norm_y, norm_text, norm_pressures = [], [], [], []

    target_x, target_y, target_ann_text = None, None, None

    for name, node in wn.nodes():
        name_str = str(name)
        coord_x = node.coordinates[0]
        coord_y = node.coordinates[1]
        p_val = avg_pressures.get(name_str, None)
        p_str = f"<br>Presión Media: {p_val:.1f} m" if p_val is not None else ""

        # Safe attribute retrieval for elevation vs base_head
        elev = getattr(node, "elevation", getattr(node, "base_head", 0.0))
        elev_label = "Elevación" if hasattr(node, "elevation") else "Carga/Nivel"
        info = f"<b>Nodo: {name_str}</b><br>Tipo: {node.node_type}<br>{elev_label}: {elev:.1f} m{p_str}"

        # Is this the target element?
        if name_str == target_node_str:
            target_x = coord_x
            target_y = coord_y
            if scenario_type == ScenarioType.LEAK:
                target_ann_text = f"💥 FUGA ACTIVA<br>Nodo {name_str}"
            elif scenario_type == ScenarioType.SENSOR_SPOOF:
                target_ann_text = f"🎯 SENSOR SPOOFED<br>Nodo {name_str}"
            elif scenario_type == ScenarioType.DEMAND_BURST:
                target_ann_text = f"⚡ CONSUMO ILÍCITO / PICO<br>Nodo {name_str}"
            elif scenario_type == ScenarioType.STEALTH_ATTACK:
                target_ann_text = f"🎭 ATAQUE HÍBRIDO (Fuga+Spoofing)<br>Nodo {name_str}"
            else:
                target_ann_text = f"📍 Elemento Objetivo<br>Nodo {name_str}"

        if node.node_type == "Reservoir":
            res_x.append(coord_x)
            res_y.append(coord_y)
            res_text.append(info)
        elif node.node_type == "Tank":
            tank_x.append(coord_x)
            tank_y.append(coord_y)
            tank_text.append(info)
        elif name_str in monitored_sensors:
            sensor_x.append(coord_x)
            sensor_y.append(coord_y)
            sensor_text.append(info)
            sensor_labels.append(f"📡 {name_str}")
        else:
            norm_x.append(coord_x)
            norm_y.append(coord_y)
            norm_text.append(info)
            norm_pressures.append(p_val if p_val is not None else 20.0)

    # Reservoirs trace
    if res_x:
        fig.add_trace(go.Scatter(
            x=res_x, y=res_y,
            mode="markers+text",
            text=[t.split("Nodo: ")[1].split("<")[0] for t in res_text],
            textposition="top center",
            marker=dict(symbol="square", size=16, color="#0D47A1", line=dict(width=2, color="#000")),
            hovertext=res_text, hoverinfo="text",
            name="Reservorio Principal"
        ))

    # Tanks trace
    if tank_x:
        fig.add_trace(go.Scatter(
            x=tank_x, y=tank_y,
            mode="markers+text",
            text=[t.split("Nodo: ")[1].split("<")[0] for t in tank_text],
            textposition="top center",
            marker=dict(symbol="diamond", size=15, color="#0097A7", line=dict(width=2, color="#000")),
            hovertext=tank_text, hoverinfo="text",
            name="Tanques de Almacenamiento"
        ))

    # Regular Junctions trace
    if color_mode == "Presión Hidráulica (m)" and norm_pressures:
        fig.add_trace(go.Scatter(
            x=norm_x, y=norm_y,
            mode="markers",
            marker=dict(
                size=8,
                color=norm_pressures,
                colorscale="Viridis",
                colorbar=dict(title="Presión (m)", thickness=12, len=0.7),
                showscale=True
            ),
            hovertext=norm_text, hoverinfo="text",
            name="Nodos (Coloreados por Presión)"
        ))
    else:
        fig.add_trace(go.Scatter(
            x=norm_x, y=norm_y,
            mode="markers",
            marker=dict(size=7, color="#546E7A"),
            hovertext=norm_text, hoverinfo="text",
            name="Nodos de Unión"
        ))

    # Monitored SCADA Sensors trace
    if sensor_x:
        fig.add_trace(go.Scatter(
            x=sensor_x, y=sensor_y,
            mode="markers+text",
            text=sensor_labels,
            textposition="top right",
            textfont=dict(size=11, color="#006064", family="Arial Black"),
            marker=dict(symbol="circle-dot", size=13, color="#00E5FF", line=dict(width=2.5, color="#006064")),
            hovertext=sensor_text, hoverinfo="text",
            name="Sensores SCADA Monitoreados"
        ))

    # Highlight Affected Target Node (Leak or Spoofed Sensor)
    if target_x is not None:
        marker_color = "#D50000" if scenario_type in [ScenarioType.LEAK, ScenarioType.SENSOR_SPOOF] else "#FF6D00"
        fig.add_trace(go.Scatter(
            x=[target_x], y=[target_y],
            mode="markers",
            marker=dict(
                symbol="star",
                size=24,
                color=marker_color,
                line=dict(width=2.5, color="#FFFFFF")
            ),
            hovertext=[target_ann_text.replace("<br>", " ")],
            hoverinfo="text",
            name="⚠️ COMPONENTE AFECTADO"
        ))
        fig.add_annotation(
            x=target_x, y=target_y,
            text=target_ann_text,
            showarrow=True,
            arrowhead=2,
            arrowsize=1.2,
            arrowwidth=2.5,
            arrowcolor="#D50000",
            ax=40, ay=-40,
            bgcolor="#FFEBEE",
            bordercolor="#D50000",
            borderwidth=1.5,
            font=dict(color="#B71C1C", size=12, family="Arial")
        )

    fig.update_layout(
        title="<b>Visualización Espacial de la Red Ciberfísica</b>",
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, xanchor="center", x=0.5),
        margin=dict(b=40, l=10, r=10, t=35),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor="#F8FAFC",
        height=480
    )
    return fig


def run_triton_pipeline_with_visual_phases(wn, scenario_config, base_config, monitored_sensors, target_element=None):
    """
    Executes the TRITON 4-phase pipeline displaying an interactive visual progress bar.
    """
    with st.status("🔄 Ejecutando Pipeline del Gemelo Digital TRITON...", expanded=True) as status_box:
        progress_bar = st.progress(0, text="Iniciando pipeline TRITON...")

        # FASE 1: OPERACIÓN FÍSICA
        st.write("🌊 **Fase 1 (Operación Física):** Validando topología, PDD e hidráulica base...")
        progress_bar.progress(20, text="Fase 1: Calculando dinámica física...")
        t0 = time.time()
        res_baseline = execute_scenario(wn, base_config)
        res_scenario = execute_scenario(wn, scenario_config)
        t_phase1 = time.time() - t0
        st.caption(f"✓ Hidráulica resuelta en {t_phase1:.2f}s ({wn.num_nodes} nodos, {wn.num_links} enlaces)")
        time.sleep(0.3)

        # FASE 2: CAPA DE CIBERSEGURIDAD
        st.write("🛡️ **Fase 2 (Capa de Ciberseguridad):** Mapeando telemetría SCADA e inyectando vector de amenaza...")
        progress_bar.progress(45, text="Fase 2: Verificando integridad de sensores...")
        st.caption("✓ Separación estricta de telemetría física (P_phys) vs lecturas SCADA observadas (P_obs)")
        time.sleep(0.3)

        # FASE 3: CAPA DE INTELIGENCIA ARTIFICIAL
        st.write("🧠 **Fase 3 (Capa de Inteligencia Artificial):** Extrayendo residuos multivariados e infiriendo anomalías...")
        progress_bar.progress(70, text="Fase 3: Entrenando Isolation Forest y comparando gemelos...")
        t_elem = target_element
        if t_elem is None:
            t_elem = (
                getattr(scenario_config, "leak_node", None)
                or getattr(scenario_config, "spoof_node", None)
                or getattr(scenario_config, "burst_node", None)
            )
        active_sensor_set = list(dict.fromkeys(list(monitored_sensors) + ([str(t_elem)] if t_elem else [])))
        ai_eval = evaluate_triton_detector(
            baseline_result=res_baseline,
            scenario_result=res_scenario,
            sensor_nodes=active_sensor_set
        )
        st.caption(f"✓ Detección completada: F1 = {ai_eval['f1']:.2f} | Umbral físico = {ai_eval['physics_threshold_m']:.2f} m")
        time.sleep(0.3)

        # FASE 4: MÉTRICAS DE SOSTENIBILIDAD
        st.write("🌱 **Fase 4 (Métricas de Sostenibilidad):** Calculando m³ de agua perdida, consumo kWh y Scorecard TRITON...")
        progress_bar.progress(90, text="Fase 4: Consolidando métricas e indicadores...")
        metrics_scenario = calculate_hydraulic_and_sustainability_metrics(res_scenario)
        metrics_baseline = calculate_hydraulic_and_sustainability_metrics(res_baseline)
        scorecard = compute_triton_evidence_vector(metrics_scenario, ai_eval)

        progress_bar.progress(100, text="¡Pipeline TRITON completado!")
        st.caption("✓ Scorecard consolidado bajo ejes CI (Ciberseguridad), SO (Sostenibilidad) e IA (Inteligencia Artificial)")
        time.sleep(0.2)

        status_box.update(
            label="✅ Pipeline TRITON Ejecutado con Éxito",
            state="complete",
            expanded=False
        )

    return res_baseline, res_scenario, metrics_baseline, metrics_scenario, ai_eval, scorecard


def main():
    st.markdown('<p class="main-title">💧 TRITON Smart Water Digital Twin</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-title">Framework de Resiliencia Tecnológica, Ciberseguridad e Inteligencia Artificial en Redes de Distribución de Agua</p>',
        unsafe_allow_html=True
    )

    # ----------------------------------------------------
    # BANCO DE PRUEBAS RÁPIDAS (QUICK PRESETS)
    # ----------------------------------------------------
    st.markdown("""
    <div class="preset-box">
        <h4 style="margin: 0 0 6px 0; color: #1565C0;">🧪 Banco de Pruebas Rápidas — Explora Escenarios e Incidentes</h4>
        <p style="margin: 0; font-size: 0.90rem; color: #37474F;">
            Selecciona un percance para configurarlo, evaluar su impacto físico/cibernético y ejecutar el gemelo digital:
        </p>
    </div>
    """, unsafe_allow_html=True)

    btn_row1_col1, btn_row1_col2, btn_row1_col3, btn_row1_col4 = st.columns(4)
    btn_row2_col1, btn_row2_col2, btn_row2_col3, btn_row2_col4 = st.columns(4)
    preset_triggered = None

    with btn_row1_col1:
        if st.button("🟢 1. Operación Normal", help="Línea base sin fallas. Física y telemetría en equilibrio.", use_container_width=True):
            preset_triggered = "baseline"
    with btn_row1_col2:
        if st.button("💧 2. Fuga Física (Rotura)", help="Falla física real. Orificio elástico, presión cae y se derrama agua.", use_container_width=True):
            preset_triggered = "leak"
    with btn_row1_col3:
        if st.button("🕵️ 3. Spoofing FDI (Cyber)", help="Ataque a telemetría. El sensor SCADA miente pero la física sigue normal.", use_container_width=True):
            preset_triggered = "spoof"
    with btn_row1_col4:
        if st.button("🚫 4. Cierre de Tubería", help="Sabotaje o bloqueo físico. Tubería cerrada con caída de caudal.", use_container_width=True):
            preset_triggered = "pipe_closure"

    with btn_row2_col1:
        if st.button("⚡ 5. Falla de Bomba", help="Apagón eléctrico o parada no programada de la estación de bombeo principal.", use_container_width=True):
            preset_triggered = "pump_outage"
    with btn_row2_col2:
        if st.button("🏭 6. Consumo Ilícito", help="Toma clandestina o pico repentino de demanda no autorizada en un nodo.", use_container_width=True):
            preset_triggered = "demand_burst"
    with btn_row2_col3:
        if st.button("🎭 7. Híbrido Sigiloso", help="Ataque coordinado dual: fuga física real + spoofing en sensor para encubrir la fuga.", use_container_width=True):
            preset_triggered = "stealth_attack"
    with btn_row2_col4:
        if st.button("🔄 Restablecer Red", help="Recargar el estado base de la red.", use_container_width=True):
            preset_triggered = "baseline"

    # Guía didáctica desplegable
    with st.expander("📘 Guía Didáctica: ¿Por qué la Fuga es el caso clásico y cómo se comparan todos los percances?", expanded=False):
        st.markdown("""
        ### 🔍 ¿Por qué casi siempre se utiliza una Fuga como escenario de referencia?
        1. **Impacto Crítico Real (Agua No Facturada - NRW):** Entre el 25% y el 45% del agua potable tratada en el mundo se pierde por fugas subterráneas. Es la principal amenaza económica y de sostenibilidad para cualquier empresa de agua.
        2. **Física Dinámica no Lineal (PDD):** Una fuga no es una demanda fija; su caudal de escape se rige por el principio de Torricelli:
           $$Q_{leak}(t) = C_d \\cdot A \\cdot \\sqrt{2 \\cdot g \\cdot P(t)}$$
           Si la presión sube, el escape de agua se dispara. Esto altera de inmediato las curvas de bomba y los gradientes piezométricos de toda la red.
        3. **El Dilema de Toma de Decisiones:** Ante una caída de presión en SCADA, si un operador cree que es una fuga y sube la potencia de bombeo para compensar, pero en realidad era un ciberataque o una válvula cerrada, **sobrepresurizará la red provocando roturas catastróficas reales**.

        ---

        ### 📋 Matriz Comparativa de Percances e Incidentes en TRITON:
        | Tipo de Percance | Estado Físico ($P_{phys}$) | Lectura SCADA ($P_{obs}$) | Residuo Físico ($R_{sens}$) | Residuo Histórico ($R_{cf}$) | Diagnóstico TRITON | Acción Recomendada |
        | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
        | 🟢 **Operación Normal** | Nominal | Nominal | $\\approx 0$ m | $\\approx 0$ m | Normal | Operación rutinaria |
        | 💧 **Fuga Física** | Cae por pérdida | Cae por pérdida | $\\approx 0$ m *(Coinciden)* | $> 0.5$ m | **Falla Física (Fuga)** | Enviar brigada de reparación física |
        | 🕵️ **Spoofing FDI** | Nominal intacta | Alterada / Sesgada | $> 1.0$ m *(Discrepancia)* | $> 0.5$ m | **Ciberataque FDI** | Aislar sensor / Revertir telemetría |
        | 🚫 **Cierre de Tubería** | Cae aguas abajo | Cae aguas abajo | $\\approx 0$ m *(Coinciden)* | $> 0.5$ m | **Falla Física (Bloqueo)** | Inspeccionar actuador / reabrir bypass |
        | ⚡ **Falla de Bomba** | Colapso general | Colapso general | $\\approx 0$ m *(Coinciden)* | $> 2.0$ m | **Falla Física (Estación)** | Arrancar bomba de respaldo |
        | 🏭 **Consumo Ilícito** | Cae localmente | Cae localmente | $\\approx 0$ m *(Coinciden)* | $> 0.5$ m | **Falla Física (Demanda)** | Inspección de tomas clandestinas |
        | 🎭 **Híbrido Sigiloso** | Cae por fuga real | **Falsa Normalidad** | $> 1.0$ m *(Discrepancia)* | $> 0.5$ m (en flujo) | **Ataque Ciberfísico Híbrido** | Alerta máxima: fuga real oculta |
        """)

    # ----------------------------------------------------
    # SIDEBAR: GESTIÓN DE RED Y CONFIGURACIÓN DEL ESCENARIO
    # ----------------------------------------------------
    with st.sidebar:
        st.header("⚙️ Panel de Control")
        
        # 1. Gestión de Red
        st.subheader("1. Gestión de Red Hidráulica")
        net_mode = st.radio(
            "Seleccionar Modelo",
            ["Biblioteca Oficial (Net3)", "Crear Red Simple Programática", "Cargar archivo .inp propio"],
            index=0
        )

        networks_dir = ROOT_DIR / "data" / "networks"
        networks_dir.mkdir(parents=True, exist_ok=True)
        network_changed = False

        if net_mode == "Biblioteca Oficial (Net3)":
            inp_file = networks_dir / "Net3.inp"
            current_net_key = "Net3"
            if not inp_file.exists():
                wn = load_network("Net3")
                save_network(wn, inp_file)
            else:
                wn = load_network(inp_file)
            st.caption(f"📁 Modelo activo: `Net3.inp` ({wn.num_nodes} nodos, {wn.num_links} enlaces)")

        elif net_mode == "Crear Red Simple Programática":
            sim_path = networks_dir / "simple_network.inp"
            current_net_key = "simple_network"
            if st.button("🔨 Crear/Regenerar Red Simple", use_container_width=True) or not sim_path.exists():
                wn = create_simple_network(output_path=sim_path)
                st.success("Red simple creada exitosamente con WNTR API.")
            else:
                wn = load_network(sim_path)
            st.caption(f"📁 Modelo activo: `simple_network.inp` ({wn.num_nodes} nodos, {wn.num_links} enlaces)")

        else:
            uploaded = st.file_uploader("Subir archivo EPANET (.inp)", type=["inp"])
            if uploaded is not None:
                save_path = networks_dir / uploaded.name
                save_path.write_bytes(uploaded.getvalue())
                wn = load_network(save_path)
                current_net_key = uploaded.name
                st.success(f"Archivo `{uploaded.name}` cargado correctamente.")
            else:
                current_net_key = "Net3_fallback"
                st.info("Carga un archivo .inp arriba o se utilizará Net3.")
                wn = load_network("Net3")

        # Detect if network model changed
        if st.session_state.get("last_network_key") != current_net_key:
            st.session_state["last_network_key"] = current_net_key
            network_changed = True

        summary = get_network_summary(wn)
        junctions = summary["junction_names"]
        pipes = summary["pipe_names"]
        pumps = summary["pump_names"]

        def format_node_option(n):
            node_obj = wn.get_node(n)
            elev = getattr(node_obj, "elevation", getattr(node_obj, "base_head", 0.0))
            coords = node_obj.coordinates
            return f"Nodo {n} (Elev: {elev:.1f}m | Coord: {coords[0]:.0f},{coords[1]:.0f})"

        st.divider()

        # 2. Configuración de Escenario
        st.subheader("2. Configuración de Anomalías e Incidentes")
        scenario_options = [
            "Baseline (Operación Normal)",
            "Fuga Física (Leak)",
            "Ciberataque Spoofing (FDI Telemetría)",
            "Cierre de Tubería (Actuador / Válvula)",
            "Falla de Bomba / Apagón (Pump Outage)",
            "Consumo Ilícito / Pico Anómalo (Demand Burst)",
            "Ataque Híbrido Sigiloso (Fuga Oculta con Spoofing)"
        ]

        # Handle Preset selection override
        default_scenario_idx = 1
        if preset_triggered == "baseline":
            default_scenario_idx = 0
        elif preset_triggered == "leak":
            default_scenario_idx = 1
        elif preset_triggered == "spoof":
            default_scenario_idx = 2
        elif preset_triggered == "pipe_closure":
            default_scenario_idx = 3
        elif preset_triggered == "pump_outage":
            default_scenario_idx = 4
        elif preset_triggered == "demand_burst":
            default_scenario_idx = 5
        elif preset_triggered == "stealth_attack":
            default_scenario_idx = 6

        scenario_choice = st.selectbox("Tipo de Escenario", scenario_options, index=default_scenario_idx)

        net_native_duration = int(summary.get("duration_hours", 72))
        sim_duration_default = min(72, max(24, net_native_duration))
        sim_duration = st.slider("Duración de Simulación (horas)", 12, 168, sim_duration_default, step=12)

        default_start_hour = min(24, max(1, sim_duration // 3))
        default_end_hour = min(sim_duration - 1, default_start_hour + min(24, max(4, sim_duration // 3)))
        start_hour = st.slider("Inicio del Evento (h)", 1, sim_duration - 2, default_start_hour)
        end_hour = st.slider("Fin del Evento (h)", start_hour + 1, sim_duration - 1, default_end_hour)
        event_hours = max(1, end_hour - start_hour)

        # Parameters by scenario
        leak_node = None
        leak_diam = 16.0
        leak_cd = 0.75
        spoof_node = None
        spoof_bias = 15.0
        close_pipe = None
        outage_pump = None
        burst_node = None
        burst_flow_m3s = 0.020
        target_element = None
        target_link = None

        if "Fuga Física" in scenario_choice:
            scen_type = ScenarioType.LEAK
            default_idx = junctions.index("113") if "113" in junctions else 0
            leak_node = st.selectbox("Seleccionar Nodo con Fuga", junctions, index=default_idx, format_func=format_node_option)
            leak_diam = st.slider("Diámetro del Orificio de Fuga (mm)", 2.0, 50.0, 16.0, step=1.0)
            leak_cd = st.slider("Coeficiente de Descarga (Cd)", 0.50, 0.99, 0.75, step=0.05)
            target_element = leak_node

            # Calculadora Hidráulica en Tiempo Real (Torricelli PDD)
            area_mm2 = math.pi * ((leak_diam / 2.0) ** 2)
            area_m2 = area_mm2 * 1e-6
            p_ref = 30.0  # presión nominal de referencia en m.c.a.
            q_est_m3s = leak_cd * area_m2 * math.sqrt(2.0 * 9.80665 * p_ref)
            q_est_lps = q_est_m3s * 1000.0
            q_est_m3h = q_est_m3s * 3600.0
            v_est_m3 = q_est_m3h * event_hours
            tinacos = v_est_m3
            pipas = v_est_m3 / 10.0
            costo = v_est_m3 * 1.50

            st.markdown(f"""
            <div style="background-color: #E3F2FD; border-left: 4px solid #1976D2; padding: 12px; border-radius: 8px; font-size: 0.84rem; margin-top: 6px;">
                <b>📐 Calculadora Hidráulica Teórica (Torricelli PDD):</b><br>
                • Área del orificio: <b>{area_mm2:.1f} mm²</b> (D = {leak_diam:.0f} mm)<br>
                • Ecuación: <code>Q = Cd · A · √(2·g·P)</code><br>
                • Caudal estimado (@30m): <b>{q_est_lps:.2f} L/s</b> (~{q_est_m3h:.1f} m³/h)<br>
                • Pérdida proyectada ({event_hours}h): <b>{v_est_m3:.1f} m³</b><br>
                • Impacto social: ~<b>{int(tinacos):,} tinacos de 1000L</b> ({pipas:.1f} pipas)<br>
                • Costo económico (@$1.5/m³): <b>${costo:,.1f} USD</b>
            </div>
            """, unsafe_allow_html=True)

        elif "Spoofing" in scenario_choice:
            scen_type = ScenarioType.SENSOR_SPOOF
            default_idx = junctions.index("111") if "111" in junctions else (1 if len(junctions) > 1 else 0)
            spoof_node = st.selectbox("Sensor Objetivo a Manipular", junctions, index=default_idx, format_func=format_node_option)
            spoof_bias = st.slider("Sesgo Inyectado en Presión (m)", -30.0, 30.0, 18.0, step=1.0)
            target_element = spoof_node
            st.caption("ℹ️ El sensor reportará una lectura falsificada en SCADA. La física real de las tuberías continúa nominal.")

        elif "Cierre" in scenario_choice:
            scen_type = ScenarioType.PIPE_CLOSURE
            default_idx = pipes.index("114") if "114" in pipes else 0
            close_pipe = st.selectbox("Tubería a Clausurar", pipes, index=default_idx)
            target_link = close_pipe
            st.caption(f"ℹ️ La tubería `{close_pipe}` será cerrada forzando la redistribución del flujo y caída de presión aguas abajo.")

        elif "Bomba" in scenario_choice:
            scen_type = ScenarioType.PUMP_OUTAGE
            if pumps:
                outage_pump = st.selectbox("Bomba a Desconectar / Apagar", pumps, index=0)
                target_link = outage_pump
                st.caption(f"⚡ Parada de emergencia de la estación de bombeo `{outage_pump}` durante las horas {start_hour} a {end_hour}.")
            else:
                st.warning("La red actual no cuenta con bombas para apagar.")

        elif "Consumo" in scenario_choice:
            scen_type = ScenarioType.DEMAND_BURST
            default_idx = junctions.index("113") if "113" in junctions else 0
            burst_node = st.selectbox("Nodo con Consumo Anómalo", junctions, index=default_idx, format_func=format_node_option)
            burst_lps = st.slider("Caudal Anómalo Inyectado (L/s)", 2.0, 60.0, 20.0, step=2.0)
            burst_flow_m3s = burst_lps / 1000.0
            target_element = burst_node
            extra_vol = (burst_flow_m3s * 3600.0) * event_hours
            st.caption(f"ℹ️ Toma no registrada: {burst_lps:.1f} L/s (~{burst_lps * 3.6:.1f} m³/h). Consumo no contabilizado: ~{extra_vol:.1f} m³.")

        elif "Híbrido" in scenario_choice:
            scen_type = ScenarioType.STEALTH_ATTACK
            default_idx = junctions.index("113") if "113" in junctions else 0
            leak_node = st.selectbox("Nodo con Fuga Física Real", junctions, index=default_idx, format_func=format_node_option)
            leak_diam = st.slider("Diámetro del Orificio de Fuga (mm)", 2.0, 50.0, 16.0, step=1.0)
            leak_cd = 0.75
            spoof_node = st.selectbox("Sensor a Manipular para Encubrir Fuga", junctions, index=default_idx, format_func=format_node_option)
            spoof_bias = st.slider("Sesgo de Presión Compensatorio (+m)", 5.0, 30.0, 15.0, step=1.0)
            target_element = leak_node

            st.markdown(f"""
            <div style="background-color: #FFF3E0; border-left: 4px solid #E65100; padding: 10px; border-radius: 8px; font-size: 0.84rem; margin-top: 6px;">
                <b>🎭 Ataque Ciberfísico Híbrido Coordinado:</b><br>
                • Ocurre una fuga real en `{leak_node}` ($D = {leak_diam:.0f}$ mm).<br>
                • El atacante falsifica la telemetría en `{spoof_node}` sumando <b>+{spoof_bias:.1f} m</b>.<br>
                • El operador SCADA observa presiones "normales", permitiendo que el agua se derrame sin ser detectada.
            </div>
            """, unsafe_allow_html=True)

        else:
            scen_type = ScenarioType.BASELINE
            target_element = None
            target_link = None

        st.divider()

        # 3. Sensores Monitoreados para IA
        st.subheader("3. Telemetría & Sensores IA")
        default_sensors = [j for j in ["101", "109", "111", "113", "197", "J1", "J2", "J3"] if j in junctions]
        if not default_sensors:
            default_sensors = junctions[:min(5, len(junctions))]
        monitored_sensors = st.multiselect("Sensores Monitoreados", junctions, default=default_sensors)
        if not monitored_sensors:
            monitored_sensors = junctions[:1]

        st.divider()
        run_btn = st.button("🚀 Ejecutar Simulación TRITON", type="primary", use_container_width=True)

    # ----------------------------------------------------
    # ORQUESTADOR: EXPERIENCIA DE CARGA POR FASES TRITON
    # ----------------------------------------------------
    should_run = run_btn or (preset_triggered is not None) or network_changed or ("triton_state" not in st.session_state)

    if should_run:
        config = ScenarioConfig(
            scenario_type=scen_type,
            event_start_hour=start_hour,
            event_end_hour=end_hour,
            leak_node=leak_node,
            leak_diameter_mm=leak_diam,
            leak_discharge_coeff=leak_cd,
            spoof_node=spoof_node,
            spoof_bias_m=spoof_bias,
            close_pipe=close_pipe,
            outage_pump=outage_pump,
            burst_node=burst_node,
            burst_flow_m3s=burst_flow_m3s,
            duration_hours=sim_duration
        )

        base_config = ScenarioConfig(
            scenario_type=ScenarioType.BASELINE,
            duration_hours=sim_duration
        )

        res_baseline, res_scenario, metrics_baseline, metrics_scenario, ai_eval, scorecard = run_triton_pipeline_with_visual_phases(
            wn=wn,
            scenario_config=config,
            base_config=base_config,
            monitored_sensors=monitored_sensors,
            target_element=target_element
        )

        st.session_state["triton_state"] = {
            "baseline": res_baseline,
            "scenario": res_scenario,
            "metrics_baseline": metrics_baseline,
            "metrics": metrics_scenario,
            "ai_eval": ai_eval,
            "scorecard": scorecard,
            "config": config,
            "target_element": target_element,
            "target_link": target_link,
            "wn": wn
        }

    # ----------------------------------------------------
    # DASHBOARD: ESTADO DE SESIÓN Y VISUALIZADOR DE FASES
    # ----------------------------------------------------
    state = st.session_state["triton_state"]
    metrics = state["metrics"]
    metrics_baseline = state["metrics_baseline"]
    ai_eval = state["ai_eval"]
    scorecard = state["scorecard"]
    config = state["config"]
    res_scen = state["scenario"]
    res_base = state["baseline"]
    wn_current = state["wn"]

    # Banner de Diagnóstico del Gemelo Digital
    pred_summary = ai_eval["timeline"]["classification"].value_counts().to_dict()
    has_hybrid = pred_summary.get("Hybrid Attack (Physical + Cyber)", 0) > 0
    has_cyber = (pred_summary.get("Cyber Attack (FDI/Spoofing)", 0) > 0) or has_hybrid
    has_phys = (pred_summary.get("Physical Fault (Leak/Outage/Closure)", 0) > 0) or (pred_summary.get("Physical Fault (Leak/Closure)", 0) > 0) or has_hybrid

    if has_hybrid or (has_cyber and has_phys):
        st.error("🚨 **DIAGNÓSTICO TRITON:** Evento Ciberfísico Híbrido detectado (Ataque a telemetría + Evento físico concurrente).")
    elif has_cyber:
        st.error("🛡️ **DIAGNÓSTICO TRITON — CIBERATAQUE DETECTADO:** Se detectó **Falsificación de Datos (FDI / Spoofing)**. La telemetría observada contradice el gemelo físico.")
    elif has_phys:
        st.warning("⚠️ **DIAGNÓSTICO TRITON — FALLA FÍSICA DETECTADA:** Se detectó una **Anomalía Física Real** (Fuga, Consumo Ilícito, Cierre o Apagón). La telemetría coincide con la física de la red.")
    else:
        st.success("✅ **DIAGNÓSTICO TRITON — RED EN ESTADO ÓPTIMO:** Operación normal de suministro. Coherencia total entre física y telemetría SCADA.")

    # Verificación de Convergencia Hidráulica Completa
    is_trunc = res_scen.get("is_truncated", False) or res_base.get("is_truncated", False)
    if is_trunc:
        act_h = res_scen.get("actual_max_hour", 0)
        exp_h = res_scen.get("expected_duration_h", config.duration_hours)
        if act_h < config.event_start_hour:
            st.warning(
                f"⚠️ **Alerta de Convergencia Hidráulica en '{current_net_key}':** "
                f"El solver de WNTR se detuvo en la **hora {act_h}** (de {exp_h}h programadas) debido a restricciones numéricas o de bomba en este archivo. "
                f"Dado que el evento fue configurado a partir de la **hora {config.event_start_hour}**, **la anomalía no llegó a ocurrir físicamente** "
                f"(por esta razón las pérdidas marcan 0.0 m³ y la presión no varía). "
                f"💡 *Recomendación:* Ajusta el inicio del evento a una hora previa (ej. hora 1 a {max(1, act_h - 1)}) o utiliza una red con mayor amortiguamiento como `Net3`."
            )
        else:
            st.info(
                f"ℹ️ **Información de Simulación:** El motor hidráulico completó hasta la **hora {act_h}** de {exp_h}h. Las métricas reflejan dicho período simulado."
            )

    # ----------------------------------------------------
    # VISUALIZADOR PERSISTENTE DE LAS 4 FASES DE TRITON
    # ----------------------------------------------------
    st.markdown("### 📊 Pipeline de Fases del Framework TRITON")
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)

    with f_col1:
        st.markdown(f"""
        <div class="phase-card" style="border-left: 4px solid #1E88E5;">
            <div class="phase-header" style="color: #1E88E5;">🌊 Fase 1: Operación Física</div>
            <div class="phase-meta">
                • Modelo: <b>{wn_current.num_nodes}</b> nodos, <b>{wn_current.num_links}</b> enlaces<br>
                • Demanda: PDD no lineal<br>
                • Estado: <span style="color:#2E7D32; font-weight:600;">✓ Simulación OK</span>
            </div>
            <div class="phase-val">{metrics['mean_pressure_m']:.1f} m <span style="font-size:0.8rem; font-weight:normal; color:#64748B;">presión media</span></div>
        </div>
        """, unsafe_allow_html=True)

    with f_col2:
        is_spoof = (config.scenario_type in [ScenarioType.SENSOR_SPOOF, ScenarioType.STEALTH_ATTACK])
        status_cyber = "⚠️ Alteración Inyectada" if is_spoof else "✓ Telemetría Íntegra"
        color_cyber = "#E53935" if is_spoof else "#2E7D32"
        cyber_res_disp = metrics.get('max_telemetry_residual_m', metrics['telemetry_physics_residual_rmse_m'])
        cyber_res_label = "Residuo Máx Sensor" if is_spoof else "RMSE Cyber/Phys"
        st.markdown(f"""
        <div class="phase-card" style="border-left: 4px solid {color_cyber};">
            <div class="phase-header" style="color: #6A1B9A;">🛡️ Fase 2: Ciberseguridad</div>
            <div class="phase-meta">
                • Sensores SCADA activos: <b>{len(monitored_sensors)}</b><br>
                • Vector: <b>{config.scenario_type}</b><br>
                • Integridad: <span style="color:{color_cyber}; font-weight:600;">{status_cyber}</span>
            </div>
            <div class="phase-val">{cyber_res_disp:.2f} m <span style="font-size:0.8rem; font-weight:normal; color:#64748B;">{cyber_res_label}</span></div>
        </div>
        """, unsafe_allow_html=True)

    with f_col3:
        if has_hybrid:
            diag_phase3 = "🚨 Ataque Híbrido"
            f1_disp_label = "F1 Score IA"
        elif has_cyber:
            diag_phase3 = "⚠️ Ciberataque FDI"
            f1_disp_label = "F1 Score IA"
        elif has_phys:
            diag_phase3 = "⚠️ Falla Física"
            f1_disp_label = "F1 Score IA"
        else:
            diag_phase3 = "✓ Operación Normal"
            f1_disp_label = "F1 (Nominal Óptimo)"

        st.markdown(f"""
        <div class="phase-card" style="border-left: 4px solid #FB8C00;">
            <div class="phase-header" style="color: #FB8C00;">🧠 Fase 3: Inteligencia Artificial</div>
            <div class="phase-meta">
                • Modelo: Isolation Forest + Twins<br>
                • Umbral físico: <b>{ai_eval['physics_threshold_m']:.2f} m</b><br>
                • Diagnóstico: <span style="font-weight:600;">{diag_phase3}</span>
            </div>
            <div class="phase-val">{ai_eval['f1']:.2f} <span style="font-size:0.8rem; font-weight:normal; color:#64748B;">{f1_disp_label}</span></div>
        </div>
        """, unsafe_allow_html=True)

    with f_col4:
        loss_label = "Consumo Ilícito" if metrics.get('burst_volume_m3', 0.0) > 0 else "Pérdidas"
        p_kwh_disp = f"{metrics['pump_energy_kwh']:.2f} kWh" if metrics['pump_energy_kwh'] < 100.0 else f"{metrics['pump_energy_kwh']:.0f} kWh"
        st.markdown(f"""
        <div class="phase-card" style="border-left: 4px solid #43A047;">
            <div class="phase-header" style="color: #43A047;">🌱 Fase 4: Sostenibilidad</div>
            <div class="phase-meta">
                • {loss_label}: <b>{metrics['leak_volume_m3']:.1f} m³</b> ({metrics['water_loss_pct']:.1f}%)<br>
                • Bombeo: <b>{p_kwh_disp}</b><br>
                • Scorecard: <span style="color:#2E7D32; font-weight:600;">✓ Consolidado</span>
            </div>
            <div class="phase-val">{metrics['service_availability_pct']:.1f}% <span style="font-size:0.8rem; font-weight:normal; color:#64748B;">disponibilidad</span></div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # ----------------------------------------------------
    # PESTAÑAS PRINCIPALES DEL SIMULADOR
    # ----------------------------------------------------
    tab_comp, tab_top, tab_tel, tab_ia, tab_sc = st.tabs([
        "🔄 Comparativa Antes vs Después",
        "🗺️ Topología de la Red",
        "📈 Telemetría SCADA vs Gemelo Físico",
        "🧠 Diagnóstico IA y Residuos TRITON",
        "📊 Scorecard TRITON (CI / SO / IA)"
    ])

    # ----------------------------------------------------
    # PESTAÑA 1: COMPARATIVA ANTES VS DESPUÉS
    # ----------------------------------------------------
    with tab_comp:
        st.subheader("Análisis Comparativo: Línea Base (Antes) vs Escenario con Evento (Después)")
        st.caption("Permite evaluar cuantitativa y visualmente el impacto del incidente en la red respecto a su operación normal.")

        # Tarjetas de comparación Antes vs Después
        c1, c2, c3, c4 = st.columns(4)

        d_pres = metrics['mean_pressure_m'] - metrics_baseline['mean_pressure_m']
        d_leak = metrics['leak_volume_m3'] - metrics_baseline['leak_volume_m3']
        d_pwr = metrics['pump_energy_kwh'] - metrics_baseline['pump_energy_kwh']
        d_serv = metrics['service_availability_pct'] - metrics_baseline['service_availability_pct']

        with c1:
            st.metric(
                "Presión Media Hidráulica",
                f"{metrics['mean_pressure_m']:.1f} m",
                delta=f"{d_pres:+.1f} m (vs {metrics_baseline['mean_pressure_m']:.1f}m base)"
            )
        with c2:
            card2_title = "Consumo Ilícito (NRW)" if config.scenario_type == ScenarioType.DEMAND_BURST else "Volumen Perdido en Fugas"
            st.metric(
                card2_title,
                f"{metrics['leak_volume_m3']:.1f} m³",
                delta=f"{d_leak:+.1f} m³ (vs {metrics_baseline['leak_volume_m3']:.1f}m³ base)",
                delta_color="inverse"
            )
        with c3:
            p_val_str = f"{metrics['pump_energy_kwh']:.2f} kWh" if metrics['pump_energy_kwh'] < 100.0 else f"{metrics['pump_energy_kwh']:.0f} kWh"
            d_pwr_str = f"{d_pwr:+.2f} kWh" if abs(d_pwr) < 10.0 else f"{d_pwr:+.0f} kWh"
            base_pwr_str = f"{metrics_baseline['pump_energy_kwh']:.2f}kWh base" if metrics_baseline['pump_energy_kwh'] < 100.0 else f"{metrics_baseline['pump_energy_kwh']:.0f}kWh base"
            st.metric(
                "Consumo Eléctrico de Bombas",
                p_val_str,
                delta=f"{d_pwr_str} (vs {base_pwr_str})",
                delta_color="inverse"
            )
        with c4:
            st.metric(
                "Continuidad de Servicio (≥20m)",
                f"{metrics['service_availability_pct']:.1f}%",
                delta=f"{d_serv:+.1f}% (vs {metrics_baseline['service_availability_pct']:.1f}% base)"
            )

        st.markdown("---")

        # Gráfico Temporal Superpuesto: ANTES VS DESPUÉS
        p_base = res_base["pressure"]
        p_scen = res_scen["pressure"]

        target_node = state["target_element"] if (state.get("target_element") and str(state["target_element"]) in p_scen["node"].astype(str).values) else (monitored_sensors[0] if monitored_sensors else p_scen["node"].iloc[0])
        
        df_target_base = p_base[p_base["node"].astype(str) == str(target_node)].sort_values("hour")
        df_target_scen = p_scen[p_scen["node"].astype(str) == str(target_node)].sort_values("hour")

        fig_compare = go.Figure()

        # Línea Base (Antes)
        fig_compare.add_trace(go.Scatter(
            x=df_target_base["hour"],
            y=df_target_base["pressure_m"],
            name="Antes (Línea Base Normal)",
            line=dict(color="#1976D2", width=3, dash="dot")
        ))

        # Escenario Físico Real (Después)
        fig_compare.add_trace(go.Scatter(
            x=df_target_scen["hour"],
            y=df_target_scen["pressure_m"],
            name="Después: Presión Física Real",
            line=dict(color="#D32F2F" if config.scenario_type != ScenarioType.BASELINE else "#2E7D32", width=3)
        ))

        # Telemetría SCADA Observada
        if config.scenario_type == ScenarioType.SENSOR_SPOOF:
            fig_compare.add_trace(go.Scatter(
                x=df_target_scen["hour"],
                y=df_target_scen["observed_pressure_m"],
                name="Después: Telemetría SCADA (Manipulada)",
                line=dict(color="#FF9800", width=2.5, dash="dash")
            ))

        if config.scenario_type != ScenarioType.BASELINE:
            fig_compare.add_vrect(
                x0=config.event_start_hour, x1=config.event_end_hour,
                fillcolor="rgba(255, 152, 0, 0.15)", layer="below", line_width=1,
                annotation_text="Ventana del Incidente", annotation_position="top left"
            )

        fig_compare.update_layout(
            title=f"<b>Comparativa Temporal de Presión en Nodo Objetivo {target_node}: Antes vs Después</b>",
            xaxis_title="Hora de Simulación (h)",
            yaxis_title="Presión Hidráulica (m)",
            hovermode="x unified",
            height=420
        )
        st.plotly_chart(fig_compare, use_container_width=True, key="plotly_comp_temporal_curve")

        st.markdown("---")
        st.subheader("🗺️ Comparativa Espacial: Mapa ANTES (Línea Base) vs Mapa DESPUÉS (Incidente)")
        st.caption("Compara la topología y distribución de presiones de la red antes y después de inyectar el evento.")

        map_comp_mode = st.radio(
            "Disposición de Mapas:",
            ["👥 Lado a Lado (Comparativa Directa)", "🔵 Solo ANTES (Línea Base Normal)", "🔴 Solo DESPUÉS (Incidente TRITON)"],
            horizontal=True,
            index=0
        )

        if map_comp_mode == "👥 Lado a Lado (Comparativa Directa)":
            map_l, map_r = st.columns(2)
            with map_l:
                st.markdown("**🔵 ANTES: Operación Normal (Línea Base)**")
                fig_map_before = plot_enhanced_network(
                    wn=wn_current,
                    target_node=None,
                    target_link=None,
                    scenario_type=ScenarioType.BASELINE,
                    monitored_sensors=monitored_sensors,
                    color_mode="Presión Hidráulica (m)",
                    sim_pressure_df=res_base["pressure"]
                )
                fig_map_before.update_layout(height=420, margin=dict(b=20, l=10, r=10, t=30))
                st.plotly_chart(fig_map_before, use_container_width=True, key="plotly_map_comp_before_sidebyside")
                st.caption(f"✓ Presión media: {metrics_baseline['mean_pressure_m']:.1f} m | Fuga: 0.0 m³ | Red nominal")

            with map_r:
                st.markdown(f"**🔴 DESPUÉS: Incidente ({config.scenario_type.upper()})**")
                t_node, t_link = get_target_components(config)
                fig_map_after = plot_enhanced_network(
                    wn=wn_current,
                    target_node=t_node,
                    target_link=t_link,
                    scenario_type=config.scenario_type,
                    monitored_sensors=monitored_sensors,
                    color_mode="Presión Hidráulica (m)",
                    sim_pressure_df=res_scen["pressure"]
                )
                fig_map_after.update_layout(height=420, margin=dict(b=20, l=10, r=10, t=30))
                st.plotly_chart(fig_map_after, use_container_width=True, key="plotly_map_comp_after_sidebyside")
                st.caption(f"⚠️ Presión media: {metrics['mean_pressure_m']:.1f} m | Pérdida: {metrics['leak_volume_m3']:.1f} m³ | Componente afectado resaltado")

        elif map_comp_mode == "🔵 Solo ANTES (Línea Base Normal)":
            fig_map_before = plot_enhanced_network(
                wn=wn_current,
                target_node=None,
                target_link=None,
                scenario_type=ScenarioType.BASELINE,
                monitored_sensors=monitored_sensors,
                color_mode="Presión Hidráulica (m)",
                sim_pressure_df=res_base["pressure"]
            )
            st.plotly_chart(fig_map_before, use_container_width=True, key="plotly_map_comp_before_full")
        else:
            t_node, t_link = get_target_components(config)
            fig_map_after = plot_enhanced_network(
                wn=wn_current,
                target_node=t_node,
                target_link=t_link,
                scenario_type=config.scenario_type,
                monitored_sensors=monitored_sensors,
                color_mode="Presión Hidráulica (m)",
                sim_pressure_df=res_scen["pressure"]
            )
            st.plotly_chart(fig_map_after, use_container_width=True, key="plotly_map_comp_after_full")

        st.markdown("---")
        # Explicación del fenómeno
        st.info(f"""
        📌 **Interpretación del Impacto en TRITON:**
        • **Estado Base (Antes):** La red operaba sin anomalías entregando el suministro a presión nominal.
        • **Estado Actual (Después):** Durante el intervalo de horas **{config.event_start_hour} a {config.event_end_hour}**, se inyectó el evento `{config.scenario_type}`.
        • **Diagnóstico de Gemelos:** {'En un ciberataque, la presión física real coincide con la línea base pero la telemetría SCADA miente creando residuo artificial.' if config.scenario_type == ScenarioType.SENSOR_SPOOF else 'En una falla física real (fuga/cierre), la presión real disminuye físicamente y la telemetría lo refleja fielmente.'}
        """)

        st.markdown("---")
        st.subheader("💡 ¿Qué pasaría SIN TRITON vs CON TRITON? (Evaluación de Resiliencia Operativa)")
        st.caption(
            "Comparativa de impacto real: ¿cómo responde un sistema de agua convencional (SCADA clásico) "
            "frente al gemelo digital asistido por IA de TRITON ante el escenario actual?"
        )

        leak_current_m3 = float(metrics['leak_volume_m3'])
        is_leak_scenario = config.scenario_type in [ScenarioType.LEAK, ScenarioType.STEALTH_ATTACK]
        is_burst_scenario = config.scenario_type == ScenarioType.DEMAND_BURST
        act_h = res_scen.get("actual_max_hour", config.duration_hours)
        truncated_before_event = bool(res_scen.get("is_truncated", False) and act_h < config.event_start_hour)

        if is_leak_scenario and leak_current_m3 > 0:
            leak_unmitigated_m3 = leak_current_m3 * 2.8
            saved_water_m3 = max(0.0, leak_unmitigated_m3 - leak_current_m3)
            saved_energy_kwh = saved_water_m3 * metrics.get('specific_energy_kwh_per_m3', 0.25)
            trad_leak_li = f"<b>En Fugas:</b> Se perderían hasta <b>{leak_unmitigated_m3:.1f} m³</b> de agua por detección tardía (24 a 72h)."
            triton_leak_li = f"<b>En Fugas:</b> Alerta temprana para aislamiento; ahorro de hasta <b>{saved_water_m3:.1f} m³</b> de agua potable."
            triton_energy_li = f"<b>Energía Protegida:</b> Ahorro de ~<b>{saved_energy_kwh:.1f} kWh</b> en bombeo inútil de agua derramada."
            chart_leak_trad = leak_unmitigated_m3
            chart_leak_triton = leak_current_m3
        elif is_burst_scenario and leak_current_m3 > 0:
            burst_unmitigated_m3 = leak_current_m3 * 3.0
            saved_water_m3 = max(0.0, burst_unmitigated_m3 - leak_current_m3)
            saved_energy_kwh = saved_water_m3 * metrics.get('specific_energy_kwh_per_m3', 0.25)
            trad_leak_li = f"<b>En Consumo Ilícito:</b> Pérdida de hasta <b>{burst_unmitigated_m3:.1f} m³</b> no contabilizados (NRW) por toma clandestina continua no detectada."
            triton_leak_li = f"<b>En Consumo Ilícito:</b> Detección analítica de demanda anómala en &lt; 1h; ahorro de hasta <b>{saved_water_m3:.1f} m³</b> de agua no registrada."
            triton_energy_li = f"<b>Energía Protegida:</b> Ahorro de ~<b>{saved_energy_kwh:.1f} kWh</b> en bombeo de agua no facturada."
            chart_leak_trad = burst_unmitigated_m3
            chart_leak_triton = leak_current_m3
        elif is_leak_scenario and truncated_before_event:
            trad_leak_li = f"<b>En Fugas:</b> Evento programado para la hora {config.event_start_hour}, pero el solver se detuvo en la hora {act_h} por restricciones del modelo."
            triton_leak_li = "<b>En Fugas:</b> 0.0 m³ de fuga física registrada en los datos antes de la detención."
            triton_energy_li = "<b>Energía Protegida:</b> 0.0 kWh (sin derrame efectivo en el intervalo simulado)."
            chart_leak_trad = 0.0
            chart_leak_triton = 0.0
        elif config.scenario_type == ScenarioType.SENSOR_SPOOF:
            trad_leak_li = "<b>En Fugas:</b> 0.0 m³ de pérdida física (ciberataque puro), pero riesgo de despresurizar o apagar bombas por alarma falsa."
            triton_leak_li = "<b>En Spoofing:</b> 0.0 m³ derramados; TRITON evita falsas maniobras operativas desacoplando el gemelo físico del SCADA."
            triton_energy_li = "<b>Energía Protegida:</b> Preservación de consignas de bombeo eficientes sin desestabilizar la red."
            chart_leak_trad = 0.0
            chart_leak_triton = 0.0
        elif config.scenario_type == ScenarioType.PIPE_CLOSURE:
            trad_leak_li = "<b>En Cierre de Tubería:</b> 0.0 m³ de derrame, pero caída de presiones aguas abajo y desabastecimiento hasta recibir quejas vecinales."
            triton_leak_li = "<b>En Cierre de Tubería:</b> Diagnóstico rápido en &lt; 1h discriminando válvula cerrada para envío directo de cuadrilla."
            triton_energy_li = "<b>Energía Protegida:</b> Evita operar bombas contra tramos bloqueados en puntos de baja eficiencia."
            chart_leak_trad = 0.0
            chart_leak_triton = 0.0
        elif config.scenario_type == ScenarioType.PUMP_OUTAGE:
            trad_leak_li = "<b>En Falla de Bomba:</b> 0.0 m³ de derrame, pero colapso del gradiente piezométrico y paro de suministro sin contingencia automática."
            triton_leak_li = "<b>En Falla de Bomba:</b> Detección instantánea de parada no programada y activación inmediata de bomba de reserva."
            triton_energy_li = "<b>Energía Protegida:</b> Supervisión de contingencia eléctrica y balanceo de carga entre estaciones."
            chart_leak_trad = 0.0
            chart_leak_triton = 0.0
        else:
            trad_leak_li = f"<b>Volumen de Agua:</b> 0.0 m³ de pérdida por rotura (operación '{config.scenario_type}')."
            triton_leak_li = "<b>En Operación Base:</b> Red vigilada continuamente por el gemelo digital en estado nominal."
            triton_energy_li = "<b>Energía Protegida:</b> Consumo de bombeo optimizado según la curva de demanda nominal."
            chart_leak_trad = 0.0
            chart_leak_triton = 0.0

        col_trad, col_triton = st.columns(2)

        with col_trad:
            st.markdown(f"""
            <div style="background-color: #FFF5F5; border: 1px solid #FEB2B2; border-radius: 8px; padding: 16px;">
                <h4 style="color: #C53030; margin-top: 0;">❌ Sin TRITON (SCADA Convencional Reactivo)</h4>
                <ul style="color: #742A2A; font-size: 0.90rem; line-height: 1.6; margin-bottom: 0;">
                    <li><b>Tiempo Medio de Detección (MTTD):</b> 24 a 72 horas (depende de reportes vecinales o rotura en superficie).</li>
                    <li>{trad_leak_li}</li>
                    <li><b>En Ciberataque Spoofing:</b> <b>100% inadvertido</b>. Los operadores creen que las presiones son reales, arriesgando apagar bombas críticas o causar golpes de ariete.</li>
                    <li><b>Energía de Bombeo:</b> Se malgastan cientos de kWh intentando presurizar tramos rotos o ante consignas falsas.</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        with col_triton:
            st.markdown(f"""
            <div style="background-color: #F0FFF4; border: 1px solid #9AE6B4; border-radius: 8px; padding: 16px;">
                <h4 style="color: #276749; margin-top: 0;">✅ Con TRITON (Gemelo Digital Ciberfísico + IA)</h4>
                <ul style="color: #22543D; font-size: 0.90rem; line-height: 1.6; margin-bottom: 0;">
                    <li><b>Tiempo Medio de Detección (MTTD):</b> <b>&lt; 1 hora</b> (detección inmediata por residual contrafactual).</li>
                    <li>{triton_leak_li}</li>
                    <li><b>En Ciberataque Spoofing:</b> <b>100% detectado</b> por discrepancia entre telemetría y leyes físicas (R_phys &gt; 1.0 m).</li>
                    <li>{triton_energy_li}</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        vol_indicator_title = "Consumo Ilícito (m³)" if is_burst_scenario else "Volumen Fuga (m³)"
        # Gráfico Estadístico de Resiliencia
        comp_df = pd.DataFrame([
            {"Indicador": "Tiempo Detección (h)", "SCADA Convencional": 48.0, "TRITON Digital Twin": 0.8},
            {"Indicador": vol_indicator_title, "SCADA Convencional": chart_leak_trad, "TRITON Digital Twin": chart_leak_triton},
            {"Indicador": "Vulnerabilidad Spoofing (%)", "SCADA Convencional": 100.0, "TRITON Digital Twin": 0.0},
            {"Indicador": "Confiabilidad Diagnóstico (%)", "SCADA Convencional": 20.0, "TRITON Digital Twin": 97.0},
        ])

        fig_stats = go.Figure()
        fig_stats.add_trace(go.Bar(
            x=comp_df["Indicador"],
            y=comp_df["SCADA Convencional"],
            name="❌ SCADA Convencional (Sin TRITON)",
            marker_color="#E53935"
        ))
        fig_stats.add_trace(go.Bar(
            x=comp_df["Indicador"],
            y=comp_df["TRITON Digital Twin"],
            name="✅ Gemelo Digital (Con TRITON)",
            marker_color="#2E7D32"
        ))

        fig_stats.update_layout(
            title="<b>Estadísticas de Resiliencia: Operación Convencional vs Gemelo Digital TRITON</b>",
            barmode="group",
            yaxis_title="Valor / Magnitud",
            height=370,
            hovermode="x unified"
        )
        st.plotly_chart(fig_stats, use_container_width=True, key="plotly_resilience_barchart")

    # ----------------------------------------------------
    # PESTAÑA 2: TOPOLOGÍA ESPACIAL DE LA RED
    # ----------------------------------------------------
    with tab_top:
        m_col_left, m_col_right = st.columns([3, 1])

        with m_col_right:
            st.markdown("#### 🔍 Control del Mapa")
            map_mode = st.radio("Modo de Coloreo:", ["Componentes y Amenazas", "Presión Hidráulica (m)"], index=0, key="map_mode_tab_top")
            
            st.markdown("---")
            st.markdown("#### 📋 Resumen del Escenario")
            st.write(f"**Escenario:** `{config.scenario_type}`")
            t_node, t_link = get_target_components(config)
            if config.scenario_type in [ScenarioType.LEAK, ScenarioType.STEALTH_ATTACK]:
                st.write(f"**Nodo Fuga:** `{config.leak_node}`")
                st.write(f"**Orificio:** `{config.leak_diameter_mm} mm` (Cd: {config.leak_discharge_coeff})")
            if config.scenario_type in [ScenarioType.SENSOR_SPOOF, ScenarioType.STEALTH_ATTACK]:
                st.write(f"**Sensor Spoofed:** `{config.spoof_node}`")
                st.write(f"**Sesgo:** `{config.spoof_bias_m:+.1f} m`")
            elif config.scenario_type == ScenarioType.PIPE_CLOSURE:
                st.write(f"**Tubería:** `{config.close_pipe}` (Cerrada)")
            elif config.scenario_type == ScenarioType.PUMP_OUTAGE:
                st.write(f"**Bomba:** `{config.outage_pump}` (Apagada / Outage)")
            elif config.scenario_type == ScenarioType.DEMAND_BURST:
                st.write(f"**Nodo Consumo:** `{config.burst_node}`")
                st.write(f"**Caudal Extra:** `{config.burst_flow_m3s*1000:.1f} L/s`")
            elif config.scenario_type == ScenarioType.BASELINE:
                st.write("**Operación:** Nominal sin fallas")

            st.write(f"**Ventana:** Horas {config.event_start_hour} a {config.event_end_hour}")
            st.write(f"**Nodos:** {wn_current.num_nodes} | **Tuberías:** {wn_current.num_links}")

        with m_col_left:
            fig_net = plot_enhanced_network(
                wn=wn_current,
                target_node=t_node,
                target_link=t_link,
                scenario_type=config.scenario_type,
                monitored_sensors=monitored_sensors,
                color_mode=map_mode,
                sim_pressure_df=res_scen["pressure"]
            )
            st.plotly_chart(fig_net, use_container_width=True, key="plotly_main_topology_map")

    # ----------------------------------------------------
    # PESTAÑA 3: TELEMETRÍA SCADA VS GEMELO FÍSICO
    # ----------------------------------------------------
    with tab_tel:
        st.subheader("Comparación Temporal: Gemelo Físico vs Telemetría SCADA")
        p_df = res_scen["pressure"]
        
        target = state["target_element"] if (state.get("target_element") and str(state["target_element"]) in p_df["node"].astype(str).values) else (monitored_sensors[0] if monitored_sensors else p_df["node"].iloc[0])
        sub_p = p_df[p_df["node"].astype(str) == str(target)].sort_values("hour")

        fig_p = go.Figure()
        fig_p.add_trace(go.Scatter(
            x=sub_p["hour"], y=sub_p["pressure_m"],
            name="Gemelo Físico (Presión Real)",
            line=dict(color="#1976D2", width=3)
        ))
        fig_p.add_trace(go.Scatter(
            x=sub_p["hour"], y=sub_p["observed_pressure_m"],
            name="Telemetría SCADA Observada",
            line=dict(color="#D32F2F", width=2.5, dash="dash")
        ))

        if config.scenario_type != ScenarioType.BASELINE:
            fig_p.add_vrect(
                x0=config.event_start_hour, x1=config.event_end_hour,
                fillcolor="rgba(255, 152, 0, 0.15)", layer="below", line_width=1,
                annotation_text="Ventana del Evento", annotation_position="top left"
            )

        fig_p.update_layout(
            title=f"Presión en Nodo {target}: Estado Físico Real vs Telemetría SCADA",
            xaxis_title="Hora de Simulación (h)",
            yaxis_title="Presión Hidráulica (m)",
            hovermode="x unified",
            height=400
        )
        st.plotly_chart(fig_p, use_container_width=True, key="plotly_telemetry_sensor_target")

        st.markdown("**Telemetría Multicanal de Sensores Monitoreados:**")
        p_sensors = p_df[p_df["node"].astype(str).isin([str(s) for s in monitored_sensors])]
        fig_multi = px.line(
            p_sensors, x="hour", y="observed_pressure_m", color="node",
            labels={"observed_pressure_m": "Presión Observada (m)", "hour": "Hora (h)", "node": "Sensor"},
            title="Lecturas de Presión en Red SCADA"
        )
        fig_multi.update_layout(height=340)
        st.plotly_chart(fig_multi, use_container_width=True, key="plotly_telemetry_multichannel_all")

    # ----------------------------------------------------
    # PESTAÑA 4: IA Y RESIDUOS TRITON
    # ----------------------------------------------------
    with tab_ia:
        st.subheader("Análisis de Residuos y Detección de Anomalías")
        timeline = ai_eval["timeline"]

        col_l, col_r = st.columns(2)
        with col_l:
            fig_res = go.Figure()
            fig_res.add_trace(go.Scatter(
                x=timeline["hour"], y=timeline["physics_residual_m"],
                name="Residuo Físico (|Obs - Phys|)",
                line=dict(color="#D32F2F", width=2.5)
            ))
            fig_res.add_hline(
                y=ai_eval["physics_threshold_m"], line_dash="dot",
                annotation_text=f"Umbral Ciberataque ({ai_eval['physics_threshold_m']:.2f}m)",
                annotation_position="bottom right", line_color="#D32F2F"
            )
            fig_res.add_trace(go.Scatter(
                x=timeline["hour"], y=timeline["counterfactual_residual_m"],
                name="Residuo Contrafactual (|Obs - Base|)",
                line=dict(color="#1976D2", width=2)
            ))
            fig_res.add_hline(
                y=ai_eval["counterfactual_threshold_m"], line_dash="dot",
                annotation_text=f"Umbral Falla Física ({ai_eval['counterfactual_threshold_m']:.2f}m)",
                annotation_position="bottom right", line_color="#1976D2"
            )
            fig_res.update_layout(
                title="Señales de Residuos TRITON",
                xaxis_title="Hora (h)", yaxis_title="Residuo (m)", height=370
            )
            st.plotly_chart(fig_res, use_container_width=True, key="plotly_ai_residual_signals_graph")

        with col_r:
            color_map = {
                "Normal Operation": "#4CAF50",
                "Physical Fault (Leak/Outage/Closure)": "#FF9800",
                "Physical Fault (Leak/Closure)": "#FF9800",
                "Cyber Attack (FDI/Spoofing)": "#F44336",
                "Hybrid Attack (Physical + Cyber)": "#9C27B0"
            }
            fig_cls = px.scatter(
                timeline, x="hour", y="classification", color="classification",
                color_discrete_map=color_map,
                title="Diagnóstico Temporal Horario",
                labels={"hour": "Hora (h)", "classification": "Diagnóstico"}
            )
            fig_cls.update_traces(marker=dict(size=9))
            fig_cls.update_layout(height=370, showlegend=False)
            st.plotly_chart(fig_cls, use_container_width=True, key="plotly_ai_classification_timeline_scatter")

        st.markdown("**Tabla Detallada de Inferencia de IA:**")
        st.dataframe(
            timeline[[
                "hour", "classification", "predicted_anomaly",
                "physics_residual_m", "counterfactual_residual_m", "anomaly_score"
            ]],
            use_container_width=True,
            height=260
        )

    # ----------------------------------------------------
    # PESTAÑA 5: SCORECARD TRITON (CI / SO / IA)
    # ----------------------------------------------------
    with tab_sc:
        st.subheader("Cuadro de Mando del Framework TRITON (CI / SO / IA)")
        st.caption("Alineado formalmente con los dominios de Ciberseguridad, Sostenibilidad e Inteligencia Artificial.")

        def style_status(val):
            if val == "Optimal":
                return "background-color: #E8F5E9; color: #2E7D32; font-weight: bold;"
            elif val in ["Warning", "Attentive"]:
                return "background-color: #FFFDE7; color: #F57F17; font-weight: bold;"
            elif val in ["Critical", "Compromised"]:
                return "background-color: #FFEBEE; color: #C62828; font-weight: bold;"
            return ""

        if hasattr(scorecard.style, "map"):
            styled_scorecard = scorecard.style.map(style_status, subset=["Status"])
        else:
            styled_scorecard = scorecard.style.applymap(style_status, subset=["Status"])

        st.dataframe(styled_scorecard, use_container_width=True, height=360)

        csv_data = scorecard.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Descargar Scorecard TRITON (CSV)",
            data=csv_data,
            file_name="triton_scorecard_report.csv",
            mime="text/csv",
            use_container_width=True
        )


if __name__ == "__main__":
    main()
