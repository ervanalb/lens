#pragma once
#include "base.h"

#define LN_PKT_TYPE_STRUCT(TYPE) struct ln_pkt_##TYPE
#define LN_PKT_TYPE_NAME(TYPE) ln_pkt_type_##TYPE

#define LN_PKT_TYPES \
    X(raw) \
    X(eth) \
    X(ipv4) \
    X(udp) \

enum ln_pkt_type {
    ln_pkt_type_none,
#define X(TYPE) LN_PKT_TYPE_NAME(TYPE),
LN_PKT_TYPES
#undef X
    ln_pkt_type_max
};

/* Functions to safely convert from generic ln_pkt. Example:
 *
 * inline struct ln_pkt_eth * LN_PKT_ETH(struct ln_pkt * pkt) {
 *     if (pkt->pkt_type == LN_PKT_TYPE_ETH) {
 *         return (struct ln_pkt_eth *) pkt;
 *     return NULL;
 * }
 *
 */
/* Removed in favor of LN_PKT_CAST(...)
#define X(TYPE) \
    inline LN_PKT_TYPE_STRUCT(TYPE) * LN_PKT_TYPE_NAME(TYPE)##_cast (struct ln_pkt * pkt) { \
        if (pkt->pkt_type == LN_PKT_TYPE_NAME(TYPE)) \
            return (LN_PKT_TYPE_STRUCT(TYPE) *) pkt; \
        return NULL; \
    }
LN_PKT_TYPES
#undef X
*/

// Safely convert from generic to ln_pkt.
// Example usage: `struct ln_pkt_raw * my_raw = LN_PKT_CAST(my_pkt, raw);`
#define LN_PKT_CAST(pkt, TYPE) ( \
    ((pkt) != NULL && (pkt)->pkt_type == LN_PKT_TYPE_NAME(TYPE)) ? (LN_PKT_TYPE_STRUCT(TYPE) *) (pkt) : NULL)

struct ln_pkt {
    // Underlying protocol/header
    struct ln_pkt * pkt_parent;
    // Payload/data
    struct ln_chain pkt_chain;
    // Reference count
    refcnt_t pkt_refcnt;
    // Type, see LN_PKT_TYPES
    enum ln_pkt_type pkt_type;
};

void ln_pkt_decref(struct ln_pkt * pkt);
void ln_pkt_incref(struct ln_pkt * pkt);
int ln_pkt_fdump(struct ln_pkt * pkt, FILE * stream);
int ln_pkt_fdumpall(struct ln_pkt * pkt, FILE * stream);
struct ln_pkt * ln_pkt_enc(struct ln_pkt * pkt, size_t payload_len);

//

struct ln_pkt_raw {
    struct ln_pkt raw_pkt;
    int raw_fd;
};

struct ln_pkt_raw * ln_pkt_raw_frecv(int fd);
int ln_pkt_raw_fsend(struct ln_pkt_raw * raw);

//

#define LN_PROTO_ETH_PAYLOAD_LEN_MIN 46
#define LN_PROTO_ETH_PAYLOAD_LEN_MAX 1500
#define LN_PROTO_ETH_HEADER_LEN (6 + 6 + 2 + 4) // Does not include tag; includes CRC
#define LN_PROTO_ETH_TYPE_IPV4 0x0800
#define LN_PROTO_ETH_TYPE_ARP  0x0806
#define LN_PROTO_ETH_TYPE_IPV6 0x86DD

struct ln_pkt_eth {
    struct ln_pkt eth_pkt;

    uint8_t eth_src[6];
    uint8_t eth_dst[6];
    uint32_t eth_tag;
    uint16_t eth_type;
    uint32_t eth_crc;
};

struct ln_pkt * ln_pkt_eth_dec(struct ln_pkt * parent_pkt);

//

#define LN_PROTO_IPV4_PAYLOAD_LEN_MAX 65535
#define LN_PROTO_IPV4_HEADER_LEN_MIN 20 // Does not include options
#define LN_PROTO_IPV4_HEADER_LEN_MAX (16 * 4)
#define LN_PROTO_IPV4_PROTO_ICMP 0x01
#define LN_PROTO_IPV4_PROTO_TCP  0x06
#define LN_PROTO_IPV4_PROTO_UDP  0x11

struct ln_pkt_ipv4 {
    struct ln_pkt ipv4_pkt;

    uint8_t ipv4_ihl;
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
};

struct ln_pkt * ln_pkt_ipv4_dec(struct ln_pkt * parent_pkt);

//

struct ln_pkt_tcp {
    struct ln_pkt tcp_pkt;

    uint16_t tcp_src;
    uint16_t tcp_dst;
    uint32_t tcp_seq;
    uint32_t tcp_ack;
    uint16_t tcp_flags;
    uint16_t tcp_window;
    uint16_t tcp_crc;
    uint16_t tcp_urg;
    struct ln_chain tcp_opts_chain;
};

struct ln_pkt * ln_pkt_tcp_dec(struct ln_pkt * parent_pkt);

//
//
#define LN_PROTO_UDP_PAYLOAD_LEN_MAX ((size_t) 65535)
#define LN_PROTO_UDP_HEADER_LEN ((size_t) 8)

struct ln_pkt_udp {
    struct ln_pkt udp_pkt;

    uint16_t udp_src;
    uint16_t udp_dst;
    uint16_t udp_crc;
};

struct ln_pkt * ln_pkt_udp_dec(struct ln_pkt * parent_pkt);
