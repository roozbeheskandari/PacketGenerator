#!/usr/bin/env python3
"""
traffic_gen.py: Generates a deterministic PCAP workload for benchmarking OVS.
Generates 100,000 packets covering:
 - 80% Known Flows (Matching OpenFlow rules across multiple subtables)
 - 20% Unmatched Flows (Stress-testing negative lookups)
"""
import struct
import socket

PCAP_FILE = "benchmark_traffic.pcap"
NUM_PACKETS = 100000

def write_pcap_header(f):
    # Global pcap header (magic, v_maj, v_min, tz, sigfigs, snaplen, linktype: 1=Ethernet)
    header = struct.pack("!IHHiIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1)
    f.write(header)

def make_eth_ip_udp(src_ip, dst_ip, src_port, dst_port, payload=b"BENCHMARK_PKT"):
    eth = b"\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x01\x08\x00"
    ip_len = 20 + 8 + len(payload)
    ip_hdr = struct.pack(
        "!BBHHHBBH4s4s",
        0x45, 0, ip_len, 54321, 0, 64, 17, 0,
        socket.inet_aton(src_ip), socket.inet_aton(dst_ip)
    )
    udp_hdr = struct.pack("!HHHH", src_port, dst_port, 8 + len(payload), 0)
    return eth + ip_hdr + udp_hdr + payload

def main():
    print(f"[*] Generating {NUM_PACKETS} deterministic packets into {PCAP_FILE}...")
    with open(PCAP_FILE, "wb") as f:
        write_pcap_header(f)
        for i in range(NUM_PACKETS):
            if i % 10 < 8:
                # 80% matching flows (cycled across 5 different known subtable patterns)
                cat = i % 5
                if cat == 0:
                    pkt = make_eth_ip_udp("10.0.0.1", "10.0.0.2", 5001, 5001)
                elif cat == 1:
                    pkt = make_eth_ip_udp("10.0.0.1", "10.0.0.2", 1000 + (i % 20), 5002)
                elif cat == 2:
                    pkt = make_eth_ip_udp(f"10.0.1.{(i % 250) + 1}", "10.0.0.2", 2000, 6000)
                elif cat == 3:
                    pkt = make_eth_ip_udp("10.0.0.1", "10.0.0.2", 3000, 7000 + (i % 10))
                else:
                    pkt = make_eth_ip_udp("10.0.0.1", "10.0.0.2", 4000, 8000)
            else:
                # 20% unmatched flows (random noise exercising negative filter branches)
                pkt = make_eth_ip_udp(f"192.168.{(i % 250) + 1}.1", "172.16.0.2", 9000, 9999)

            ts_sec = i // 10000
            ts_usec = (i % 10000) * 100
            pkt_len = len(pkt)
            pkt_hdr = struct.pack("!IIII", ts_sec, ts_usec, pkt_len, pkt_len)
            f.write(pkt_hdr + pkt)
    print(f"[+] Workload generation complete: {PCAP_FILE}")

if __name__ == "__main__":
    main()
