import os
import time
import uuid
from datetime import datetime, UTC
from scapy.all import get_if_list, get_if_addr
from pathlib import Path

from collection.experiment.runner import run_expt
from collection.capture.passive import capture_packets
from collection.persistence.csv_writer import write_passive_packets, write_active_probe

project_root = Path(__file__).resolve().parent.parent
data_dir = project_root / "data" / "raw"

def get_active_interface():
    """Automatically identifies the currently active network interface."""

    for iface in get_if_list():
        try:
            ip = get_if_addr(iface)
            if ip.startswith("10.") or ip.startswith("192.") or ip.startswith("172."):
                return iface

        except Exception:
            continue

    return None

def connect_vpn(location_code: str, warmup_time = 15):
    """Connects Mullvad VPN to the desired location."""

    print(f"[VPN] Connecting to {location_code.upper()}")

    os.system(f"mullvad relay set location {location_code}")
    os.system("mullvad connect")

    print("[VPN] Waiting for tunnel stabilization...\n")
    time.sleep(warmup_time)
    print("[VPN] Tunnel stabilization completed...\n")

def disconnect_vpn():
    """Disconnects Mullvad VPN"""

    print("[VPN] Disconnecting Mullvad VPN...\n")
    os.system("mullvad disconnect")
    time.sleep(5)

protocol = ["tcp", "icmp", "udp"]
packet_size = [64, 128, 256, 512, 1024, 1400]
locations = ["in", "us", "jp", "de"]

num_probes = 30
probe_interval = 0.25
timeout = 1.0

def run_single_expt(protocol, packet_size, dst_ip, source_location, vpn_provider):
    expt_id = uuid.uuid4().hex
    timestamp = datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%S')

    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"[EXPT] ID = {expt_id}")
    print(f"[EXPT] Protocol={protocol}, Size={packet_size}, Src={source_location}")

    active_iface = get_active_interface()

    capture_start = time.time()
    estimated_duration = (num_probes * probe_interval + timeout + 2.0)
    capture_end = capture_start + estimated_duration

    # passive capture
    packets = capture_packets(interface=active_iface, start_time=capture_start, end_time=capture_end)

    # active probing
    results = run_expt(protocol=protocol, dst_ip=dst_ip, packet_size=packet_size,
                       num_probes=num_probes, probe_interval=probe_interval, timeout=timeout)

    for row in results:
        row["source_location"] = source_location
        row["vpn_provider"] = vpn_provider
        row["experiment_id"] = expt_id
        row["timestamp"] = timestamp

    write_active_probe(results, str(data_dir / f"active_probe_raw_{datetime.now().strftime('%Y_%m')}.csv"))
    write_passive_packets(packets, str(data_dir / f"passive_probe_raw_{datetime.now().strftime('%Y_%m')}.csv"),
                          source_location=source_location, vpn_provider=vpn_provider, experiment_id=expt_id,
                          experiment_timestamp=timestamp)

    print(f"[EXPT] Completed -> {data_dir}\n")

def main():
    target = ["8.8.8.8", "1.1.1.1", "9.9.9.9"]

    print("STARTING DATA COLLECTION...\n")

    for loc in locations:
        if loc == "in":
            disconnect_vpn()
            vpn_provider = "None"
        else:
            connect_vpn(loc)
            vpn_provider = "Mullvad"

        for tar in target:
            for prt in protocol:
                for pktsize in packet_size:
                    run_single_expt(protocol=prt, packet_size=pktsize,
                                    dst_ip=tar, source_location=loc,
                                    vpn_provider=vpn_provider)

    disconnect_vpn()

    print("ALL EXPERIMENT COMPLETED.")

if __name__ == '__main__':
    main()