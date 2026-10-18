#!/usr/bin/env python3
"""
Advanced Network Packet Generator for OVS Benchmarking (Q1 Evaluation)
Generates standard raw PCAP files with valid, unknown (miss), and drop/attack packets.
"""

import struct
import random
import time
import sys

def write_pcap_header(f):
    # PCAP Global Header: magic, v_major, v_minor, thiszone, sigfigs, snaplen, network
    pcap_hdr = struct.pack('!IHHiIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1)
    f.write(pcap_hdr)

def create_raw_packet(src_ip, dst_ip, src_port, dst_port, is_drop=False):
    # Ethernet Header (14 bytes)
    eth_dst = b'\x00\x0c\x29\x4f\x8e\x35'
    eth_src = b'\x00\x0c\x29\x4f\x8e\x2b'
    eth_type = b'\x08\x00' # IPv4
    eth_header = eth_dst + eth_src + eth_type

    # IPv4 Header (20 bytes)
    ip_ver_ihl = 0x45
    ip_tos = 0
    ip_tot_len = 54 # 20 (IP) + 20 (TCP) + 14 (Eth)
    ip_id = random.randint(1, 65535)
    ip_frag_off = 0
    ip_ttl = 64 if not is_drop else 1 # TTL=1 can cause drop
    ip_proto = 6 # TCP
    ip_check = 0 # Kernel/OVS handles or validates

    ip_src_b = bytes(map(int, src_ip.split('.')))
    ip_dst_b = bytes(map(int, dst_ip.split('.')))

    ip_header = struct.pack('!BBHHHBBH4s4s',
                            ip_ver_ihl, ip_tos, ip_tot_len, ip_id,
                            ip_frag_off, ip_ttl, ip_proto, ip_check,
                            ip_src_b, ip_dst_b)

    # TCP Header (20 bytes)
    tcp_seq = random.randint(1000, 500000)
    tcp_ack = 0
    tcp_offset_res = (5 << 4)
    tcp_flags = 0x02 if not is_drop else 0x00 # SYN or Corrupt Flags
    tcp_window = 8192
    tcp_check = 0
    tcp_urg_ptr = 0

    tcp_header = struct.pack('!HHIIBBHHH',
                             src_port, dst_port, tcp_seq, tcp_ack,
                             tcp_offset_res, tcp_flags, tcp_window,
                             tcp_check, tcp_urg_ptr)

    return eth_header + ip_header + tcp_header

def generate_pcap(filename="ovs_eval_trace.pcap", count=1000000):
    print(f"[*] Starting raw PCAP generation: {count} packets -> {filename}")
    start_time = time.time()
    
    with open(filename, "wb") as f:
        write_pcap_header(f)
        
        for i in range(count):
            r = random.random()
            if r < 0.70:
                # 70% Valid / Known Flows (Cache & Cuckoo Hits)
                src_ip = f"10.0.{random.randint(1, 4)}.{random.randint(1, 20)}"
                dst_ip = f"192.168.1.{random.randint(1, 20)}"
                src_p, dst_p = random.randint(1024, 2000), 80
                is_drop = False
            elif r < 0.90:
                # 20% Unknown Flows (Cuckoo Misses -> Subtable / dpcls Lookup)
                src_ip = f"172.16.{random.randint(50, 150)}.{random.randint(1, 254)}"
                dst_ip = f"10.200.{random.randint(1, 100)}.{random.randint(1, 254)}"
                src_p, dst_p = random.randint(10000, 60000), random.randint(1000, 5000)
                is_drop = False
            else:
                # 10% Dropped / Attack / Collision Traffic
                src_ip = "0.0.0.0"
                dst_ip = "255.255.255.255"
                src_p, dst_p = 0, 0
                is_drop = True

            pkt_bytes = create_raw_packet(src_ip, dst_ip, src_p, dst_p, is_drop)
            
            # PCAP Record Header (16 bytes): ts_sec, ts_usec, incl_len, orig_len
            pkt_len = len(pkt_bytes)
            rec_hdr = struct.pack('!IIII', int(time.time()), i, pkt_len, pkt_len)
            f.write(rec_hdr)
            f.write(pkt_bytes)

    duration = time.time() - start_time
    print(f"[+] Done! Successfully generated {count} packets in {duration:.2f} seconds.")

if __name__ == "__main__":
    pkt_count = int(sys.argv[1]) if len(sys.argv) > 1 else 1000000
    generate_pcap("ovs_eval_trace.pcap", pkt_count)
