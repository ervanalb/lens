#pragma once
#include "base.h"

struct ln_pkt_raw {
    refcnt_t raw_refcnt;
    const void * raw_src;

    struct ln_chain raw_chain;
};

struct ln_pkt_raw * ln_pkt_raw_create(const void * src);
void ln_pkt_raw_decref(struct ln_pkt_raw * raw);
void ln_pkt_raw_incref(struct ln_pkt_raw * raw);

//

#define LN_PROTO_ETH_PAYLOAD_LEN_MIN 46
#define LN_PROTO_ETH_PAYLOAD_LEN_MAX 1500
#define LN_PROTO_ETH_HEADER_LEN (6 + 6 + 2 + 4) // Does not include tag; includes CRC
#define LN_PROTO_ETH_TYPE_IPV4 0x0800
#define LN_PROTO_ETH_TYPE_ARP  0x0806
#define LN_PROTO_ETH_TYPE_IPV6 0x86DD

struct ln_pkt_eth {
    struct ln_pkt_raw * eth_raw;
    refcnt_t eth_refcnt;

    uint8_t eth_src[6];
    uint8_t eth_dst[6];
    uint32_t eth_tag;
    uint16_t eth_type;
    uint32_t eth_crc;

    struct ln_chain eth_chain;
};

struct ln_pkt_eth * ln_pkt_eth_create_raw(struct ln_pkt_raw * raw);
void ln_pkt_eth_decref(struct ln_pkt_eth * eth);
void ln_pkt_eth_incref(struct ln_pkt_eth * eth);
int ln_pkt_eth_fdump(struct ln_pkt_eth * eth, FILE * stream);

//

#define LN_PROTO_IPV4_PAYLOAD_LEN_MAX 65535
#define LN_PROTO_IPV4_HEADER_LEN_MIN 20 // Does not include options
#define LN_PROTO_IPV4_PROTO_ICMP 0x01
#define LN_PROTO_IPV4_PROTO_TCP  0x06
#define LN_PROTO_IPV4_PROTO_UDP  0x11

struct ln_pkt_ipv4 {
    struct ln_pkt_eth * ipv4_eth;
    refcnt_t ipv4_refcnt;

    uchar ipv4_opts[65]; // fixme...
    uint8_t ipv4_dscp_ecn;
    uint16_t ipv4_id;
    uint8_t ipv4_flags;
    uint16_t ipv4_fragoff;
    uint8_t ipv4_ttl;
    uint8_t ipv4_proto;
    uint16_t ipv4_crc;
    uint32_t ipv4_src;
    uint32_t ipv4_dst;

    struct ln_chain ipv4_chain;
};

struct ln_pkt_ipv4 * ln_pkt_ipv4_create_eth(struct ln_pkt_eth * eth);
void ln_pkt_ipv4_decref(struct ln_pkt_ipv4 * ipv4);
void ln_pkt_ipv4_incref(struct ln_pkt_ipv4 * ipv4);
int ln_pkt_ipv4_fdump(struct ln_pkt_ipv4 * ipv4, FILE * stream);

//

struct ln_pkt_tcp {
    struct ln_pkt_ipv4 * tcp_ipv4;
    refcnt_t tcp_refcnt;

    uint16_t tcp_src;
    uint16_t tcp_dst;
    uint32_t tcp_seq;
    uint32_t tcp_ack;
    uint16_t tcp_flags;
    uint16_t tcp_window;
    uint16_t tcp_crc;
    uint16_t tcp_urg;
    struct ln_chain tcp_opts_chain;

    struct ln_chain tcp_chain;
};
