import os
import time
import uuid
from datetime import datetime

from collection.experiment.runner import run_expt
from collection.capture.passive import capture_packets
from collection.persistence.csv_writer import write_passive_packets, write_active_probe

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

network_interface = "wlan0"

def run_single_expt(protocol, packet_size, dst_ip, source_location, vpn_provider):
    expt_id = uuid.uuid4().hex
    timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

    output_dir = os.path.join("data", "raw")
    os.makedirs(output_dir, exist_ok=True)

    print(f"[EXPT] ID = {expt_id}")
    print(f"[EXPT] Protocol={protocol}, Size={packet_size}, Src={source_location}")

    capture_start = time.time()
    estimated_duration = (num_probes * probe_interval + timeout + 2.0)
    capture_end = capture_start + estimated_duration

    # passive capture
    packets = capture_packets(interface=network_interface, start_time=capture_start, end_time=capture_end)

    # active probing
    results = run_expt(protocol=protocol, dst_ip=dst_ip, packet_size=packet_size,
                       num_probes=num_probes, probe_interval=probe_interval, timeout=timeout)

    for row in results:
        row["source_location"] = source_location
        row["vpn_provider"] = vpn_provider
        row["experiment_id"] = expt_id
        row["timestamp"] = timestamp

    write_active_probe(results, os.path.join(output_dir, f"active_probe_raw_{datetime.now().strftime('%Y_%M')}.csv"))
    write_passive_packets(packets, os.path.join(output_dir, f"passive_probe_raw_{datetime.now().strftime('%Y_%M')}.csv"),
                          source_location=source_location, vpn_provider=vpn_provider, experiment_id=expt_id,
                          experiment_timestamp=timestamp)

    print(f"[EXPT] Completed -> {output_dir}\n")

def main():
    target = "8.8.8.8"

    print("STARTING DATA COLLECTION...\n")

    for loc in locations:
        if loc == "in":
            disconnect_vpn()
            vpn_provider = "None"
        else:
            connect_vpn(loc)
            vpn_provider = "Mullvad"

        for prt in protocol:
            for pktsize in packet_size:
                run_single_expt(protocol=prt, packet_size=pktsize,
                                dst_ip=target, source_location=loc,
                                vpn_provider=vpn_provider)

    disconnect_vpn()



    print("ALL EXPERIMENT COMPLETED.")


if __name__ == '__main__':
    main()