#include "pkt.h"

// struct ln_pkt_raw

struct ln_pkt_raw * ln_pkt_raw_create(const void * src) {
    struct ln_pkt_raw * raw = calloc(1, sizeof *raw);
    if (raw == NULL) return NULL;

    raw->raw_src = src;
    return raw;
}

void ln_pkt_raw_decref(struct ln_pkt_raw * raw) {
    if(!raw->raw_refcnt--) {
        ln_chain_term(&raw->raw_chain);
        free(raw);
    }
}

void ln_pkt_raw_incref(struct ln_pkt_raw * raw) {
    raw->raw_refcnt++;
}

int ln_pkt_raw_fdump(struct ln_pkt_raw * raw, FILE * stream) {
    return fprintf(stream, "[raw len=%-4zu source=%#lx]",
                    ln_chain_len(&raw->raw_chain),
                    (uintptr_t) raw->raw_src);
}

// struct ln_pkt_eth

//TODO: There's at least 2 bytes missing, maybe CRC? 
struct ln_pkt_eth * ln_pkt_eth_create_raw(struct ln_pkt_raw * raw) {
    struct ln_chain * raw_chain = &raw->raw_chain;
    size_t raw_len = ln_chain_len(raw_chain);
    uchar * rpos = raw_chain->chain_pos;

    if (raw_len < LN_PROTO_ETH_HEADER_LEN + LN_PROTO_ETH_PAYLOAD_LEN_MIN)
        return (errno = EINVAL), NULL;
    if (raw_len > LN_PROTO_ETH_HEADER_LEN + LN_PROTO_ETH_PAYLOAD_LEN_MAX)
        return (errno = EINVAL), NULL;

    struct ln_pkt_eth * eth = calloc(1, sizeof *eth);
    if (eth == NULL) return NULL;

    eth->eth_raw = raw;
    ln_pkt_raw_incref(raw);
    
    size_t header_size = 18;
    ln_chain_read(&raw_chain, &rpos, &eth->eth_dst, sizeof eth->eth_dst);
    ln_chain_read(&raw_chain, &rpos, &eth->eth_src, sizeof eth->eth_src);
    ln_chain_read(&raw_chain, &rpos, &eth->eth_type, sizeof eth->eth_type);
    eth->eth_type = ntohs(eth->eth_type);
    if (eth->eth_type == 0x8100) {
        header_size += 4;
        ln_chain_read(&raw_chain, &rpos, &eth->eth_tag, sizeof eth->eth_tag);
        eth->eth_tag = ntohl(eth->eth_tag);
    }
    ln_chain_readref(&raw_chain, &rpos, &eth->eth_chain, raw_len - header_size);
    ln_chain_read(&raw_chain, &rpos, &eth->eth_crc, sizeof eth->eth_crc);
    eth->eth_crc = ntohl(eth->eth_crc);

    return eth;
}

void ln_pkt_eth_decref(struct ln_pkt_eth * eth) {
    if(!eth->eth_refcnt--) {
        if (eth->eth_raw != NULL)
            ln_pkt_raw_decref(eth->eth_raw);
        ln_chain_term(&eth->eth_chain);
        free(eth);
    }
}

void ln_pkt_eth_incref(struct ln_pkt_eth * eth) {
    eth->eth_refcnt++;
}

int ln_pkt_eth_fdump(struct ln_pkt_eth * eth, FILE * stream) {
    return fprintf(stream, "[eth"
                           " len=%-4zu"
                           " src=%02x:%02x:%02x:%02x:%02x:%02x"
                           " dst=%02x:%02x:%02x:%02x:%02x:%02x"
                           " type=%#04x]",
                    ln_chain_len(&eth->eth_chain),
                    eth->eth_src[0], eth->eth_src[1], eth->eth_src[2],
                    eth->eth_src[3], eth->eth_src[4], eth->eth_src[5],
                    eth->eth_dst[0], eth->eth_dst[1], eth->eth_dst[2],
                    eth->eth_dst[3], eth->eth_dst[4], eth->eth_dst[5],
                    eth->eth_type);
}

// struct ln_pkt_ipv4

