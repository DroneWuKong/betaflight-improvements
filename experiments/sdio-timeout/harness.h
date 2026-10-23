/* SPDX-License-Identifier: GPL-3.0-or-later
 * Host-only boundary stubs for the actual upstream sdcardSdio_poll function.
 * These do not model DMA, peripheral reset, or physical SD-card timing.
 */
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define SD_OK 0
#define SDCARD_BLOCK_OPERATION_READ 0
#define SDCARD_BLOCK_OPERATION_WRITE 1

static struct {
    bool enabled, useCache;
    sdcardState_e state;
    uint32_t operationStartTime, multiWriteBlocksRemain, multiWriteNextBlock;
    unsigned failureCount;
    struct {
        uint8_t *buffer;
        uint32_t blockIndex, callbackData;
        void (*callback)(int, uint32_t, uint8_t *, uint32_t);
    } pendingOperation;
} sdcard;

static uint32_t now;
static unsigned reads, resets;
static sdcardReceiveBlockStatus_e read_status = SDCARD_RECEIVE_BLOCK_IN_PROGRESS;
static uint32_t millis(void) { return now; }
static bool SD_GetState(void) { return false; }
static int SD_CheckWrite(void) { return 1; }
static bool sdcard_checkInitDone(void) { return true; }
static bool sdcard_fetchCSD(void) { return true; }
static bool sdcard_receiveCID(void) { return true; }
static void cache_reset(void) { }
static void sdcard_endWriteBlocks(void) { sdcard.state = SDCARD_STATE_READY; }
static bool sdcard_isReady(void) {
    return sdcard.state == SDCARD_STATE_READY || sdcard.state == SDCARD_STATE_WRITING_MULTIPLE_BLOCKS;
}
static void sdcard_reset(void) {
    ++resets;
    sdcard.state = SDCARD_STATE_NOT_PRESENT;
}
static sdcardReceiveBlockStatus_e sdcard_receiveDataBlock(uint8_t *buffer, int count) {
    (void)buffer;
    (void)count;
    /* An actual poll must return to its caller instead of re-reading in a loop. */
    if (++reads > 8) { exit(73); }
    return read_status;
}
