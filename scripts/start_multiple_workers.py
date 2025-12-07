"""
Helper script to start multiple mock workers for testing.
Each worker runs in a separate process.
"""
import subprocess
import sys
import os
import time

def start_workers(num_workers: int = 3):
    """Start multiple worker processes."""
    print(f"Starting {num_workers} workers...")
    print("Press Ctrl+C to stop all workers\n")
    
    processes = []
    
    try:
        for i in range(num_workers):
            # Start each worker in a new process
            # On Windows, use start to open new windows
            if sys.platform == "win32":
                # Windows: start in new console window
                process = subprocess.Popen(
                    [sys.executable, "scripts/mock_worker.py"],
                    cwd=os.path.dirname(os.path.dirname(__file__)),
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                # Linux/Mac: run in background
                process = subprocess.Popen(
                    [sys.executable, "scripts/mock_worker.py"],
                    cwd=os.path.dirname(os.path.dirname(__file__))
                )
            
            processes.append(process)
            print(f"✅ Started worker {i+1}/{num_workers} (PID: {process.pid})")
            time.sleep(1)  # Stagger startup
        
        print(f"\n✅ All {num_workers} workers started!")
        print("Workers are running in separate windows/processes.")
        print("Run the dashboard to see results from all workers.")
        print("\nPress Ctrl+C to stop all workers...")
        
        # Wait for user interrupt
        while True:
            time.sleep(1)
            # Check if any process died
            for i, proc in enumerate(processes):
                if proc.poll() is not None:
                    print(f"⚠️  Worker {i+1} (PID: {proc.pid}) has stopped")
    
    except KeyboardInterrupt:
        print("\n\nStopping all workers...")
        for i, proc in enumerate(processes):
            try:
                proc.terminate()
                print(f"Stopped worker {i+1} (PID: {proc.pid})")
            except:
                pass
        print("All workers stopped.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Start multiple mock workers")
    parser.add_argument(
        "-n", "--num-workers",
        type=int,
        default=3,
        help="Number of workers to start (default: 3)"
    )
    args = parser.parse_args()
    
    start_workers(args.num_workers)

