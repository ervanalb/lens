#include "libdill/libdill.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>

typedef uint32_t refcnt_t;
typedef unsigned char uchar;

#define LN_BUF_SIZE (4096 - sizeof(refcnt_t))

struct ln_buf {
    refcnt_t buf_refcnt;
    uchar buf_start[LN_BUF_SIZE];
};

struct ln_chain {
    struct ln_buf * chain_buf;
    uchar * chain_pos;
    uchar * chain_last;
    struct ln_chain * chain_next;
};

struct ln_pkt_raw {
    const void * raw_src;
    refcnt_t raw_refcnt;

    struct ln_chain raw_chain;
};

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

struct ln_pkt_ipv4 {
    struct ln_pkt_eth * ipv4_eth;
    refcnt_t ipv4_refcnt;

    uchar ipv4_opts[65];
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

struct ln_pkt_tcp {
    union {
        struct ln_pkt_ipv4 * tcp_ipv4;
    };
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

union ln_layer {
    struct ln_pkt_raw raw;   
    struct ln_pkt_eth eth;
    struct ln_pkt_ipv4 ipv4;
};

//

uint8_t read8(char ** buf) {
    return *(*buf)++;
}

void write8(char ** buf, uint8_t val) {
    *(*buf)++ = val;
}

uint16_t read16(char **buf) {
    uint16_t val = 0;
    memcpy(&val, *buf, sizeof val);
    *buf += sizeof val;
    return ntohs(val);
}

void write16(char **buf, uint16_t val) {
    uint16_t nval = htons(val);
    memcpy(*buf, &nval, sizeof nval);
    *buf += sizeof nval;
}

uint32_t read32(char **buf) {
    uint32_t val = 0;
    memcpy(&val, *buf, sizeof val);
    *buf += sizeof val;
    return ntohl(val);
}

void write32(char **buf, uint32_t val) {
    uint32_t nval = htons(val);
    memcpy(*buf, &nval, sizeof nval);
    *buf += sizeof nval;
}

#define hton ntoh
void ntoh(void * buf, size_t len) {
    if (len <= 1) return;
    else if (len == 2) *(uint16_t *) buf = ntohs(*(uint16_t *) buf);
    else if (len == 4) *(uint32_t *) buf = ntohl(*(uint32_t *) buf);
    else abort();
}

// struct ln_buf & struct ln_chain

void ln_buf_decref(struct ln_buf * buf) {
    if(!buf->buf_refcnt--)
        free(buf);
}

void ln_buf_incref(struct ln_buf * buf) {
    buf->buf_refcnt++;
}

void ln_chain_term(struct ln_chain * chain) {
    while (chain != NULL) {
        if (chain->chain_buf != NULL)
            ln_buf_decref(chain->chain_buf);
        struct ln_chain * next = chain->chain_next;
        chain->chain_next = NULL;
        chain = next;
    }
}

//

#define ln_chain_read_ntoh(CHAIN, POS, TARGET) ({ \
    ssize_t _rv = ln_chain_read((CHAIN), (POS), (TARGET), sizeof *(TARGET)); \
    ntoh((TARGET), sizeof *(TARGET)); \
    _rv; })

ssize_t ln_chain_read(struct ln_chain ** chain, uchar ** pos, void * _out, size_t len) {
    if (*chain == NULL || *pos == NULL)
        return -1;

    ssize_t rc = 0;
    uchar * out = _out;
    while (len--) {
        if (out != NULL)
            *out++ = *(*pos)++;
        rc++;
        while (*pos < (*chain)->chain_last) {
            *chain = (*chain)->chain_next;
            if (*chain == NULL) {
                *pos = NULL;
                break;
            } else {
                *pos = (*chain)->chain_pos;
            }
        }
    }
    return rc;
}

#define ln_chain_write_ntoh(CHAIN, POS, TARGET) ({ \
    hton((TARGET), sizeof *(TARGET)); \
    ssize_t _rv = ln_chain_write((CHAIN), (POS), (TARGET), sizeof *(TARGET)); \
    ntoh((TARGET), sizeof *(TARGET)); \
    _rv; })

ssize_t ln_chain_write(struct ln_chain ** chain, uchar ** pos, const void * _inp, size_t len) {
    if (*chain == NULL || *pos == NULL)
        return -1;

    ssize_t rc = 0;
    const uchar * inp = _inp;
    while (len--) {
        *(*pos)++ = *inp++;
        rc++;
        while (*pos < (*chain)->chain_last) {
            *chain = (*chain)->chain_next;
            if (*chain == NULL) {
                *pos = NULL;
                break;
            } else {
                *pos = (*chain)->chain_pos;
            }
        }
    }
    return rc;
}

