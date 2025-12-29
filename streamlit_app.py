import streamlit as st
import time

from core.cluster import ClusterManager
from ui.sidebar import render_sidebar
from ui.cluster_view import render_cluster_html, render_log_table

st.set_page_config(page_title="Raft Simulator", layout="wide")
st.title("🛠️ Raft Consensus Simulator")

# ============================
# INIT CLUSTER MANAGER
# ============================
if "cluster" not in st.session_state:
    st.session_state.cluster = ClusterManager()

cluster = st.session_state.cluster

# ============================
# SIDEBAR
# ============================
render_sidebar(cluster)

# ============================
# MAIN VIEW
# ============================
st.subheader("Cluster View")

if not cluster.nodes:
    st.info("Cluster not initialized. Choose node count and start cluster.")
else:
    render_cluster_html(cluster.nodes)
    render_log_table(cluster.nodes)

time.sleep(0.5)
st.rerun()
