from core.state import RaftState
from core.raft import RaftLogic
from rpc import raft_pb2
import time
from threading import RLock


class RaftNode:
    def __init__(self, node_id, peers, rpc_clients):
        self.state = RaftState(node_id, peers)
        self.rpc_clients = rpc_clients
        self.logic = RaftLogic(self)

        # Leader volatile state (only meaningful when role == Leader)
        self.next_index = {}
        self.match_index = {}
        

    def start(self):
        print(f"[Node {self.state.node_id}] starting")
        self.logic.start()

    def disconnect(self):
        print(f"[Node {self.state.node_id}] Disconnected")
        self.state.connected = False
        if self.state.role == "Leader":
            self.state.role = "Follower"

    def reconnect(self):
        print(f"[Node {self.state.node_id}] Connected")

        self.state.connected = True
        self.state.last_heartbeat = time.time()

    def is_blocked(self, peer_id: int) -> bool:
        return peer_id in self.state.blocked_peers
    
    def append_local_log(self, command: str) -> int:
        
            entry = (int(self.state.current_term), str(command))
            self.state.log.append(entry)
            return len(self.state.log) - 1

    # RPC HANDLERS
    def on_request_vote(self, req):
        state = self.state
        if not self.state.connected:
            return raft_pb2.RequestVoteResponse(
                term=self.state.current_term,
                vote_granted=False
            )

        if req.term < self.state.current_term:
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
        if not self.state.connected:
            return raft_pb2.AppendEntriesResponse(
                term=self.state.current_term,
                success=False,
                match_index=-1
            )

        if req.term < self.state.current_term:
            return raft_pb2.AppendEntriesResponse(
                term=self.state.current_term,
                success=False,
                match_index=-1
            )

        
        # Accept leader term and step down.
        if req.term > self.state.current_term:
            self.state.current_term = req.term
            self.state.voted_for = None

        self.state.role = "Follower"
        self.state.last_heartbeat = time.time()
        self.state.last_leader_id = int(req.leader_id)

        if not req.entries:
            print(f"[Node {self.state.node_id}] ← Received heartbeat from {req.leader_id}, term={req.term}")
        else:
            print(f"[Node {self.state.node_id}] ← Received AppendEntries from {req.leader_id} entries={len(req.entries)}")

        # Log consistency check.
        if req.prev_log_index >= 0:
            if req.prev_log_index >= len(self.state.log):
                return raft_pb2.AppendEntriesResponse(
                    term=self.state.current_term,
                    success=False,
                    match_index=len(self.state.log) - 1
                )
            prev_term = self.state.log[req.prev_log_index][0]
            if prev_term != req.prev_log_term:
                # Conflict: reject so leader backs up.
                return raft_pb2.AppendEntriesResponse(
                    term=self.state.current_term,
                    success=False,
                    match_index=req.prev_log_index - 1
                )

        # Remove any conflicting entries after prev_log_index, then append new ones.
        truncate_from = req.prev_log_index + 1
        if truncate_from < len(self.state.log):
            self.state.log = self.state.log[:truncate_from]

        if req.entries:
            for e in req.entries:
                self.state.log.append((int(e.term), str(e.command)))

        if len(self.state.log) == 0:
            last_index = -1
        else:
            last_index = len(self.state.log) - 1

        # Commit index update.
        if req.leader_commit is not None:
            self.state.commit_index = min(
                int(req.leader_commit), last_index)
            self.logic.apply_committed_entries()

        self.logic.rebuild_state_machine()
        
        return raft_pb2.AppendEntriesResponse(
            term=self.state.current_term,
            success=True,
            match_index=last_index if req.entries else req.prev_log_index
        )

    def on_submit_command(self, req):
        if not self.state.connected:
            return raft_pb2.ClientCommandReply(
                accepted=False,
                leader_id=int(self.state.last_leader_id),
                term=int(self.state.current_term),
                index=-1,
                message="Node unavailable",
            )

        
        if self.state.role != "Leader":
            return raft_pb2.ClientCommandReply(
                accepted=False,
                leader_id=int(self.state.last_leader_id),
                term=int(self.state.current_term),
                index=-1,
                message="Not leader",
            )

        idx = self.append_local_log(str(req.command))
        return raft_pb2.ClientCommandReply(
            accepted=True,
            leader_id=int(self.state.node_id),
            term=int(self.state.current_term),
            index=int(idx),
            message="Appended",
        )

    def get_log_reply(self):
        
            return raft_pb2.LogReply(
                entries=[raft_pb2.LogEntry(term=t, command=c)
                         for (t, c) in self.state.log],
                commit_index=int(self.state.commit_index),
            )
