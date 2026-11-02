#ifndef MIXED_MATH_HPP
#define MIXED_MATH_HPP

namespace mixed {

/* Header-only template: exercises function definitions outside a .cpp. */
template <typename T>
inline T clamp_value(T value, T low, T high) {
    if (value < low) {
        return low;
    }
    return value > high ? high : value;
}

/*
kodama-docs-llm:skip
Legacy helper kept for ABI compatibility; the class skip also covers its
members, so legacy_add gets no LLM task either.
*/
class LegacyMath {
public:
    int legacy_add(int a, int b) {
        return a + b;
    }
};

}  // namespace mixed

#endif /* MIXED_MATH_HPP */
