"""Punto de entrada para Streamlit / Render: `streamlit run streamlit_app.py`.

Versión 2: el mapa es el selector de entidades. La versión 1 queda de respaldo en
`streamlit_app_v1.py` (sni_dashboard/app.py).
"""
from sni_dashboard.app_v2 import DashboardV2

DashboardV2().run()
