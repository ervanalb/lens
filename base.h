#pragma once
#include "libdill/libdill.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>

#include "log.h"

//

// 

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

// Endianness conversions

/*
inline uint8_t read8(char ** buf) {
    return *(*buf)++;
}

inline void write8(char ** buf, uint8_t val) {
    *(*buf)++ = val;
}

inline uint16_t read16(char **buf) {
    uint16_t val = 0;
    memcpy(&val, *buf, sizeof val);
    *buf += sizeof val;
    return ntohs(val);
}

inline void write16(char **buf, uint16_t val) {
    uint16_t nval = htons(val);
    memcpy(*buf, &nval, sizeof nval);
    *buf += sizeof nval;
}

inline uint32_t read32(char **buf) {
    uint32_t val = 0;
    memcpy(&val, *buf, sizeof val);
    *buf += sizeof val;
    return ntohl(val);
}

inline void write32(char **buf, uint32_t val) {
    uint32_t nval = htons(val);
    memcpy(*buf, &nval, sizeof nval);
    *buf += sizeof nval;
}
*/

#define hton ntoh
inline void ntoh(void * buf, size_t len) {
    if (len <= 1) {
        return;
    } else if (len == 2) {
        uint16_t t;
        memcpy(&t, buf, sizeof t);
        t = ntohs(t);
        memcpy(buf, &t, sizeof t);
    } else if (len == 4) {
        uint32_t t;
        memcpy(&t, buf, sizeof t);
        t = ntohl(t);
        memcpy(buf, &t, sizeof t);
    } else {
        abort();
    }
}


// ln_buf functions

void ln_buf_decref(struct ln_buf * buf);
void ln_buf_incref(struct ln_buf * buf);

// ln_chain functions

#define ln_chain_read_ntoh(CHAIN, POS, TARGET) ({ \
    ssize_t _rv = ln_chain_read((CHAIN), (POS), (TARGET), sizeof *(TARGET)); \
    ntoh((TARGET), sizeof *(TARGET)); \
    _rv; })


#define ln_chain_write_ntoh(CHAIN, POS, TARGET) ({ \
    hton((TARGET), sizeof *(TARGET)); \
    ssize_t _rv = ln_chain_write((CHAIN), (POS), (TARGET), sizeof *(TARGET)); \
    ntoh((TARGET), sizeof *(TARGET)); \
    _rv; })

ssize_t ln_chain_read(struct ln_chain ** chain, uchar ** pos, void * _out, size_t len);
ssize_t ln_chain_write(struct ln_chain ** chain, uchar ** pos, const void * _inp, size_t len);
size_t ln_chain_len(const struct ln_chain * chain);
uchar * ln_chain_offset(const struct ln_chain * chain, size_t len);
int ln_chain_readref(struct ln_chain ** in_chain, uchar ** pos, struct ln_chain * out_chain, size_t len);
void ln_chain_term(struct ln_chain * chain);
