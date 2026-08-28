/* Fixture consumer: mimics mavlink_runtime.c — includes the header so it
 * gets its own private copy of the static function + local table. */
#include "mavlink_style.h"

uint32_t runtime_use(uint32_t msgid)
{
    const mavlink_msg_entry_t *e = mavlink_get_msg_entry(msgid);
    return e ? e->msgid : 0;
}
