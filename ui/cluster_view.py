import streamlit as st
import grpc
from rpc.client import RaftRPCClient

MAX_COLS = 4

ROLE_COLORS = {
    "Leader": "🟨",
    "Candidate": "🟥",
    "Follower": "🟦",
    "DEAD": "⬜"
}

def render_cluster_html(cluster):    
    msg_box = st.empty()
    msg_box.text("Status messages will appear here...")

    nodes = cluster.nodes
    for i in range(0, len(nodes), MAX_COLS):
        cols = st.columns(MAX_COLS)

        for col, node in zip(cols, nodes[i:i + MAX_COLS]):
            with col:
                status = None
                process_alive = node["process"] is not None
                node_alive = None
                
                if process_alive:
                    try:
                        client = RaftRPCClient(
                            f"localhost:{node['port']}"
                        )
                        status = client.get_status()
                        node_alive = status.alive
                        
                    except grpc.RpcError:
                        process_alive = False

                if not process_alive or not node_alive:
                    role = "DEAD"
                    term = "-"
                else:
                    role = status.role
                    term = status.term

                # ============================
                # NODE CARD
                # ============================
                with st.container(border=True):
                    st.markdown(
                        f"### {ROLE_COLORS[role]} Node {node['id']}"
                    )

                    st.text(f"Role: {role}")
                    st.text(f"Term: {term}")

                    st.divider()

                    col_kill, col_play = st.columns([1,1])
                    
                    # ---------- Pause ----------
                    with col_kill:
                        if process_alive and node_alive:
                            if st.button("💀 Kill", key=f"kill_{node['id']}"):
                                client.kill_node()
                                msg_box.warning(f"Node {node['id']} killed")
                        else:
                            st.button("💀 Kill", disabled=True, key=f"kill_disabled_{node['id']}")

                    # ---------- Play ----------
                    with col_play:
                        if process_alive and not node_alive:
                            if st.button("▶ Play", key=f"play_{node['id']}"):
                                client.play_node()
                                msg_box.success(f"Node {node['id']} resumed")
                        else:
                            st.button("▶ Play", disabled=True, key=f"play_disabled_{node['id']}")

            