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
            
            cols[0].write(f"Node {node_id} | Port {port} | {net}")
            status_cache[node_id] = status
            running_nodes.append({"id": node_id, "port": port})
            # =============================
            # 🔍 Leader lookup by partition
            # =============================
            def find_leader_in_group(group_ids):
                for nid in group_ids:
                    stt = status_cache.get(nid)
                    if stt and stt.role == "Leader":
                        return nid
                return None

        except Exception:
            cols[0].write(f"Node {node_id} | Port {port} | UNREACHABLE")
            continue

    st.sidebar.divider()
    if "partition" not in st.session_state:
        st.session_state.partition = {
            "active": False,
            "group_a": [],
            "group_b": []
        }

    st.sidebar.markdown("### 🧑‍💻 Client A")
    client_msg_a = st.sidebar.empty()
    value_a = st.sidebar.number_input(
        "Send number a",
        min_value=0,
        max_value=10_000,
        value=5,
        step=1,
    )
    
    if st.sidebar.button("Send to Leader A", use_container_width=True):
        if not running_nodes:
            client_msg_a.warning("Cluster is not running")
        else:
            # Prefer explicit leader if UI can see it.
            leader_id = None
            if st.session_state.partition["active"]:
                leader_id = find_leader_in_group(
                    st.session_state.partition["group_a"]
                )
            else:
                leader_id = find_leader_in_group(
                    [n["id"] for n in running_nodes]
                )

            def _submit_to(node_id_to_send: int):
                node_info = next(
                    (n for n in running_nodes if n["id"] == node_id_to_send), None)
                if not node_info:
                    return None
                c = RaftRPCClient(f"localhost:{node_info['port']}")
                return c.submit_command(str(int(value_a)))

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
                client_msg_a.error("Failed to submit command")
            elif reply.accepted:
                client_msg_a.success(
                    f"Accepted by leader {reply.leader_id} | term={reply.term} | index={reply.index}"
                )
            else:
                client_msg_a.info(
                    f"Rejected: {reply.message} | leader hint={reply.leader_id}"
                )

    st.sidebar.divider()
    
    if st.session_state.partition["active"]:
        st.sidebar.markdown("### 🧑‍💻 Client B")
        client_msg_b = st.sidebar.empty()
        value_b = st.sidebar.number_input(
            "Send number b",
            min_value=0,
            max_value=10_000,
            value=5,
            step=1,
        )

        if st.sidebar.button("Send to Leader B", use_container_width=True):
            if not running_nodes:
                client_msg_b.warning("Cluster is not running")
            else:
                # Prefer explicit leader if UI can see it.
                leader_id = None
                leader_id = find_leader_in_group(
                    st.session_state.partition["group_b"]
                )


                def _submit_to(node_id_to_send: int):
                    node_info = next(
                        (n for n in running_nodes if n["id"] == node_id_to_send), None)
                    if not node_info:
                        return None
                    c = RaftRPCClient(f"localhost:{node_info['port']}")
                    return c.submit_command(str(int(value_b)))

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
                    client_msg_b.error("Failed to submit command")
                elif reply.accepted:
                    client_msg_b.success(
                        f"Accepted by leader {reply.leader_id} | term={reply.term} | index={reply.index}"
                    )
                else:
                    client_msg_b.info(
                        f"Rejected: {reply.message} | leader hint={reply.leader_id}"
                    )

        st.sidebar.divider()

    # =============================
    # 🔪 Network Partition
    # =============================
    st.sidebar.markdown("### 🔪 Network Partition")

    if not running_nodes:
        st.sidebar.info("Start cluster to create partition")
        return

    node_ids = [int(n["id"]) for n in running_nodes]

    group_a = st.sidebar.multiselect(
        "Group A",
        options=node_ids,
        default=node_ids[: len(node_ids)//2]
    )

    group_b = [nid for nid in node_ids if nid not in group_a]

    st.sidebar.caption(f"Group B (auto): {group_b}")

    partition_msg = st.sidebar.empty()

    def _call_partition(target_id, peers, mode):
        node_info = next(n for n in running_nodes if int(n["id"]) == target_id)
        c = RaftRPCClient(f"localhost:{node_info['port']}")
        return c.partition(peers=peers, mode=mode)

    if not st.session_state.partition["active"]:
        if st.sidebar.button("Create Partition", use_container_width=True):
            if not group_a or not group_b:
                partition_msg.error("Partition must have 2 non-empty groups")
            else:
                try:
                    # Block A -> B
                    for a in group_a:
                        _call_partition(a, group_b, "block")

                    # Block B -> A
                    for b in group_b:
                        _call_partition(b, group_a, "block")

                    st.session_state.partition = {
                        "active": True,
                        "group_a": group_a.copy(),
                        "group_b": group_b.copy()
                    }

                    partition_msg.success(
                        f"Partition created: A={group_a} | B={group_b}"
                    )
                except Exception as e:
                    partition_msg.error(f"Failed: {e}")

    else:
        if st.sidebar.button("Heal Partition", use_container_width=True):
            try:
                for nid in node_ids:
                    _call_partition(nid, node_ids, "unblock")

                st.session_state.partition = {
                    "active": False,
                    "group_a": [],
                    "group_b": []
                }

                partition_msg.success("Partition healed (network restored)")
            except Exception as e:
                partition_msg.error(f"Heal failed: {e}")
