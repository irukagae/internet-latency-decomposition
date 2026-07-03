import time
import subprocess
import re
from scapy.all import sr1, srp1, Ether, conf, ARP

_gateway_mac_cache = None

def get_gateway_mac():
    """Resolves gateway MAC address via ARP"""

    global _gateway_mac_cache
    if _gateway_mac_cache is not None:
        return _gateway_mac_cache

    route_info = conf.route.route("0.0.0.0")
    gateway_ip = route_info[2]

    arp_response = sr1(ARP(pdst=gateway_ip), timeout=3, verbose=0)
    if arp_response:
        _gateway_mac_cache = arp_response.hwsrc
        print(f"Gateway MAC resolved: {_gateway_mac_cache}")
        return _gateway_mac_cache

    return None

def measure_rtt(packet, timeout=1.0, iface=None):
    """Measures round-trip time (RTT) for a given packet"""

    gateway_mac = get_gateway_mac()
    if gateway_mac is None:
        return {"success": False,
                "rtt_ms": None,
                "send_timestamp": time.monotonic(),
                "recv_timestamp": None}

    #wrap packet in Ethernet frame with correct gateway MAC (L2 sending)
    l2_packet = Ether(dst=gateway_mac) / packet

    send_timestamp = time.monotonic()  # record timestamp immediately before sending the packet

    response = srp1(l2_packet, timeout=timeout, verbose=0, iface=iface)  # send one packet and wait for a single response

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
