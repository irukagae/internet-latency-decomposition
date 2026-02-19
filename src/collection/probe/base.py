import time
from scapy.all import sr1


def measure_rtt(packet, timeout=1.0, iface=None):
    """Measures round-trip time (RTT) for a given packet"""

    send_timestamp = time.monotonic()  # record timestamp immediately before sending the packet

    response = sr1(packet, timeout=timeout, verbose=0, iface=iface)  # send one packet and wait for a single response

    if response is None:  # if no response is received
        return {"success": False,
                "rtt_ms": None,
                "send_timestamp": send_timestamp,
                "recv_timestamp": None}

    recv_timestamp = time.monotonic()  # record timestamp immediately after receiving the response
    rtt_ms = (recv_timestamp - send_timestamp) * 1000  # compute RTT in milliseconds

    return {"success": True,
            "rtt_ms": rtt_ms,
            "send_timestamp": send_timestamp,
            "recv_timestamp": recv_timestamp}
