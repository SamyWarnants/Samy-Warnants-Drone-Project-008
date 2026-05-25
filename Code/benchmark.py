import time
import multiprocessing
import os
import sys

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

def worker_cpu_numpy(duration_sec):
    start_time = time.time()
    # Create large matrices for continuous stress
    size = 1000
    while time.time() - start_time < duration_sec:
        a = np.random.rand(size, size)
        b = np.random.rand(size, size)
        _ = np.dot(a, b)

def worker_cpu_pure(duration_sec):
    start_time = time.time()
    while time.time() - start_time < duration_sec:
        # Intense arithmetic to stress CPU
        n = 5000
        _ = sum([i * i for i in range(n)])

def run_benchmark(level_name, duration_sec):
    total_cores = os.cpu_count() or 4
    
    if level_name == 'light':
        cores_to_use = 1
    elif level_name == 'medium':
        cores_to_use = max(1, total_cores // 2)
    elif level_name == 'hard':
        cores_to_use = total_cores
    else:
        print("Invalid level.")
        return

    print(f"\n--- Starting {level_name.upper()} Benchmark ---")
    print(f"Duration: {duration_sec} seconds ({duration_sec / 60:.1f} minutes)")
    print(f"Using {cores_to_use} out of {total_cores} CPU cores")
    print("Press Ctrl+C to abort...")
    
    try:
        import psutil
        HAS_PSUTIL = True
    except ImportError:
        HAS_PSUTIL = False

    def get_temperature():
        try:
            # Jetson typically stores temperature here
            with open('/sys/devices/virtual/thermal/thermal_zone0/temp', 'r') as f:
                return f"{int(f.read().strip()) / 1000.0:.1f}°C"
        except:
            return "N/A"

    def get_stats():
        stats = []
        if HAS_PSUTIL:
            stats.append(f"CPU: {psutil.cpu_percent()}%")
            stats.append(f"Mem: {psutil.virtual_memory().percent}%")
        else:
            try:
                import subprocess
                out = subprocess.check_output(['free', '-m']).decode('utf-8').splitlines()[1].split()
                mem_pct = (int(out[2]) / int(out[1])) * 100
                stats.append(f"Mem: {mem_pct:.1f}%")
            except:
                stats.append("Mem: N/A")
        stats.append(f"Temp: {get_temperature()}")
        return " | ".join(stats)
    
    target_func = worker_cpu_numpy if HAS_NUMPY else worker_cpu_pure
    
    processes = []
    try:
        for _ in range(cores_to_use):
            p = multiprocessing.Process(target=target_func, args=(duration_sec,))
            processes.append(p)
            p.start()
            
        # Update progress and stats every 10 seconds
        start_time = time.time()
        while time.time() - start_time < duration_sec:
            time.sleep(10)
            elapsed = time.time() - start_time
            if elapsed < duration_sec:
                print(f"[{elapsed / 60:.1f} / {duration_sec / 60:.1f} mins] {get_stats()}")

        for p in processes:
            p.join()
            
        print("\n--- Benchmark Completed Successfully ---")
    except KeyboardInterrupt:
        print("\nBenchmark aborted by user.")
        for p in processes:
            p.terminate()
            p.join()
        sys.exit(0)

if __name__ == "__main__":
    print("========================================")
    print("       Jetson Benchmark Tool            ")
    print("========================================")
    if not HAS_NUMPY:
        print("Warning: NumPy not found. Using pure Python fallback.")
    
    print("\nSelect a usage level:")
    print("1) Light   (Uses 1 CPU core)")
    print("2) Medium  (Uses half of available CPU cores)")
    print("3) Hard    (Uses all available CPU cores)")
    
    choice = input("\nEnter choice (1/2/3) or (light/medium/hard): ").strip().lower()
    
    level_map = {
        '1': 'light', 'light': 'light',
        '2': 'medium', 'medium': 'medium',
        '3': 'hard', 'hard': 'hard'
    }
    
    if choice not in level_map:
        print(f"Invalid choice '{choice}', defaulting to 'medium'")
        level = 'medium'
    else:
        level = level_map[choice]

    # Each test runs for 10 minutes (600 seconds)
    duration = 600
    
    run_benchmark(level, duration)
