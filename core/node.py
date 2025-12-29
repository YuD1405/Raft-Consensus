from core.state import RaftState
from core.raft import RaftLogic
from rpc import raft_pb2
import time

class RaftNode:
    def __init__(self, node_id, peers, rpc_clients):
        self.state = RaftState(node_id, peers)
        self.rpc_clients = rpc_clients
        self.logic = RaftLogic(self)
        self.server = None

    def start(self):
        print(f"[Node {self.state.node_id}] starting")
        self.logic.start()

    def shutdown(self):
        if hasattr(self, "server"):
            self.server.stop(0)
            
    # RPC HANDLERS
    def on_request_vote(self, req):
        state = self.state

        if not state.alive:
            raise RuntimeError("Node is dead")

        if req.term < state.current_term:
            return raft_pb2.RequestVoteResponse(
                term=state.current_term,
                vote_granted=False
            )

        if req.term > state.current_term:
            state.current_term = req.term
            state.voted_for = None
            state.role = "Follower"
        
        if state.voted_for is None or state.voted_for == req.candidate_id:
            state.voted_for = req.candidate_id
            state.last_heartbeat = time.time()
            print(f"[Node {self.state.node_id}] -> Voted for {req.candidate_id}")
            return raft_pb2.RequestVoteResponse(
                term=state.current_term,
                vote_granted=True
            )

        return raft_pb2.RequestVoteResponse(
            term=state.current_term,
            vote_granted=False
        )


    def on_append_entries(self, req):
        if not self.state.alive:
            # simulate crashed node: no response
            raise RuntimeError("Node is dead")
    
        if req.term < self.state.current_term:
            return raft_pb2.AppendEntriesResponse(
                term=self.state.current_term,
                success=False
            )

        self.state.current_term = req.term
        self.state.role = "Follower"
        self.state.last_heartbeat = time.time()
        self.state.voted_for = None


        print(f"[Node {self.state.node_id}] ← heartbeat from {req.leader_id}, term={req.term}")

        return raft_pb2.AppendEntriesResponse(
            term=self.state.current_term,
            success=True
        )
