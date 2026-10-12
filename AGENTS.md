# TRITON Smart Water Digital Twin — Contexto del Agente

Este repositorio contiene el desarrollo del simulador para el **Framework TRITON** (Technology Resilience, cybersecurity and Intelligence for Transformative Optimization of smart water Networks).

## 📍 Estado Actual del Proyecto: FASE 5 Perfeccionada y Validada ✅
- [x] **Fase 1: Inicialización** (Estructura de directorios, `requirements.txt`, `.venv` verificado con WNTR 1.5.0 y Streamlit 1.65.0, `Net3.inp` generado).
- [x] **Fase 2: Motor Base** (`src/engine/wntr_runner.py` con carga `.inp`, creación programática de red, simulación PDD y cálculo de energía kWh).
- [x] **Fase 3: Escenarios Ampliados e Incidentes** (`src/scenarios/injector.py`):
  - Inyección de fugas físicas con selección completa de nodo y **Calculadora Hidráulica PDD en tiempo real** (Torricelli, caudal $L/s$, volumen $m^3$, tinacos y costo USD).
  - Cierre de tuberías troncales (`PIPE_CLOSURE`).
  - Ciberataques de sensor spoofing / FDI en telemetría observada (`SENSOR_SPOOF`).
  - **Falla o apagón de estación de bombeo** (`PUMP_OUTAGE`).
  - **Consumo ilícito o pico súbito de demanda anómala** (`DEMAND_BURST`).
  - **Ataque ciberfísico híbrido sigiloso** (`STEALTH_ATTACK`: fuga real + alteración de telemetría para encubrir la pérdida ante SCADA).
- [x] **Fase 4: Capa de IA y TRITON** (`src/ai/detector.py`, `metrics.py` - comparador Physical Twin vs Cyber Twin, Isolation Forest, clasificación tri-estado e híbrida, matriz de confusión y scorecard TRITON CI/SO/IA).
- [x] **Fase 5: Interfaz de Usuario y Orquestador** (`app/ui.py`, `main.py`):
  - [x] Corregido error Pandas 3 `Styler.map`.
  - [x] Corregido `AttributeError: 'Reservoir' object has no attribute 'elevation'` mediante extracción segura de atributos hidráulicos (`base_head` / `elevation`).
  - [x] **Visualizador Persistente de las 4 Fases de TRITON** en tarjetas interactivas permanentes (Física, Ciberseguridad, IA y Sostenibilidad).
  - [x] **Pestaña Comparativa Antes vs Después (Línea Base vs Escenario Actual)**:
    - Métricas comparativas con $\Delta$.
    - Gráfica temporal superpuesta de presiones.
    - **Mapas Lado a Lado (Comparativa Directa Espacial)**: Mapa de red antes vs mapa de red después con componentes afectados destacados (bombas, nudos, tuberías).
    - **Evaluación de Resiliencia Operativa**: Análisis estadístico y gráfico cuantitativo de **¿Qué pasaría SIN TRITON vs CON TRITON?** (ahorro en agua, mitigación rápida, detección de spoofing y energía).
  - [x] Mapa espacial interactivo con capas limpias, resaltado dinámico de elementos afectados y selector de modos.
  - [x] **Banco de 7 pruebas rápidas (Presets interactivos)**: Normal, Fuga, Spoofing, Cierre, Falla de Bomba, Consumo Ilícito y Ataque Híbrido.
  - [x] **Guía didáctica multidimensional**: Explicación teórica del por qué de la fuga en literatura vs comparativa de todos los percances.
  - [x] **Informe Técnico Completo para Revisión Docente**: Generado en `INFORME_TECNICO_TRITON.md` con fundamentación teórica, formulación matemática PDD y de energía, arquitectura, resultados de validación Net3 y guía de evaluación.

## Cómo Ejecutar el Simulador
```bash
# 1. Navegar al simulador
cd "02_TRITON_SIMULATOR"

# 2. Ejecutar la interfaz web (Streamlit)
./.venv/bin/streamlit run app/ui.py
# O alternativamente:
./.venv/bin/python main.py

# 3. Modo Benchmark / CLI de prueba
./.venv/bin/python main.py --demo
```

## Estructura de Trabajo
- `01_REFERENCIAS/`: Documentación teórica, paper de TRITON y prototipo base (Solo lectura).
- `02_TRITON_SIMULATOR/`: Directorio principal de desarrollo (Escritura).
  - `data/networks/`: Archivos de red EPANET (`.inp` como `Net3.inp` y `simple_network.inp`).
  - `src/engine/`: Motor hidráulico WNTR (`wntr_runner.py`).
  - `src/scenarios/`: Inyección de anomalías (`injector.py`).
  - `src/ai/`: Capa de IA y Sostenibilidad TRITON (`detector.py`, `metrics.py`).
  - `app/`: Interfaz interactiva Streamlit (`ui.py`).
  - `main.py`: Lanzador universal de la aplicación y benchmark.
  - `.venv/`: Entorno virtual Python con dependencias instaladas.

## Guía Principal
Consulta siempre [`instrucciones_para_agente_agy.md`](./instrucciones_para_agente_agy.md) para los requerimientos canónicos y el plan de ejecución por fases.