size_t ln_chain_len(const struct ln_chain * chain) {
    size_t len = 0;
    while (chain != NULL) {
        len += chain->chain_last - chain->chain_pos;
        chain = chain->chain_next;
    }
    return len;
}

uchar * ln_chain_offset(const struct ln_chain * chain, size_t len) {
    while (chain != NULL) {
        size_t blen = chain->chain_last - chain->chain_pos;
        if (len < blen)
            return chain->chain_pos + len;
        len -= blen;
        chain = chain->chain_next;
    }
    return NULL;
}

int ln_chain_readref(struct ln_chain ** in_chain, uchar ** pos, struct ln_chain * out_chain, size_t len) {
    if (out_chain->chain_next != NULL)
        return (errno = EINVAL), -1;

    while (len) {
        out_chain->chain_buf = (*in_chain)->chain_buf;
        ln_buf_incref((*in_chain)->chain_buf);
        out_chain->chain_pos = *pos;
        out_chain->chain_last = (*in_chain)->chain_last;
        size_t blen = (*in_chain)->chain_last - (*in_chain)->chain_pos;
        if (len < blen) {
            out_chain->chain_last = out_chain->chain_pos + len;
            *pos += len;
            break;
        }
        out_chain->chain_last = (*in_chain)->chain_last;
        len -= blen;
        if (len == 0) break;
        if ((*in_chain)->chain_next == NULL) return (errno = EINVAL), -1;
        *in_chain = (*in_chain)->chain_next;
        *pos = (*in_chain)->chain_pos;
        out_chain->chain_next = calloc(1, sizeof *out_chain->chain_next);
        out_chain = out_chain->chain_next;
        if (out_chain == NULL) return -1;
    }
    return 0;
}

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

// struct ln_pkt_eth

#define LN_PROTO_ETH_PAYLOAD_LEN_MIN 46
#define LN_PROTO_ETH_PAYLOAD_LEN_MAX 1500
#define LN_PROTO_ETH_HEADER_LEN (6 + 6 + 2 + 4) // Does not include tag; includes CRC

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
    eth->eth_refcnt = 1;
    
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
    if(!--eth->eth_refcnt) {
        if (eth->eth_raw != NULL)
            ln_pkt_raw_decref(eth->eth_raw);
        ln_chain_term(&eth->eth_chain);
        free(eth);
    }
}

void ln_pkt_eth_incref(struct ln_pkt_eth * eth) {
    eth->eth_refcnt++;
}

// struct ln_pkt_ipv4

#define LN_PROTO_IPV4_PAYLOAD_LEN_MAX 65535
#define LN_PROTO_IPV4_HEADER_LEN_MIN 20 // Does not include options

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
    ipv4->ipv4_refcnt = 1;

    uint8_t ihl;
    ln_chain_read_ntoh(&eth_chain, &rpos, &ihl);
    ihl &= 0xF;
    ln_chain_read_ntoh(&eth_chain, &rpos, &ipv4->ipv4_dscp_ecn);
    uint16_t len;
    ln_chain_read_ntoh(&eth_chain, &rpos, &len);
    if (len < 20 + 4 * ihl) {
        errno = EINVAL; goto fail; }
    len -= 20 + 4 * ihl;
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
    ln_chain_read(&eth_chain, &rpos, &ipv4->ipv4_opts, 4 * ihl);
    ln_chain_readref(&eth_chain, &rpos, &ipv4->ipv4_chain, len);
    return ipv4;

fail:
    ln_pkt_eth_decref(eth);
    free(ipv4);
    return NULL;
}

void ln_pkt_ipv4_decref(struct ln_pkt_ipv4 * ipv4) {
    if(!--ipv4->ipv4_refcnt) {
        if (ipv4->ipv4_eth != NULL)
            ln_pkt_eth_decref(ipv4->ipv4_eth);
        ln_chain_term(&ipv4->ipv4_chain);
        free(ipv4);
    }
}

void ln_pkt_ipv4_incref(struct ln_pkt_ipv4 * ipv4) {
    ipv4->ipv4_refcnt++;
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

//

void coroutine ln_run_eth_ipv4(int eth_in, int ipv4_out) {
    struct ln_pkt_eth eth_buf;
    while (1) {
        int rc = chrecv(eth_in, &eth_buf, sizeof buf, -1);
        // check rc
        switch (buf.eth_type) {
        case LN_ETH_TYPE_IPV4:
            rc = chsend(ipv4_out, &ipv4_buf, sizeof ipv4_buf, -1);
            // check rc
            break;
        }
    }
}
*/

int main(int argc, char ** argv) {
    return 0;
}
