#include <sys/types.h>
#include <sys/socket.h>
#include <linux/if_packet.h>
#include <net/ethernet.h>

#include "pkt.h"
#include "base.h"
#include "libdill/libdill.h"

/* TODO
 * ====
 *
 * - Handle coroutine crashes
 *   - Maybe they should just crash the whole program?
 *   - Is there a way to detect this & restart the coro?
 * - Bidirectional data flow
 *   - Channel pairs? (They could also be typed?)
 * - Channel type information / safety
 *   - Enforced once; but it's OK to do it at the start of the coros
 */

enum loglevel loglevel = LOGLEVEL_INFO;

void coroutine ln_run_ipv4_udp(int ipv4_in, int udp_out) {
    while (1) {
        struct ln_pkt_ipv4 * ipv4 = NULL;
        int rc = chrecv(ipv4_in, &ipv4, sizeof ipv4, -1);
        if (rc < 0) goto fail;

        switch (ipv4->ipv4_proto) {
        case LN_PROTO_IPV4_PROTO_UDP:;
            struct ln_pkt_udp * udp = ln_pkt_udp_create_ipv4(ipv4);
            if (udp == NULL) {
                WARN("Skipping packet");
            } else {
                ln_pkt_raw_fdump(udp->udp_ipv4->ipv4_eth->eth_raw, stderr);
                fprintf(stderr, " --> ");
                ln_pkt_eth_fdump(udp->udp_ipv4->ipv4_eth, stderr);
                fprintf(stderr, " --> ");
                ln_pkt_ipv4_fdump(udp->udp_ipv4, stderr);
                fprintf(stderr, " --> ");
                ln_pkt_udp_fdump(udp, stderr);
                fprintf(stderr, "\n");
                //rc = chsend(ipv4_out, &ipv4, sizeof ipv4, -1);
                //if (rc < 0) goto fail;
                ln_pkt_udp_decref(udp);
            }
            break;
        case LN_PROTO_IPV4_PROTO_ICMP:
            INFO("ICMP");
            break;
        case LN_PROTO_IPV4_PROTO_TCP:
            INFO("TCP");
            break;
        default:
            INFO("Unknown proto %#02x", ipv4->ipv4_proto);
            break;
        }

        ln_pkt_ipv4_decref(ipv4);
    }

fail:
    PERROR("fail");
    return;
}

void coroutine ln_run_eth_ipv4(int eth_in, int ipv4_out) {
    while (1) {
        struct ln_pkt_eth * eth = NULL;
        int rc = chrecv(eth_in, &eth, sizeof eth, -1);
        if (rc < 0) goto fail;

        switch (eth->eth_type) {
        case LN_PROTO_ETH_TYPE_IPV4:;
            struct ln_pkt_ipv4 * ipv4 = ln_pkt_ipv4_create_eth(eth);
            if (ipv4 == NULL) {
                WARN("Skipping packet");
            } else {
                rc = chsend(ipv4_out, &ipv4, sizeof ipv4, -1);
                if (rc < 0) goto fail;
            }
            break;
        default:
            INFO("Unknown ethertype %#04x", eth->eth_type);
            break;
        }

        ln_pkt_eth_decref(eth);
    }

fail:
    PERROR("fail");
    return;
}

void coroutine ln_run_raw_eth(int raw_in, int eth_out) {
    while (1) {
        struct ln_pkt_raw * raw;
        int rc = chrecv(raw_in, &raw, sizeof raw, -1);
        if (rc < 0) goto fail;

        struct ln_pkt_eth * eth = ln_pkt_eth_create_raw(raw);
        if (eth == NULL) {
            WARN("Skipping packet");
            ln_pkt_raw_fdump(raw, stderr);
            fprintf(stderr, "\n");
        } else {
            rc = chsend(eth_out, &eth, sizeof eth, -1);
            if (rc < 0) goto fail;
        }
        ln_pkt_raw_decref(raw);
    }

fail:
    PERROR("fail");
    return;
}

void coroutine ln_run_sock_raw(int sock, int raw_out) {
    int * sock_src = calloc(1, 1); // random id; memory leak is ok
    if (sock_src == NULL) goto fail;

    while (1) {
        struct ln_pkt_raw * raw = calloc(1, sizeof *raw);
        if (raw == NULL) goto fail;
        struct ln_buf * buf = calloc(1, sizeof *buf);
        if (buf == NULL) goto fail;

discard_read:;
        int rc = fdin(sock, -1);
        if (rc < 0) goto fail;
        rc = recv(sock, buf->buf_start, sizeof buf->buf_start, MSG_DONTWAIT | MSG_TRUNC);
        if (rc < 0 && errno == EAGAIN) goto discard_read;
        if (rc < 0) goto fail;
        if ((size_t) rc >= sizeof buf->buf_start) goto discard_read; // Jumbo frame or something weird?

        raw->raw_src = sock_src;
        raw->raw_chain.chain_buf = buf;
        raw->raw_chain.chain_pos = buf->buf_start;
        raw->raw_chain.chain_last = buf->buf_start + rc;
        raw->raw_chain.chain_next = NULL;

        rc = chsend(raw_out, &raw, sizeof raw, -1);
        if (rc < 0) goto fail;
    }

fail:
    PERROR("fail");
    return;
}

int main(int argc, char ** argv) {
    int raw_sock = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    if (raw_sock < 0) PFAIL("Unable to open socket");

    int raw_in = channel(sizeof(struct ln_pkt_raw *), 16);
    if (raw_in < 0) PFAIL("Unable to open raw_in channel");

    int eth_in = channel(sizeof(struct ln_pkt_eth *), 16);
    if (eth_in < 0) PFAIL("Unable to open eth_in channel");

    int ipv4_in = channel(sizeof(struct ln_pkt_ipv4 *), 16);
    if (ipv4_in < 0) PFAIL("Unable to open ipv4_in channel");

    int udp_in = channel(sizeof(struct ln_pkt_udp *), 16);
    if (udp_in < 0) PFAIL("Unable to open udp_in channel");

    go(ln_run_sock_raw(raw_sock, raw_in));
    go(ln_run_raw_eth(raw_in, eth_in));
    go(ln_run_eth_ipv4(eth_in, ipv4_in));
    go(ln_run_ipv4_udp(ipv4_in, udp_in));

    // There's probably something more clever to do here
    while(1) msleep(-1);

    return 0;
}
