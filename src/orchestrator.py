import time
import uuid
import threading
from datetime import datetime, UTC
from scapy.all import conf
from pathlib import Path

from collection.experiment.runner import run_expt
from collection.capture.passive import capture_packets
from collection.persistence.csv_writer import write_passive_packets, write_active_probe

#resolve project root dynamically so the script works regardless of working directory
project_root = Path(__file__).resolve().parent.parent
data_dir = project_root / "data" / "raw"

def get_active_interface():
    """Returns the interface currently used by windows to send traffic to the internet

       Forces scapy to resync its routing table from the OS before querying, ensuring stable cache doesn't
       return outdated interface information"""

    conf.route.resync()  # force scapy to refresh its routing table from the OS to detect VPN changes

    route_info = conf.route.route("0.0.0.0")  #query default route
    iface = route_info[0]
    src_ip = route_info[1]
    return iface, src_ip

# experiment parameters
protocol = ["tcp", "icmp", "udp"] # protocols to probe with
packet_size = [64, 128, 256, 512, 1024, 1400]  # packet sizes in bytes to vary D_trans
location = "in"  # source location hardcoded to INDIA

# probe configuration
num_probes = 30  # number of probes per experiment
probe_interval = 0.25  # seconds between consecutive probes
timeout = 1.0  # seconds to wait for a response before marking probe a failure

def get_week_of_month():
    """Returns the week of the month as w1/w2/w3/w4/w5 based on the current day."""

    day = datetime.now().day
    week_num = (day - 1) // 7+1
    return f"w{week_num}"

def run_single_expt(protocol, packet_size, dst_ip, source_location, target):
    """Executes a single end-to-end experiment: passive capture + active probing + CSV writing

       Generates a unique Experiment ID and UTC timestamp for full traceability.
       Passive capture and active probing works concurrently via threading to ensure background traffic is captured
       simultaneously with RTT measurement."""

    expt_id = uuid.uuid4().hex  # unique Experiment ID to join active ans passive CSVs later
    timestamp = datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%S')  # UTC timestamp for consistency

    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"[EXPT] ID = {expt_id}")
    print(f"[EXPT] Protocol={protocol}, Size={packet_size}, Src={source_location}, Target={target}")

    active_iface, src_ip = get_active_interface()
    print(f"[INFO] Using interface: {active_iface}")

    # calculate capture window - passive sniffer runs exactly for this duration
    capture_start = time.time()
    estimated_duration = (num_probes * probe_interval + timeout + 2.0)  # 2sec buffer for safety
    capture_end = capture_start + estimated_duration

    # passive capture runs in a background thread concurrently with active probing
    packets = []

    def passive_task():
        captured = capture_packets(interface=active_iface, start_time=capture_start, end_time=capture_end)
        packets.extend(captured)

    passive_thread = threading.Thread(target=passive_task)
    passive_thread.start()

    # active probing runs on main thread while passive thread sniffs background traffic
    results = run_expt(protocol=protocol, dst_ip=dst_ip, src_ip=src_ip, packet_size=packet_size,
                       num_probes=num_probes, probe_interval=probe_interval, timeout=timeout, iface=active_iface)

    passive_thread.join()  # wait for passive capture to finish before proceeding

    for row in results:
        row["source_location"] = source_location
        row["experiment_id"] = expt_id
        row["timestamp"] = timestamp

    file_label = f"{datetime.now().strftime('%Y_%m')}_{get_week_of_month()}"
    write_active_probe(results, str(data_dir / f"active_probe_raw_{file_label}.csv"))
    write_passive_packets(packets, str(data_dir / f"passive_probe_raw_{file_label}.csv"),
                          source_location=source_location, experiment_id=expt_id,
                          experiment_timestamp=timestamp)

    print(f"[EXPT] Completed -> {data_dir}\n")

def main():
    target = ["8.8.8.8", "1.1.1.1", "94.140.14.14", "185.222.222.222", "45.11.45.11"]

    print("STARTING DATA COLLECTION...\n")

    for tar in target:
        for prt in protocol:
            for pktsize in packet_size:
                run_single_expt(protocol=prt, packet_size=pktsize,
                                dst_ip=tar, source_location=location, target=tar)

    print("ALL EXPERIMENT COMPLETED.")

if __name__ == '__main__':
    main()