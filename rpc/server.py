import grpc
import time
from concurrent import futures
from rpc import raft_pb2, raft_pb2_grpc


class RaftRPCServer(raft_pb2_grpc.RaftServiceServicer):
    def __init__(self, node):
        self.node = node

    def RequestVote(self, req, ctx):
        return self.node.on_request_vote(req)

    def AppendEntries(self, req, ctx):
        return self.node.on_append_entries(req)

    def DisconnectNode(self, req, ctx):
        self.node.disconnect()
        return raft_pb2.Empty()

    def ReconnectNode(self, req, ctx):
        self.node.reconnect()
        return raft_pb2.Empty()

    def GetStatus(self, request, context):
        state = self.node.state
        return raft_pb2.StatusReply(
            node_id=state.node_id,
            role=state.role,
            term=state.current_term,
            connected=state.connected,
            log_len=len(state.log),
            commit_index=state.commit_index,
        )

    def GetLog(self, req, ctx):
        return self.node.get_log_reply()

    def SubmitCommand(self, req, ctx):
        return self.node.on_submit_command(req)

    def KillNode(self, req, ctx):
        print(f"[RPC] Killing node {self.node.state.node_id}")
        self.node.state.alive = False
        # self.node.shutdown()
        return raft_pb2.Empty()
    
    def PlayNode(self, req, ctx):
        print(f"[RPC] Continuing node {self.node.state.node_id}")
        self.node.state.alive = True
        # self.node.shutdown()
        return raft_pb2.Empty()


    def Ping(self, request, context):
        print(f"[RPC] Node {self.node.state.node_id} received Ping!")
        return raft_pb2.PingReply(
            message=f"Node {self.node.state.node_id} alive"
        )
    
    def Partition(self, req, ctx):
        peers = req.peers
        mode = req.mode

        if mode == "block":
            for p in peers:
                self.node.state.blocked_peers.add(int(p))
            print(f"[PARTITION] Node {self.node.state.node_id} BLOCK -> {list(peers)}")

        elif mode == "unblock":
            for p in peers:
                self.node.state.blocked_peers.discard(int(p))
            print(f"[PARTITION] Node {self.node.state.node_id} UNBLOCK -> {list(peers)}")

        return raft_pb2.PartitionReply(ok=True)



def serve(node, port):
    server = grpc.server(futures.ThreadPoolExecutor(10))
    node.server = server
    raft_pb2_grpc.add_RaftServiceServicer_to_server(
        RaftRPCServer(node), server
    )
    # Windows setups often fail binding IPv6 [::]; bind IPv4 instead.
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    print(f"[RPC] Node {node.state.node_id} on {port}")

    server.wait_for_termination()
