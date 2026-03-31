import time
from collection.probe.base import measure_rtt
from collection.probe.tcp import build_tcp_syn_packet
from collection.probe.udp import build_udp_packet
from collection.probe.icmp import build_icmp_echo_packet

# protocol -> packet builder mapping
probe_builder = {"tcp": build_tcp_syn_packet,
                  "icmp": build_icmp_echo_packet,
                  "udp": build_udp_packet}

def run_expt(protocol: str, dst_ip: str, src_ip: str,
             packet_size: int, num_probes: int, probe_interval: float,
             timeout: float, iface, record: bool = True):
    """Execute a single sealed active-probing experiment and return probe results."""

    protocol = protocol.lower()
    if protocol not in probe_builder:
        raise ValueError(f"Unsupported protocol: {protocol}")

    packet_builder = probe_builder[protocol]
    result = []

    for probe_index in range(num_probes):
        # build packet (protocol specific)
        packet = packet_builder(dst_ip, src_ip=src_ip, packet_size=packet_size)

        # measure rtt
        rtt_result = measure_rtt(packet, timeout=timeout, iface=iface)

        # attach experiment metadata
        probe_result = {"protocol": protocol,
                        "dst_ip": dst_ip,
                        "packet_size": packet_size,
                        "probe_index": probe_index,
                        "success": rtt_result["success"],
                        "rtt_ms": rtt_result["rtt_ms"],
                        "send_timestamp": rtt_result["send_timestamp"],
                        "recv_timestamp": rtt_result["recv_timestamp"]}

        if record:
            result.append(probe_result)

        # sleep between the probes (not after the last one)
        if probe_index < num_probes - 1:
            time.sleep(probe_interval)

    return result
