import streamlit as st
from rpc.client import RaftRPCClient


def render_sidebar(cluster):
    st.sidebar.header("⚙️ Cluster Controls")

    msg_box = st.sidebar.empty()

    node_count = st.sidebar.number_input(
        "Number of nodes",
        min_value=5,
        max_value=10,
        value=len(cluster.nodes) if cluster.nodes else 5,
        step=1
    )

    if not cluster.is_running():
        if st.sidebar.button("Apply Node Count", use_container_width=True):
            cluster.resize(node_count)
            msg_box.success(f"Prepared {node_count} nodes")
    else:
        msg_box.info("Stop cluster before resizing")

    col1, col2 = st.sidebar.columns(2)

    with col1:
        if st.button("▶️ Start Cluster", use_container_width=True):
            cluster.start_all()
            msg_box.success("Cluster started")

    with col2:
        if st.button("⛔ Stop Cluster", use_container_width=True):
            cluster.stop_all()
            msg_box.warning("Cluster stopped")

    st.sidebar.markdown("### 🔍 Node List")

    status_cache = {}
    running_nodes = []

    for node in cluster.nodes:
        cols = st.sidebar.columns([1])

        node_id = node["id"]
        port = node["port"]

        if not node.get("process"):
            cols[0].write(f"Node {node_id} | Port {port} | STOPPED")
            continue

        client = RaftRPCClient(f"localhost:{port}")
        try:
            status = client.get_status()
            net = "CONNECTED" if status.connected else "DISCONNECTED"
            cols[0].write(f"Node {node_id} | Port {port} | RUNNING | {net}")
            status_cache[node_id] = status
            running_nodes.append({"id": node_id, "port": port})
        except Exception:
            cols[0].write(f"Node {node_id} | Port {port} | UNREACHABLE")
            continue

    st.sidebar.markdown("### 🧑‍💻 Client")
    client_msg = st.sidebar.empty()

    value = st.sidebar.number_input(
        "Send number",
        min_value=0,
        max_value=10_000,
        value=5,
        step=1,
    )

    if st.sidebar.button("Send to Leader", use_container_width=True):
        if not running_nodes:
            client_msg.warning("Cluster is not running")
        else:
            # Prefer explicit leader if UI can see it.
            leader_id = None
            for nid, stt in status_cache.items():
                if getattr(stt, "connected", False) and stt.role == "Leader":
                    leader_id = int(nid)
                    break

            def _submit_to(node_id_to_send: int):
                node_info = next(
                    (n for n in running_nodes if n["id"] == node_id_to_send), None)
                if not node_info:
                    return None
                c = RaftRPCClient(f"localhost:{node_info['port']}")
                return c.submit_command(str(int(value)))

            reply = None
            if leader_id is not None:
                try:
                    reply = _submit_to(leader_id)
                except Exception:
                    reply = None

            # Fallback: try any reachable node, then follow leader hint once.
            if reply is None or not getattr(reply, "accepted", False):
                for n in running_nodes:
                    try:
                        tmp = _submit_to(int(n["id"]))
                    except Exception:
                        continue
                    if tmp is None:
                        continue
                    if tmp.accepted:
                        reply = tmp
                        break
                    hinted = int(getattr(tmp, "leader_id", 0) or 0)
                    if hinted:
                        try:
                            tmp2 = _submit_to(hinted)
                            if tmp2 and tmp2.accepted:
                                reply = tmp2
                                break
                            reply = tmp
                        except Exception:
                            reply = tmp
                        break

            if reply is None:
                client_msg.error("Failed to submit command")
            elif reply.accepted:
                client_msg.success(
                    f"Accepted by leader {reply.leader_id} | term={reply.term} | index={reply.index}"
                )
            else:
                client_msg.info(
                    f"Rejected: {reply.message} | leader hint={reply.leader_id}"
                )
