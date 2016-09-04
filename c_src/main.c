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

void coroutine ln_run_read_sock(int sock, int pkt_out) {
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

        //rc = chsend(pkt_out, &raw, sizeof raw, -1);
        //if (rc < 0) goto fail;
        ln_pkt_fdumpall(dec_pkt, stderr);
        fprintf(stderr, "\n");
        ln_pkt_decref(dec_pkt);
    }

fail:
    PERROR("fail");
    return;
}

void coroutine ln_run_write_sock(int sock, int pkt_in) {
    while (1) {
        int rc = fdout(sock, -1);
        if (rc < 0) goto fail;

        struct ln_pkt * pkt = NULL;
        rc = chrecv(pkt_in, &pkt, sizeof pkt, -1);
        if (rc < 0) goto fail;

        struct ln_pkt * enc_pkt = ln_pkt_enc(pkt, 0);
        if (enc_pkt == NULL) goto fail;
        struct ln_pkt_raw * pkt_raw = LN_PKT_CAST(enc_pkt, raw);
        if (pkt_raw == NULL) goto fail;

        do {
            rc = ln_pkt_raw_fsend(pkt_raw);
        } while (rc < 0 && errno == EAGAIN);
        if (rc < 0) goto fail;

        ln_pkt_decref(pkt);
    }

fail:
    PERROR("fail");
    return;
}

int main(int argc, char ** argv) {
    int raw_sock = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    if (raw_sock < 0) PFAIL("Unable to open socket");

    //int ctl = channel(1, 1);
    //if (ctl < 0) PFAIL("Unable to create control channel");

    int pkt_rx = channel(sizeof(struct ln_pkt_pkt *), 16);
    if (pkt_rx < 0) PFAIL("Unable to open pkt_rx channel");
    int pkt_tx = channel(sizeof(struct ln_pkt_pkt *), 16);
    if (pkt_tx < 0) PFAIL("Unable to open pkt_tx channel");

    go(ln_run_read_sock(raw_sock, pkt_rx));
    go(ln_run_write_sock(raw_sock, pkt_tx));

    while(1) {
        struct ln_pkt * pkt = NULL;
        int rc = chrecv(pkt_rx, &pkt, sizeof pkt, -1);
        if (rc < 0) FAIL("chrecv failed");

        // Do something with pkt here

        //rc = chsend(pkt_tx, &pkt, sizeof pkt, -1);
        //if (rc < 0) FAIL("chsend failed");
    }

    return 0;
}
