# TRITON Smart Water Digital Twin - Guía de Desarrollo para Agy

## 1. Contexto del Proyecto
Hola Agy. Eres un ingeniero de software experto en sistemas ciberfísicos, gemelos digitales (Digital Twins) e Inteligencia Artificial. Tu objetivo es construir un simulador interactivo basado en el **Framework TRITON** (Technology Resilience, cybersecurity and Intelligence for Transformative Optimization of smart water Networks). 

TRITON es una metodología que integra **Ciberseguridad**, **Sostenibilidad** e **Inteligencia Artificial** para optimizar redes de distribución de agua, permitiendo diferenciar entre eventos físicos reales (ej. fugas) y ciberataques (ej. falsificación de datos de sensores o *spoofing*).

## 2. Estructura del Entorno de Trabajo
El espacio de trabajo se divide estrictamente en dos carpetas principales. Debes basar tu desarrollo leyendo el contexto de la Carpeta 1 y escribiendo el código en la Carpeta 2.

```text
/
├── 01_REFERENCIAS/                 # (Solo lectura) Contexto y bases del proyecto
│   ├── TRITON_SmartWater_DT_v0.1/  # Código del prototipo anterior (extraído del .zip)
│   ├── TRITON_Paper.pdf            # Documento teórico sobre el framework TRITON
│   └── conversacion_gpt.odt        # Historial de decisiones de diseño y requisitos
│
└── 02_TRITON_SIMULATOR/            # (Escritura) Aquí construirás el nuevo simulador
    ├── data/
    │   └── networks/               # Archivos EPANET (.inp) generados o cargados
    ├── src/
    │   ├── engine/                 # Motor de simulación física (WNTR)
    │   ├── scenarios/              # Inyección de anomalías (fugas, cierres, spoofing)
    │   └── ai/                     # Modelos de detección (Isolation Forest, etc.)
    ├── app/
    │   └── ui.py                   # Interfaz gráfica principal con Streamlit
    ├── requirements.txt
    └── main.py                     # Script de arranque
```

## 3. Requisitos de la Aplicación y Funcionalidades Core

Debes construir una aplicación modular que cumpla con los siguientes requisitos:

### A. Gestión de Redes de Agua (Física)
*   **Cargar Redes:** Permitir cargar archivos `.inp` de EPANET.
*   **Crear Redes Simples:** Proveer una función básica para crear una red de agua desde cero (ej. 1 tanque, 1 bomba, 3 nodos, 2 tuberías) usando la API de WNTR, y guardarla como `.inp`.

### B. Motor de Escenarios (Physical & Cyber Twin)
*   **Baseline:** Operación normal.
*   **Fuga (Leak):** Inyectar un orificio (emisor) en un nodo físico o demanda adicional.
*   **Spoofing (Ciberataque):** El estado físico se mantiene normal, pero se alteran los datos de presión o caudal leídos por los sensores virtuales.
*   **Cierre de Tubería:** Modificar el estado de una tubería a `CLOSED`.

### C. Interfaz de Usuario (UI)
*   Usar **Streamlit** para la interfaz web.
*   Debe tener un panel lateral para cargar/crear redes y configurar el escenario.
*   **REQUISITO ESTELAR (Fases TRITON):** Al ejecutar la simulación, debe mostrarse una experiencia visual por fases usando barras de progreso (`st.progress`) o spinners encadenados (`st.spinner` / `st.status`):
    *   *Cargando Fase 1 (Operación Física):* Calculando hidráulica base...
    *   *Cargando Fase 2 (Capa de Ciberseguridad):* Verificando integridad de sensores / inyectando spoofing...
    *   *Cargando Fase 3 (Capa de Inteligencia Artificial):* Analizando residuos e infiriendo anomalías...
    *   *Cargando Fase 4 (Métricas de Sostenibilidad):* Calculando m3 perdidos y kWh consumidos...

## 4. Stack Tecnológico a Utilizar
*   **Backend Hidráulico:** `wntr` (Water Network Tool for Resilience). Es obligatorio usar esto para manejar la simulación de EPANET.
*   **Procesamiento de Datos:** `pandas`, `numpy`.
*   **Inteligencia Artificial:** `scikit-learn` (Isolation Forest para detección de anomalías basado en el residuo físico vs medido).
*   **Frontend:** `streamlit`, `plotly` (para graficar la red y las series temporales).

## 5. Plan de Ejecución para Agy (Pasos a seguir)
Por favor, ejecuta el desarrollo en este orden, confirmando conmigo cada vez que termines un paso:

1.  **Inicialización:** Crea la estructura de carpetas en `02_TRITON_SIMULATOR/` y genera el `requirements.txt`.
2.  **Motor Base (`src/engine/wntr_runner.py`):** Escribe el código para inicializar un modelo WNTR, ya sea cargando un `.inp` o generando una red programáticamente.
3.  **Escenarios (`src/scenarios/`):** Crea la lógica para inyectar la fuga en la red física y el *spoofing* en los resultados de salida.
4.  **Lógica IA y TRITON (`src/ai/`):** Implementa el comparador (Physical Twin vs Cyber Twin) para detectar si la falla es real o cibernética.
5.  **Interfaz Gráfica (`app/ui.py`):** Construye el dashboard de Streamlit, asegurando implementar la barra de carga de fases solicitada.

¡Comencemos! Revisa los documentos de la carpeta `01_REFERENCIAS` si tienes dudas conceptuales y procede con el Paso 1.