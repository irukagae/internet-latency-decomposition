import os
import re
import time
import uuid
import threading
import subprocess
from datetime import datetime, UTC
from scapy.all import conf
from pathlib import Path

from collection.experiment.runner import run_expt
from collection.capture.passive import capture_packets
from collection.persistence.csv_writer import write_passive_packets, write_active_probe

project_root = Path(__file__).resolve().parent.parent
data_dir = project_root / "data" / "raw"

def get_active_interface():
    """Returns the interface currently used by windows to send traffic to the internet"""

    conf.route.resync()  # force scapy to refresh its routing table from the OS to detect VPN changes

    result = subprocess.run(["mullvad", "status"], capture_output=True, text=True)
    status_output = result.stdout.strip()

    if "Connected" in status_output:
        # mullvad is active: extract tunnel IP from ipconfig's Mullvad adapter section
        ipconfig = subprocess.run(["ipconfig"], capture_output=True, text=True)
        lines = ipconfig.stdout.splitlines()

        mullvad_section = False
        for  line in lines:
            if "Mullvad" in line:
                mullvad_section = True  # entered the mullvad adapter section in ipconfig
            if mullvad_section and "IPv4 Address" in line:
                # extract IP from line like: "   IPv4 Address. . . : 10.141.190.96"
                match = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                if match:
                    tunnel_ip = match.group(1)
                    route_info = conf.route.route("0.0.0.0")
                    iface = route_info[0]
                    return iface, tunnel_ip

    # VPN not connected or India baseline: use normal routing
    route_info = conf.route.route("0.0.0.0")
    iface = route_info[0]
    src_ip = route_info[1]
    return iface, src_ip

def connect_vpn(location_code: str, warmup_time = 60):
    """Connects Mullvad VPN to the desired location."""

    print(f"[VPN] Connecting to {location_code.upper()}")

    old_iface, old_ip = get_active_interface()  #unpack the tuple to store both old interface and old IP

    os.system(f"mullvad relay set location {location_code}")
    os.system("mullvad connect")

    print("[VPN] Waiting for routing convergence...")

    start = time.time()
    while time.time() - start < warmup_time:
        result = subprocess.run(["mullvad", "status"], capture_output=True, text=True)
        status = result.stdout.strip()

        if "Connected" in status:
            iface, tunnel_ip = get_active_interface()
            print(f"[VPN] Tunnel active | Tunnel IP: {tunnel_ip}\n")
            return iface, tunnel_ip

        print(f"[VPN] Status: {status.splitlines()[0]} - waiting...")
        time.sleep(3)

    raise RuntimeError("VPN routing did not stabilize in time.")

def disconnect_vpn():
    """Disconnects Mullvad VPN"""

    print("[VPN] Disconnecting Mullvad VPN...\n")
    os.system("mullvad disconnect")
    time.sleep(3)

protocol = ["tcp", "icmp", "udp"]
packet_size = [64, 128, 256, 512, 1024, 1400]
locations = ["us", "jp", "de"]

num_probes = 30
probe_interval = 0.25
timeout = 1.0

def warmup_tunnel(protocol="icmp", dst_ip="8.8.8.8", src_ip=None, iface=None):
    print("[INFO] Running VPN warmup probes...")

    run_expt(protocol, dst_ip, src_ip, packet_size=64, num_probes=7, probe_interval=0.2, timeout=1.0, iface=iface, record=False)

    print("[INFO] Warmup completed.\n")

def run_single_expt(protocol, packet_size, dst_ip, source_location, vpn_provider, target):
    expt_id = uuid.uuid4().hex
    timestamp = datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%S')

    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"[EXPT] ID = {expt_id}")
    print(f"[EXPT] Protocol={protocol}, Size={packet_size}, Src={source_location}, Target={target}")

    active_iface, src_ip = get_active_interface()
    print(f"[INFO] Using interface: {active_iface}")

    capture_start = time.time()
    estimated_duration = (num_probes * probe_interval + timeout + 2.0)
    capture_end = capture_start + estimated_duration

    # passive capture
    packets = []

    def passive_task():
        captured = capture_packets(interface=active_iface, start_time=capture_start, end_time=capture_end)
        packets.extend(captured)

    passive_thread = threading.Thread(target=passive_task)
    passive_thread.start()

    # active probing runs concurrently while passive thread  is sniffing
    results = run_expt(protocol=protocol, dst_ip=dst_ip, src_ip=src_ip, packet_size=packet_size,
                       num_probes=num_probes, probe_interval=probe_interval, timeout=timeout, iface=active_iface)

    passive_thread.join()  # wait for passive capture to finish before proceeding

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

            active_iface, src_ip = get_active_interface()
            warmup_tunnel(src_ip=src_ip, iface=active_iface)

        for tar in target:
            for prt in protocol:
                for pktsize in packet_size:
                    run_single_expt(protocol=prt, packet_size=pktsize,
                                    dst_ip=tar, source_location=loc,
                                    vpn_provider=vpn_provider, target=tar)

    disconnect_vpn()

    print("ALL EXPERIMENT COMPLETED.")

if __name__ == '__main__':
    main()