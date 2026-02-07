import pandas as pd
import os
from scapy.layers.inet import IP, TCP, UDP, ICMP

def write_active_probe(results, output_path):
    """Write active probe RTT results to a csv using pandas"""

    # ensures parent directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    df = pd.DataFrame(results)

    columns = ["timestamp", "experiment_id", "source_location", "vpn_provider", "protocol",
               "dst_ip", "packet_size", "probe_index", "success",
               "rtt_ms", "send_timestamp", "recv_timestamp"]

    df = df[columns]

    file_exists = os.path.exists(output_path)
    df.to_csv(output_path, mode="a", header=not file_exists, index=False)

def write_passive_packets(packets, output_path, source_location,
                          vpn_provider, experiment_id, experiment_timestamp):
    """Writes passively captured packets to csv."""

    # ensures parent directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    rows = []

    for pkt in packets:
        if IP not in pkt:
            continue  # ignores non-IP packets

        protocol = "OTHER"
        tcp_flag = None
        window_size = None

        if TCP in pkt:
            protocol = "TCP"
            tcp_flag = pkt[TCP].flags
            window_size = pkt[TCP].window
        elif UDP in pkt:
            protocol = "UDP"
        elif ICMP in pkt:
            protocol = "ICMP"

        rows.append({"timestamp": pkt.time, "src_ip": pkt[IP].src, "dst_ip": pkt[IP].dst,
                     "protocol": protocol, "packet_length": len(pkt), "ttl": pkt[IP].ttl,
                     "tcp_flag": tcp_flag, "window_size": window_size,
                     "source_location": source_location, "vpn_provider": vpn_provider,
                     "experiment_id": experiment_id, "experiment_timestamp": experiment_timestamp})

    df = pd.DataFrame(rows)

    columns = ["timestamp", "src_ip", "dst_ip", "protocol",
               "packet_length", "ttl", "tcp_flag", "window_size",
               "source_location", "vpn_provider",
               "experiment_id", "experiment_timestamp"]

    df = df[columns]

    file_exists = os.path.exists(output_path)
    df.to_csv(output_path, mode="a", header=not file_exists, index=False)