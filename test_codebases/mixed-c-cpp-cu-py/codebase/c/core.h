#ifndef MIXED_CORE_H
#define MIXED_CORE_H

#ifdef __cplusplus
extern "C" {
#endif

/* Add two integers; the C entry point used by C++ and Python. */
int c_add(int a, int b);

/* Scale a value after routing it through c_add (exercises a same-file call). */
int c_scale(int value, int factor);

/* Version of this little native core. */
int mixed_version(void);

#ifdef __cplusplus
}
#endif

#endif /* MIXED_CORE_H */