struct ln_pkt_ipv4 * ln_pkt_ipv4_create_eth(struct ln_pkt_eth * eth) {
    struct ln_chain * eth_chain = &eth->eth_chain;
    size_t eth_len = ln_chain_len(eth_chain);
    uchar * rpos = eth_chain->chain_pos;

    if (eth_len < LN_PROTO_IPV4_HEADER_LEN_MIN)
        return (errno = EINVAL), NULL;
    if (eth_len > LN_PROTO_IPV4_HEADER_LEN_MIN + LN_PROTO_IPV4_PAYLOAD_LEN_MAX)
        return (errno = EINVAL), NULL;
    if ((*rpos & 0xF0) != 0x40)
        return (errno = EINVAL), NULL;

    struct ln_pkt_ipv4 * ipv4 = calloc(1, sizeof *ipv4);
    if (ipv4 == NULL) return NULL;

    ipv4->ipv4_eth = eth;
    ln_pkt_eth_incref(eth);

    uint8_t ihl;
    ln_chain_read_ntoh(&eth_chain, &rpos, &ihl);
    ihl &= 0xF;
    ln_chain_read_ntoh(&eth_chain, &rpos, &ipv4->ipv4_dscp_ecn);
    uint16_t len;
    ln_chain_read_ntoh(&eth_chain, &rpos, &len);
    if (len < 4 * ihl) {
        errno = EINVAL; goto fail; }
    len -= 4 * ihl;
    ln_chain_read_ntoh(&eth_chain, &rpos, &ipv4->ipv4_id);
    uint16_t flags_fragoff;
    ln_chain_read_ntoh(&eth_chain, &rpos, &flags_fragoff);
    ipv4->ipv4_flags = flags_fragoff >> 13;
    ipv4->ipv4_fragoff = flags_fragoff & 0x1FFF;
    ln_chain_read_ntoh(&eth_chain, &rpos, &ipv4->ipv4_ttl);
    ln_chain_read_ntoh(&eth_chain, &rpos, &ipv4->ipv4_proto);
    ln_chain_read_ntoh(&eth_chain, &rpos, &ipv4->ipv4_crc);
    ln_chain_read_ntoh(&eth_chain, &rpos, &ipv4->ipv4_src);
    ln_chain_read_ntoh(&eth_chain, &rpos, &ipv4->ipv4_dst);
    ln_chain_read(&eth_chain, &rpos, &ipv4->ipv4_opts, 4 * ihl - 20);
    ln_chain_readref(&eth_chain, &rpos, &ipv4->ipv4_chain, len);
    return ipv4;

fail:
    ln_pkt_eth_decref(eth);
    free(ipv4);
    return NULL;
}

void ln_pkt_ipv4_decref(struct ln_pkt_ipv4 * ipv4) {
    if(!ipv4->ipv4_refcnt--) {
        if (ipv4->ipv4_eth != NULL)
            ln_pkt_eth_decref(ipv4->ipv4_eth);
        ln_chain_term(&ipv4->ipv4_chain);
        free(ipv4);
    }
}

void ln_pkt_ipv4_incref(struct ln_pkt_ipv4 * ipv4) {
    ipv4->ipv4_refcnt++;
}

int ln_pkt_ipv4_fdump(struct ln_pkt_ipv4 * ipv4, FILE * stream) {
    uint8_t src_ip[4];
    uint8_t dst_ip[4];
    memcpy(src_ip, &ipv4->ipv4_src, 4);
    memcpy(dst_ip, &ipv4->ipv4_dst, 4);
    return fprintf(stream, "[ipv4"
                           " len=%-4zu"
                           " src=%hhu.%hhu.%hhu.%hhu"
                           " dst=%hhu.%hhu.%hhu.%hhu"
                           " proto=%#04x]",
                    ln_chain_len(&ipv4->ipv4_chain),
                    src_ip[3], src_ip[2], src_ip[1], src_ip[0],
                    dst_ip[3], dst_ip[2], dst_ip[1], dst_ip[0],
                    ipv4->ipv4_proto);
}

