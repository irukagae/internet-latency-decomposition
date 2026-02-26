from scapy.layers.inet import UDP, IP
from scapy.packet import Raw

def build_udp_packet(dst_ip, src_ip, dst_port=33434, packet_size=64):
    """Build a UDP probe packet with an approximate total packet size"""

    # Approximate header size (bytes)
    ip_header = 20
    udp_header = 8

    payload_size = packet_size - (ip_header + udp_header)  # Compute payload size to reach the desired packet size
    if payload_size < 0:
        payload_size = 0

    payload = Raw(load=b"A" * payload_size) if payload_size > 0 else None

    # Construct packet layers
    ip_layer = IP(dst=dst_ip, src=src_ip)
    udp_layer = UDP(dport=dst_port)

    if payload:
        return ip_layer / udp_layer / payload

    return ip_layer / udp_layer