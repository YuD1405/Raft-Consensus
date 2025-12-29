import time
import random
from threading import Thread
import os
from rpc import raft_pb2

ELECTION_TIMEOUT = (5, 10)
HEARTBEAT_INTERVAL = 1
MAX_APPEND_BATCH = 10


def set_title(title):
    os.system(f'title "{title}"')


class RaftLogic:
    def __init__(self, node):
        self.node = node

    def start(self):
        Thread(target=self.election_loop, daemon=True).start()

    def election_loop(self):
        while self.node.state.alive:
            if not self.node.state.connected:
                time.sleep(0.1)
                continue
            if self.node.state.role != "Leader":
                timeout = random.uniform(*ELECTION_TIMEOUT)
                if time.time() - self.node.state.last_heartbeat > timeout:
                    self.start_election()
            time.sleep(0.1)

    def start_election(self):
        state = self.node.state
        if not state.connected or not state.alive:
            return
        state.role = "Candidate"
        state.current_term += 1
        state.voted_for = state.node_id
        votes = 1

        set_title(
            f"RAFT Node {state.node_id} | CANDIDATE | term={state.current_term}"
        )
        print(
            f"RAFT Node {state.node_id} | CANDIDATE | term={state.current_term}")

        for peer in state.peers:
            try:
                resp = self.node.rpc_clients[peer].request_vote(
                    term=state.current_term,
                    candidate_id=state.node_id
                )
                if resp.vote_granted:
                    votes += 1
            except:
                pass

        if votes > (len(state.peers) + 1) // 2:
            self.become_leader()

    def become_leader(self):
        self.node.state.role = "Leader"
        set_title(
            f"RAFT Node {self.node.state.node_id} | LEADER"
        )
        print(f"RAFT Node {self.node.state.node_id} | LEADER")

        with self.node._lock:
            last_index = len(self.node.state.log)
            self.node.next_index = {
                peer: last_index for peer in self.node.state.peers}
            self.node.match_index = {
                peer: -1 for peer in self.node.state.peers}

        Thread(target=self.heartbeat_loop, daemon=True).start()

    def heartbeat_loop(self):
        while (
            self.node.state.alive
            and self.node.state.connected
            and self.node.state.role == "Leader"
        ):
            for peer in self.node.state.peers:
                self.replicate_to_peer(peer)

            self.advance_commit_index()
            time.sleep(HEARTBEAT_INTERVAL)

    def replicate_to_peer(self, peer: int):
        state = self.node.state
        if state.role != "Leader":
            return

        with self.node._lock:
            next_idx = int(self.node.next_index.get(peer, len(state.log)))
            prev_idx = next_idx - 1
            prev_term = 0
            if prev_idx >= 0 and prev_idx < len(state.log):
                prev_term = int(state.log[prev_idx][0])
            entries_slice = state.log[next_idx: next_idx + MAX_APPEND_BATCH]
            entries = [raft_pb2.LogEntry(term=t, command=c)
                       for (t, c) in entries_slice]
            leader_commit = int(state.commit_index)
            current_term = int(state.current_term)
            leader_id = int(state.node_id)

        # Demo visibility (similar to earlier version)
        if len(entries) == 0:
            print(f"Sent heartbeat to {peer}")
        else:
            print(f"Sent AppendEntries to {peer} entries={len(entries)}")

        try:
            resp = self.node.rpc_clients[peer].append_entries(
                term=current_term,
                leader_id=leader_id,
                prev_log_index=int(prev_idx),
                prev_log_term=int(prev_term),
                entries=entries,
                leader_commit=leader_commit,
            )
        except:
            return

        if resp.term > current_term:
            with self.node._lock:
                state.current_term = int(resp.term)
                state.role = "Follower"
                state.voted_for = None
            return

        if resp.success:
            with self.node._lock:
                match_idx = int(resp.match_index)
                self.node.match_index[peer] = match_idx
                self.node.next_index[peer] = match_idx + 1
        else:
            with self.node._lock:
                self.node.next_index[peer] = max(
                    0, int(self.node.next_index.get(peer, 0)) - 1)

    def advance_commit_index(self):
        state = self.node.state
        if state.role != "Leader":
            return

        with self.node._lock:
            last_index = len(state.log) - 1
            if last_index < 0:
                return

            match_indexes = [last_index]
            match_indexes.extend(int(self.node.match_index.get(p, -1))
                                 for p in state.peers)
            match_indexes.sort(reverse=True)

            majority_pos = (len(match_indexes) - 1) // 2
            candidate_index = match_indexes[majority_pos]
            if candidate_index > state.commit_index:
                # Only commit entries from current term (simplified Raft rule).
                if 0 <= candidate_index < len(state.log) and int(state.log[candidate_index][0]) == int(state.current_term):
                    state.commit_index = int(candidate_index)
