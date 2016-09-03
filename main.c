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

/*
void coroutine ln_run_read_ipv4(int ipv4_in, int udp_out) {
    while (1) {
        struct ln_pkt_ipv4 * ipv4 = NULL;
        int rc = chrecv(ipv4_in, &ipv4, sizeof ipv4, -1);
        if (rc < 0) goto fail;

        switch (ipv4->ipv4_proto) {
        case LN_PROTO_IPV4_PROTO_UDP:;
            struct ln_pkt_udp * udp = ln_pkt_udp_dec(&ipv4->ipv4_pkt);
            if (udp == NULL) {
                WARN("Skipping packet");
            } else {
                ln_pkt_fdumpall(&udp->udp_pkt, stderr);
                fprintf(stderr, "\n");
                //rc = chsend(ipv4_out, &ipv4, sizeof ipv4, -1);
                //if (rc < 0) goto fail;
                ln_pkt_decref(&udp->udp_pkt);
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

        ln_pkt_decref(&ipv4->ipv4_pkt);
    }

fail:
    PERROR("fail");
    return;
}

void coroutine ln_run_read_eth(int eth_in, int ipv4_out) {
    while (1) {
        struct ln_pkt_eth * eth = NULL;
        int rc = chrecv(eth_in, &eth, sizeof eth, -1);
        if (rc < 0) goto fail;

        switch (eth->eth_type) {
        case LN_PROTO_ETH_TYPE_IPV4:;
            struct ln_pkt_ipv4 * ipv4 = ln_pkt_ipv4_dec(&eth->eth_pkt);
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

void coroutine ln_run_read_raw(int raw_in, int eth_out) {
    while (1) {
        struct ln_pkt_raw * raw;
        int rc = chrecv(raw_in, &raw, sizeof raw, -1);
        if (rc < 0) goto fail;

        struct ln_pkt_eth * eth = ln_pkt_eth_dec_raw(raw);
        if (eth == NULL) {
            WARN("Skipping packet");
            ln_pkt_raw_fdump(raw, stderr);
            fprintf(stderr, "\n");
        } else {
            rc = chsend(eth_out, &eth, sizeof eth, -1);
            if (rc < 0) goto fail;
        }
        ln_pkt_decref(&raw->raw_pkt);
    }

fail:
    PERROR("fail");
    return;
}
*/

void coroutine ln_run_read_sock(int sock, int raw_out) {
    int * sock_src = calloc(1, 1); // random id; memory leak is ok
    if (sock_src == NULL) goto fail;

    while (1) {
        int rc = fdin(sock, -1);
        if (rc < 0) goto fail;

        struct ln_pkt_raw * raw = ln_pkt_raw_frecv(sock);
        if (raw == NULL && errno == EAGAIN) continue; // Not ready; retry
        if (raw == NULL && errno == EMSGSIZE) continue; // Too big; skip
        if (raw == NULL) goto fail;

        struct ln_pkt * dec_pkt = ln_pkt_eth_dec(&raw->raw_pkt);
        if (dec_pkt == NULL) goto fail; // Unable to decode at least ethernet

        //rc = chsend(raw_out, &raw, sizeof raw, -1);
        //if (rc < 0) goto fail;
        ln_pkt_fdumpall(dec_pkt, stderr);
        fprintf(stderr, "\n");
        ln_pkt_decref(dec_pkt);
    }

fail:
    PERROR("fail");
    return;
}

void coroutine ln_run_write_sock(int sock, int raw_in) {
    while (1) {
        int rc = fdout(sock, -1);
        if (rc < 0) goto fail;

        struct ln_pkt_raw * raw = NULL;
        rc = chrecv(raw_in, &raw, sizeof raw, -1);
        if (rc < 0) goto fail;

        do {
            rc = ln_pkt_raw_fsend(raw);
        } while (rc < 0 && errno == EAGAIN);
        if (rc < 0) goto fail;

        ln_pkt_decref(&raw->raw_pkt);
    }

fail:
    PERROR("fail");
    return;
}

void coroutine ln_run_setup_sock(int ctl, int sock) {
    int raw_rx = channel(sizeof(struct ln_pkt_raw *), 16);
    if (raw_rx < 0) PFAIL("Unable to open raw_rx channel");
    int raw_tx = channel(sizeof(struct ln_pkt_raw *), 16);
    if (raw_tx < 0) PFAIL("Unable to open raw_tx channel");

    go(ln_run_read_sock(sock, raw_rx));
    go(ln_run_write_sock(sock, raw_tx));

    //ln_run_setup_eth(ctl, raw_rx, raw_tx);
}

int main(int argc, char ** argv) {
    int raw_sock = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    if (raw_sock < 0) PFAIL("Unable to open socket");

    int ctl = channel(1, 1);
    if (ctl < 0) PFAIL("Unable to create control channel");

    go(ln_run_setup_sock(ctl, raw_sock));

    // There's probably something more clever to do here
    while(1) msleep(-1);

    return 0;
}
