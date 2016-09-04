#include "base.h"

/*
extern inline uint8_t read8(char ** buf);
extern inline void write8(char ** buf, uint8_t val);
extern inline uint16_t read16(char **buf);
extern inline void write16(char **buf, uint16_t val);
extern inline uint32_t read32(char **buf);
extern inline void write32(char **buf, uint32_t val);
*/

extern inline void ntoh(void * buf, size_t len);

// ln_buf

void ln_buf_decref(struct ln_buf * buf) {
    if(!buf->buf_refcnt--)
        free(buf);
}

void ln_buf_incref(struct ln_buf * buf) {
    buf->buf_refcnt++;
}

// ln_chain

ssize_t ln_chain_read(struct ln_chain ** chain, uchar ** pos, void * _out, size_t len) {
    if (*chain == NULL || *pos == NULL)
        return -1;

    ssize_t rc = 0;
    uchar * out = _out;
    while (len--) {
        if (out != NULL)
            *out++ = *(*pos)++;
        rc++;
        while (*pos >= (*chain)->chain_last) {
            *chain = (*chain)->chain_next;
            if (*chain == NULL) {
                *pos = NULL;
                return rc;
            } else {
                *pos = (*chain)->chain_pos;
            }
        }
    }
    return rc;
}

ssize_t ln_chain_write(struct ln_chain ** chain, uchar ** pos, const void * _inp, size_t len) {
    if (*chain == NULL || *pos == NULL)
        return -1;

    ssize_t rc = 0;
    const uchar * inp = _inp;
    while (len--) {
        *(*pos)++ = *inp++;
        rc++;
        while (*pos >= (*chain)->chain_last) {
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

int ln_chain_resize(struct ln_chain * chain, size_t len) {
    if (chain == NULL) return -1;

    while (1) {
        chain->chain_last = LN_BUF_LAST(chain->chain_buf);
        size_t clen = chain->chain_last - chain->chain_pos;
        if (clen >= len) {
            chain->chain_last = chain->chain_pos + len;
            break;
        }
        len -= clen;
        if (chain->chain_next == NULL) {
            // Need to allocate new chain+buf object
            chain->chain_next = calloc(1, sizeof *chain);
            if (chain->chain_next == NULL) MEMFAIL();
            chain = chain->chain_next;

            chain->chain_next->chain_buf = calloc(1, sizeof *chain->chain_buf);
            if (chain->chain_next->chain_buf == NULL) MEMFAIL();
            // Will set pos/last next
        }
        chain = chain->chain_next;
        chain->chain_pos = chain->chain_buf->buf_start;
    }

    // Zero out remaining chain links
    chain = chain->chain_next;
    while (chain != NULL) {
        chain->chain_last = chain->chain_pos;
        chain = chain->chain_next;
    }

    return 0;
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
    if (*in_chain == NULL || *pos == NULL)
        return -1;

    do {
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

        if (out_chain->chain_next == NULL)
            out_chain->chain_next = calloc(1, sizeof *out_chain->chain_next);
        if (out_chain->chain_next == NULL) return -1;
        out_chain = out_chain->chain_next;
    } while (len);

    // Zero out remaining chain links
    out_chain = out_chain->chain_next;
    while (out_chain != NULL) {
        out_chain->chain_last = out_chain->chain_pos;
        out_chain = out_chain->chain_next;
    }

    return 0;
}

void ln_chain_term(struct ln_chain * chain) {
    bool first = true;
    while (chain != NULL) {
        if (chain->chain_buf != NULL)
            ln_buf_decref(chain->chain_buf);
        struct ln_chain * next = chain->chain_next;
        chain->chain_next = NULL;
        if (!first) free(chain);
        first = false;
        chain = next;
    }
}

struct iovec * ln_chain_iov = NULL;
static size_t n_iovs = 0;

// Not re-entrant
int ln_chain_iovec(struct ln_chain * chain) {
    size_t idx = 0;
    while (chain != NULL) {
        if (idx >= n_iovs) {
            n_iovs = idx * 2;
            ln_chain_iov = realloc(ln_chain_iov, n_iovs * sizeof *ln_chain_iov);
            if (ln_chain_iov == NULL) MEMFAIL();
        }
        ln_chain_iov[idx].iov_base = chain->chain_pos;
        ln_chain_iov[idx].iov_len = chain->chain_last -  chain->chain_pos;
        chain = chain->chain_next;
        idx++;
    }
    return idx;
}
