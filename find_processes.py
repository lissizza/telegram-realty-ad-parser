#!/usr/bin/env python3
import os
import subprocess
import signal

def find_python_processes():
    """Find all Python processes"""
    try:
        # Try to find processes using /proc
        pids = []
        for pid in os.listdir('/proc'):
            if pid.isdigit():
                try:
                    with open(f'/proc/{pid}/comm', 'r') as f:
                        comm = f.read().strip()
                    if 'python' in comm:
                        pids.append(pid)
                except:
                    continue
        return pids
    except:
        return []

def kill_processes(pids):
    """Kill processes by PID"""
    for pid in pids:
        try:
            print(f"Killing process {pid}")
            os.kill(int(pid), signal.SIGTERM)
        except:
            try:
                os.kill(int(pid), signal.SIGKILL)
            except:
                pass

if __name__ == "__main__":
    print("Looking for Python processes...")
    pids = find_python_processes()
    print(f"Found Python processes: {pids}")
    
    if pids:
        print("Killing processes...")
        kill_processes(pids)
        print("Done!")
    else:
        print("No Python processes found")

