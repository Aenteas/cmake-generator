#include "A/AA/AAA/aaa.h"
#ifdef USE_liba_B_BA
#include "B/BA/ba.h"
#endif
#include "build_info_install.h"

#include <iostream>
using namespace std;

int main(int argc, char *argv[])
{
    AAA::print();
#ifdef USE_liba_B_BA
    cout << "Using BA dependency" << endl;
    BA::print();
#endif
}