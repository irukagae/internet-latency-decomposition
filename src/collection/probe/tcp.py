from scapy.layers.inet import IP, TCP
from scapy.packet import Raw

def build_tcp_syn_packet(dst_ip, src_ip, dst_port=80, packet_size=64):
    """Build a TCP SYN packet within an approximate total packet size."""

    # Approximate header sizes (bytes)
    ip_header_size = 20
    tcp_header_size = 20

    payload_size = packet_size - (ip_header_size + tcp_header_size) # Compute payload size needed to reach desired packet size

    if payload_size < 0:
        payload_size = 0

    payload = Raw(load=b"A" * payload_size) if payload_size > 0 else None

    # Construct packet layers
    ip_layer = IP(dst=dst_ip, src=src_ip)
    tcp_layer = TCP(dport=dst_port, flags="S")

    if payload:
        return ip_layer / tcp_layer / payload

    return ip_layer / tcp_layer