/* Fixture consumer: mimics mavlink_routing.c — same header, second private
 * copy. */
#include "mavlink_style.h"
#include "trivial_accessors.h"

uint32_t routing_use(uint32_t msgid)
{
    const mavlink_msg_entry_t *e = mavlink_get_msg_entry(msgid);
    if (e) {
        return e->msgid + cfgGetType((const cfg_t *)0);
    }
    return 0;
}
