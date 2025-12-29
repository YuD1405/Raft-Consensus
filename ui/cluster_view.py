import streamlit as st
import grpc
from rpc.client import RaftRPCClient
import pandas as pd

MAX_COLS = 4

ROLE_COLORS = {
    "Leader": "🟨",
    "Candidate": "🟥",
    "Follower": "🟦",
    "DEAD": "⬜"
}

def render_cluster_html(cluster):
    MAX_COLS = 4

    nodes = cluster.nodes
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
                        node_alive = status.connected
                        
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
                                client.disconnect()
                                msg_box.warning(f"Node {node['id']} killed")
                        else:
                            st.button("💀 Kill", disabled=True, key=f"kill_disabled_{node['id']}")

                    # ---------- Play ----------
                    with col_play:
                        if process_alive and not node_alive:
                            if st.button("▶ Play", key=f"play_{node['id']}"):
                                client.reconnect()
                                msg_box.success(f"Node {node['id']} resumed")
                        else:
                            st.button("▶ Play", disabled=True, key=f"play_disabled_{node['id']}")



def render_log_table(nodes):
    st.write("")
    st.subheader("Log")

    rows = []
    max_len = 0
    node_logs = {}
    node_terms = {}
    node_commit = {}

    for node in nodes:
        node_id = node["id"]
        label = f"Node {node_id}"

        if not node.get("process"):
            rows.append(f"{label} (STOPPED)")
            node_logs[rows[-1]] = []
            node_terms[rows[-1]] = []
            node_commit[rows[-1]] = -1
            continue

        client = RaftRPCClient(f"localhost:{node['port']}")
        try:
            status = client.get_status()
            log_reply = client.get_log()
        except Exception:
            rows.append(f"{label} (UNREACHABLE)")
            node_logs[rows[-1]] = []
            node_terms[rows[-1]] = []
            node_commit[rows[-1]] = -1
            continue

        if not status.connected:
            label = f"{label} (DISCONNECTED)"

        entries = list(log_reply.entries)
        rows.append(label)
        node_logs[label] = [e.command for e in entries]
        node_terms[label] = [int(e.term) for e in entries]
        node_commit[label] = int(log_reply.commit_index)
        max_len = max(max_len, len(entries))

    if max_len == 0:
        st.info("No log entries yet.")
        return

    base_cols = 15
    col_count = max(base_cols, max_len)
    columns = [str(i) for i in range(1, col_count + 1)]

    df = pd.DataFrame("", index=rows, columns=columns)
    term_df = pd.DataFrame(0, index=rows, columns=columns)
    commit_df = pd.DataFrame(False, index=rows, columns=columns)

    for r in rows:
        entries = node_logs.get(r, [])
        terms = node_terms.get(r, [])
        commit_idx = int(node_commit.get(r, -1))
        for i in range(min(len(entries), col_count)):
            col = columns[i]
            df.loc[r, col] = entries[i]
            term_df.loc[r, col] = terms[i]
            commit_df.loc[r, col] = i <= commit_idx

    def style_cells(_):
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        for r in df.index:
            for c in df.columns:
                val = df.loc[r, c]
                if val == "":
                    styles.loc[r, c] = "background-color: #cccccc; color: #333;"
                    continue

                # Non-yellow palette: committed = follower-blue, uncommitted = candidate-pink.
                bg = "#99ccff" if bool(commit_df.loc[r, c]) else "#ff9999"
                base = f"background-color: {bg}; color: #000; font-weight: 700; text-align: center;"
                styles.loc[r, c] = base
        return styles

    st.dataframe(df.style.apply(style_cells, axis=None),
                 use_container_width=True)
