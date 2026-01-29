from scapy.layers.inet import IP, ICMP
from scapy.packet import Raw

def build_icmp_echo_packet(dst_ip, packet_size=64):
    """Build an ICMP Echo request (ping-like) packet with an approximate total packet size."""

    # Approximate header size (bytes)
    ip_header_size = 20
    icmp_header_size = 8

    payload_size = packet_size - (ip_header_size + icmp_header_size) # Compute payload size needed to reach desired packet size
    if payload_size < 0:
        payload_size = 0

    payload = Raw(load=b"A" * payload_size) if payload_size > 0 else None

    # Construct packet layers
    ip_layer = IP(dst=dst_ip)
    icmp_layer = ICMP(type="echo-request")

    if payload:
        return ip_layer / icmp_layer / payload

    return ip_layer / icmp_layer