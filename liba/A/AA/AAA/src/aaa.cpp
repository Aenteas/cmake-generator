#include "aaa.h"

#include <iostream>
using namespace std;

void AAA::print(){
    cout << "AAA" << endl;
    ABA::print();
    AAB::print();
#ifdef USE_B_BA
    cout << "BA is used within AAA" << endl;
    BA::print();
#else
    cout << "BA is not used within AAA" << endl;
#endif
}