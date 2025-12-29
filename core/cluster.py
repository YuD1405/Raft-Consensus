# core/cluster_manager.py
import subprocess
import sys
import os
import time
import re


class ClusterManager:
    def __init__(self):
        self.nodes = []        # [{id, port, process}]
        self.running = False
        self._starting = False

    def _venv_python(self):
        # Prefer workspace venv if present so node processes use the same deps.
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate = os.path.join(repo_root, ".venv", "Scripts", "python.exe")
        return candidate if os.path.exists(candidate) else sys.executable

    def _kill_process_on_port(self, port: int):
        # Best-effort cleanup for orphaned processes holding ports (common on Windows).
        try:
            out = subprocess.check_output(
                ["cmd.exe", "/c", f"netstat -ano | findstr :{port}"],
                stderr=subprocess.STDOUT,
                text=True,
            )
        except Exception:
            return

        pids = set()
        for line in out.splitlines():
            # Typical: TCP    0.0.0.0:5001   0.0.0.0:0   LISTENING   1234
            if "LISTENING" not in line.upper():
                continue
            parts = re.split(r"\s+", line.strip())
            if not parts:
                continue
            pid = parts[-1]
            if pid.isdigit():
                pids.add(pid)

        for pid in pids:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    def is_running(self):
        return self.running

    def resize(self, n):
        if self.running:
            return
        self.nodes = []
        base_port = 5000
        for i in range(n):
            self.nodes.append({
                "id": i + 1,
                "port": base_port + i + 1,
                "process": None
            })

    def start_all(self):
        if self.running or self._starting:
            return

        self._starting = True
        try:
            # Always cleanup before starting to avoid stale ports/logs.
            self.stop_all()

            peer_args = []
            for node in self.nodes:
                peer_args.append(f"{node['id']}@localhost:{node['port']}")

            peer_str = ",".join(peer_args)

            for node in self.nodes:
                python_exe = self._venv_python()
                python_cmd = (
                    f'"{python_exe}" run_node.py '
                    f'--id {node["id"]} '
                    f'--port {node["port"]} '
                    f'--peers "{peer_str}"'
                )

                full_cmd = (
                    f'cmd.exe /k '
                    f'title RAFT-NODE-{node["id"]} && '
                    f'{python_cmd}'
                )

                node["process"] = subprocess.Popen(
                    full_cmd,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )

            self.running = True
        finally:
            self._starting = False

    def stop_all(self):
        for node in self.nodes:
            proc = node["process"]
            if proc:
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except Exception as e:
                    print(f"Failed to stop node {node['id']}: {e}")

                node["process"] = None

        # Give Windows a moment to release ports.
        time.sleep(0.2)

        # Extra safety: free ports even if user closed consoles manually.
        for node in self.nodes:
            try:
                self._kill_process_on_port(int(node["port"]))
            except Exception:
                pass

        self.running = False
