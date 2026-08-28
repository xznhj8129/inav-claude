/* Fixture: MAVLink-style macro-hidden static linkage with a local static
 * aggregate table inside a header-defined function — the exact pattern of
 * the confirmed mavlink_get_msg_entry duplication bug. */
#ifndef FIXTURE_MAVLINK_STYLE_H
#define FIXTURE_MAVLINK_STYLE_H

#include <stdint.h>

#ifndef MAVLINK_HELPER
#define MAVLINK_HELPER
#endif

typedef struct {
    uint32_t msgid;
    uint8_t crc_extra;
    uint8_t min_msg_len;
    uint8_t max_msg_len;
    uint8_t flags;
    uint16_t target_system_ofs;
    uint16_t target_component_ofs;
} mavlink_msg_entry_t;

/* protocol.h expands MAVLINK_HELPER to plain `static` in the normal build;
 * emulate that here so the tool sees internal linkage through the macro. */
#undef MAVLINK_HELPER
#define MAVLINK_HELPER static

MAVLINK_HELPER const mavlink_msg_entry_t *mavlink_get_msg_entry(uint32_t msgid)
{
    static const mavlink_msg_entry_t mavlink_message_crcs[] = {
        {0, 50, 9, 9, 0, 0, 0},
        {1, 51, 10, 10, 0, 0, 0},
        {2, 52, 11, 11, 0, 0, 0},
        {3, 53, 12, 12, 0, 0, 0},
        {4, 54, 13, 13, 0, 0, 0},
    };
    uint32_t low = 0, high = sizeof(mavlink_message_crcs) / sizeof(mavlink_message_crcs[0]) - 1;
    (void)msgid;
    return &mavlink_message_crcs[low];
}

#endif /* FIXTURE_MAVLINK_STYLE_H */
