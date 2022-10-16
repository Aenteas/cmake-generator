#include "aaa2.h"
#include "build_info.h"
#ifdef USE_B_BA
    #include "B/BA/ba.h"
#endif
#include <iostream>
using namespace std;

void AAA2::print(){
    cout << "AAA2" << endl;
#ifdef USE_B_BA
    cout << "BA is used within AAA2" << endl;
    BA::print();
#else
    cout << "BA is not used within AAA2" << endl;
#endif
}