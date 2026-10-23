/* SPDX-License-Identifier: GPL-3.0-or-later */
int main(int argc, char **argv)
{
    if (argc != 2) { return 2; }
    int scenario = atoi(argv[1]);
    sdcard.enabled = true;
    sdcard.state = SDCARD_STATE_READING;
    sdcard.operationStartTime = 1000;
    now = 1010;
    bool expect_reset = false;
    bool expect_ready = false;
    switch (scenario) {
    case 0: break; /* Normal pending read. */
    case 1: now = 1100; break; /* Exact read deadline retains existing <= semantics. */
    case 2: /* Deadline wraps while the current time has not yet wrapped. */
        sdcard.operationStartTime = UINT32_MAX - 49; now = UINT32_MAX - 9; break;
    case 3: /* Current time has also wrapped; elapsed time is 75 ms. */
        sdcard.operationStartTime = UINT32_MAX - 49; now = 25; break;
    case 4:
        sdcard.operationStartTime = UINT32_MAX - 49; now = 50; break;
    case 5:
        sdcard.state = SDCARD_STATE_WAITING_FOR_WRITE;
        sdcard.operationStartTime = UINT32_MAX - 100; now = UINT32_MAX - 50; break;
    case 6:
        sdcard.state = SDCARD_STATE_STOPPING_MULTIPLE_BLOCK_WRITE;
        sdcard.operationStartTime = UINT32_MAX - 100; now = UINT32_MAX - 50; break;
    case 7:
        sdcard.state = SDCARD_STATE_WAITING_FOR_WRITE;
        sdcard.operationStartTime = UINT32_MAX - 100; now = 100; break;
    case 8:
        sdcard.state = SDCARD_STATE_WAITING_FOR_WRITE;
        sdcard.operationStartTime = UINT32_MAX - 100; now = 150; expect_reset = true; break;
    case 9:
        sdcard.state = SDCARD_STATE_STOPPING_MULTIPLE_BLOCK_WRITE;
        now = 1251; expect_reset = true; break;
    case 10:
        sdcard.state = SDCARD_STATE_WAITING_FOR_WRITE;
        now = 1250; break;
    case 11:
        read_status = SDCARD_RECEIVE_SUCCESS; expect_ready = true; break;
    case 12:
        sdcard.enabled = false; break;
    default: return 2;
    }
    sdcardState_e initial = sdcard.state;
    bool ready = sdcardSdio_poll();
    if (ready != expect_ready) { return 3; }
    if (resets != (unsigned)expect_reset) { return 4; }
    sdcardState_e expected = !sdcard.enabled || expect_reset ? SDCARD_STATE_NOT_PRESENT :
        expect_ready ? SDCARD_STATE_READY : initial;
    if (sdcard.state != expected) { return 5; }
    if (sdcard.enabled && initial == SDCARD_STATE_READING && reads != 1) { return 6; }
    return 0;
}