/*
void * ln_pkt_ipv4_write_start(struct ln_pkt_ipv4 * ipv4, size_t sz) {
    if (ipv4->ipv4_eth != NULL) {
        size_t header_size = LN_PROTO_IPV4_HEADER_LEN_MIN + 0;
        size_t packet_size = ipv4->ipv4_len + header_size;

        void * buf = ln_pkt_eth_write_start(ipv4->ipv4_eth, packet_size);
        if (buf == NULL) return NULL;

        // write header...
        uint8_t ihl = read8(&buf) & 0xF;
        ipv4->ipv4_dscp_ecn = read8(&buf);
        ipv4->ipv4_len = read16(&buf) - 20 - 4 * ihl;
        ipv4->ipv4_id = read16(&buf);
        uint16_t flags_fragoff = read16(&buf);
        ipv4->ipv4_flags = flags_fragoff >> 13;
        ipv4->ipv4_fragoff = flags_fragoff & 0x1FFF;
        ipv4->ipv4_ttl = read8(&buf);
        ipv4->ipv4_proto = read8(&buf);
        ipv4->ipv4_crc = read16(&buf);
        ipv4->ipv4_src = read32(&buf);
        ipv4->ipv4_dst = read32(&buf);
        ipv4->ipv4_opts = buf;
        ipv4->ipv4_data = buf + 4 * ihl;

        // write body
        memmove(buf, ipv4->ipv4_data, ipv4_len);

        int rc = ln_pkt_eth_write_finish(ipv4->ipv4_eth, packet_size);
        if (rc != 0) return NULL;
    } else {
        errno = EINVAL;
        return NULL;
    }
}

int ln_pkt_ipv4_write_finish(struct ln_pkt_ipv4 * ipv4, size_t sz) {

}
*/

// struct ln_pkt_udp
static struct ln_pkt_udp * ln_pkt_udp_create_chain(struct ln_chain * chain);

struct ln_pkt_udp * ln_pkt_udp_create_ipv4(struct ln_pkt_ipv4 * ipv4) {
    struct ln_chain * ipv4_chain = &ipv4->ipv4_chain;

    struct ln_pkt_udp * udp = ln_pkt_udp_create_chain(ipv4_chain);
    if (udp == NULL) return NULL;
    udp->udp_ipv4 = ipv4;
    ln_pkt_ipv4_incref(ipv4);

    return udp;
}
    
static struct ln_pkt_udp * ln_pkt_udp_create_chain(struct ln_chain * chain) {
    size_t chain_len = ln_chain_len(chain);
    uchar * rpos = chain->chain_pos;

    if (chain_len < LN_PROTO_UDP_HEADER_LEN)
        return (errno = EINVAL), NULL;

    struct ln_pkt_udp * udp = calloc(1, sizeof *udp);
    if (udp == NULL) return NULL;

    uint16_t udp_len = 0;
    ln_chain_read_ntoh(&chain, &rpos, &udp->udp_src);
    ln_chain_read_ntoh(&chain, &rpos, &udp->udp_dst);
    ln_chain_read_ntoh(&chain, &rpos, &udp_len);
    ln_chain_read_ntoh(&chain, &rpos, &udp->udp_crc);
    
    // Check packet size
    if (udp_len > chain_len)
        goto fail;
    if (udp_len < chain_len)
        INFO("Extra bytes: %zu", udp_len - chain_len);

    ln_chain_readref(&chain, &rpos, &udp->udp_chain, udp_len);
    return udp;

fail:
    free(udp);
    return NULL;
}

void ln_pkt_udp_decref(struct ln_pkt_udp * udp) {
    if(!udp->udp_refcnt--) {
        if (udp->udp_ipv4 != NULL)
            ln_pkt_ipv4_decref(udp->udp_ipv4);
        ln_chain_term(&udp->udp_chain);
        free(udp);
    }
}

void ln_pkt_udp_incref(struct ln_pkt_udp * udp) {
    udp->udp_refcnt++;
}

int ln_pkt_udp_fdump(struct ln_pkt_udp * udp, FILE * stream) {
    return fprintf(stream, "[udp"
                           " len=%-4zu"
                           " src=%hu"
                           " dst=%hu]",
                    ln_chain_len(&udp->udp_chain),
                    udp->udp_src,
                    udp->udp_dst);
}
