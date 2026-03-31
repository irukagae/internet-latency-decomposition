import time
from scapy.all import sniff

def capture_packets(interface: str, start_time: float, end_time: float):
    """Passively captures packet on a given interface within a time window"""

    if end_time <= start_time:
        raise ValueError("end_time must be greater than start_time.")

    captured_packets = []

    # wait until capture window opens
    now = time.time()
    if now < start_time:
        time.sleep(start_time - now)

    def packet_handler(pkt):
        captured_packets.append(pkt)

    duration = end_time - time.time()
    # start sniffing until end_time is reached
    sniff(iface=interface,prn=packet_handler, store=False,
          stop_filter=lambda _: time.time() >= end_time, timeout=duration)

    return captured_packets
