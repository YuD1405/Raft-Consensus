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
        self._lock = RLock()

        # Leader volatile state (only meaningful when role == Leader)
        self.next_index = {}
        self.match_index = {}

    def start(self):
        print(f"[Node {self.state.node_id}] starting")
        self.logic.start()

    def disconnect(self):
        with self._lock:
            self.state.connected = False
            if self.state.role == "Leader":
                self.state.role = "Follower"

    def reconnect(self):
        with self._lock:
            self.state.connected = True
            self.state.last_heartbeat = time.time()

    def append_local_log(self, command: str) -> int:
        with self._lock:
            entry = (int(self.state.current_term), str(command))
            self.state.log.append(entry)
            return len(self.state.log) - 1

    # RPC HANDLERS
    def on_request_vote(self, req):
        if not self.state.alive or not self.state.connected:
            return raft_pb2.RequestVoteResponse(
                term=self.state.current_term,
                vote_granted=False
            )

        if req.term < self.state.current_term:
            return raft_pb2.RequestVoteResponse(
                term=self.state.current_term,
                vote_granted=False
            )

        self.state.current_term = req.term
        self.state.voted_for = req.candidate_id
        self.state.last_heartbeat = time.time()

        return raft_pb2.RequestVoteResponse(
            term=self.state.current_term,
            vote_granted=True
        )

    def on_append_entries(self, req):
        if not self.state.alive or not self.state.connected:
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

        with self._lock:
            # Accept leader term and step down.
            if req.term > self.state.current_term:
                self.state.current_term = req.term
                self.state.voted_for = None

            self.state.role = "Follower"
            self.state.last_heartbeat = time.time()
            self.state.last_leader_id = int(req.leader_id)

            if not req.entries:
                print(f"Received heartbeat from {req.leader_id}")
            else:
                print(
                    f"Received AppendEntries from {req.leader_id} entries={len(req.entries)}")

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

            return raft_pb2.AppendEntriesResponse(
                term=self.state.current_term,
                success=True,
                match_index=last_index if req.entries else req.prev_log_index
            )

    def on_submit_command(self, req):
        if not self.state.alive or not self.state.connected:
            return raft_pb2.ClientCommandReply(
                accepted=False,
                leader_id=int(self.state.last_leader_id),
                term=int(self.state.current_term),
                index=-1,
                message="Node unavailable",
            )

        with self._lock:
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
        with self._lock:
            return raft_pb2.LogReply(
                entries=[raft_pb2.LogEntry(term=t, command=c)
                         for (t, c) in self.state.log],
                commit_index=int(self.state.commit_index),
            )
