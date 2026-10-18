import sys
import time
import subprocess
import argparse
import csv
import re
import psutil

def get_ovs_pid():
    for p in psutil.process_iter(['name', 'cmdline']):
        try:
            if 'ovs-vswitchd' in p.info['name'] or (p.info['cmdline'] and any('ovs-vswitchd' in c for c in p.info['cmdline'])):
                return p.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def clear_ovs_stats():
    subprocess.run(["ovs-appctl", "dpif-netdev/pmd-stats-clear"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_pmd_stats():
    res = subprocess.run(["ovs-appctl", "dpif-netdev/pmd-stats-show"], capture_output=True, text=True)
    out = res.stdout
    rx = tx = megaflow_hits = lookups_per_hit = 0
    
    rx_m = re.search(r"Rx packets:\s+(\d+)", out)
    tx_m = re.search(r"Tx packets:\s+(\d+)", out)
    mf_m = re.search(r"Megaflow hits:\s+(\d+)\s+\([^\)]+,\s*([\d\.]+)\s+subtbl lookups/hit\)", out)
    
    if rx_m: rx = int(rx_m.group(1))
    if tx_m: tx = int(tx_m.group(1))
    if mf_m:
        megaflow_hits = int(mf_m.group(1))
        lookups_per_hit = float(mf_m.group(2))
    return rx, tx, megaflow_hits, lookups_per_hit

def run_test(scenario, duration_sec=15):
    print(f"=== Starting Benchmark for Scenario: {scenario} ===")
    ovs_pid = get_ovs_pid()
    if not ovs_pid:
        print("[!] Error: ovs-vswitchd is not running.")
        sys.exit(1)
    
    proc = psutil.Process(ovs_pid)
    clear_ovs_stats()
    
    print("[*] Replaying PCAP traffic in ns1...")
    pcap_cmd = "tcpreplay --topspeed --loop=3 -i veth1 benchmark_traffic.pcap"
    replay_proc = subprocess.Popen(
        ["ip", "netns", "exec", "ns1", "bash", "-c", pcap_cmd],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    
    cpu_records = []
    mem_records = []
    start_time = time.time()
    
    while time.time() - start_time < duration_sec:
        cpu = proc.cpu_percent(interval=0.2)
        mem = proc.memory_info().rss / (1024 * 1024)
        cpu_records.append(cpu)
        mem_records.append(mem)
        if replay_proc.poll() is not None:
            break
            
    try:
        replay_proc.kill()
    except:
        pass
        
    rx, tx, mf_hits, lookups_per_hit = get_pmd_stats()
    avg_cpu = sum(cpu_records) / len(cpu_records) if cpu_records else 0
    max_cpu = max(cpu_records) if cpu_records else 0
    avg_mem = sum(mem_records) / len(mem_records) if mem_records else 0
    elapsed = max(time.time() - start_time, 0.001)
    mpps = (rx / elapsed) / 1e6
    
    ping_res = subprocess.run(
        ["ip", "netns", "exec", "ns1", "ping", "-c", "20", "-i", "0.2", "10.0.0.2"],
        capture_output=True, text=True
    )
    rtt_match = re.search(r"rtt min/avg/max/mdev = ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)", ping_res.stdout)
    rtt_avg = float(rtt_match.group(2)) if rtt_match else 0.0

    result = {
        "Scenario": scenario,
        "Total_Rx_Packets": rx,
        "Total_Tx_Packets": tx,
        "Throughput_Mpps": round(mpps, 4),
        "Subtbl_Lookups_per_Hit": lookups_per_hit,
        "Megaflow_Hits": mf_hits,
        "Avg_CPU_Percent": round(avg_cpu, 2),
        "Max_CPU_Percent": round(max_cpu, 2),
        "Avg_Memory_MB": round(avg_mem, 2),
        "Avg_RTT_Latency_ms": round(rtt_avg, 3)
    }
    
    filename = f"results_{scenario.lower()}.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=result.keys())
        writer.writeheader()
        writer.writerow(result)
        
    print(f"[+] Benchmark completed! Results saved to: {filename}")
    print(result)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, choices=["BASE", "LOCAL", "GLOBAL_AI", "FULL_TIER"])
    args = parser.parse_args()
    run_test(args.scenario)
