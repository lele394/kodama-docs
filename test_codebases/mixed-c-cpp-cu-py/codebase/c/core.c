#include "core.h"
#include "../include/mixed/version.h"

/*
Maximum count reported by mixed_call_count().
This is a multiline developer comment on a macro.
*/
#define CORE_MAX 1024

/* Number of additions performed by this translation unit. */
static int call_count = 0;

/*
Add two integers and count the operation.
This is a multiline block comment: both lines must stick to the function.
*/
int c_add(int a, int b) {
    call_count++;
    return a + b;
}

/* Scale a value after adding zero to it. */
int c_scale(int value, int factor) {
    return c_add(value, 0) * factor;
}

/* Return the version macro exposed by the public header. */
int mixed_version(void) {
    return MIXED_VERSION;
}

/* Expose the global counter to callers that want to check it. */
int mixed_call_count(void) {
    return call_count > CORE_MAX ? CORE_MAX : call_count;
}
