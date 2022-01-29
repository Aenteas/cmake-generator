#include "A/AB/ABA/aba.h"
#include "A/AA/AAB/aab.h"
#include "build_info.h"
#ifdef USE_B_BA
    #include "B/BA/ba.h"
#endif

struct AAA{
    static void print();

    // test C++17 feature
    inline static int num = 10;
};