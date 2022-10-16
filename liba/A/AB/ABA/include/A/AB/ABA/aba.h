#include "A/AB/ABB/abb.h"
#include <iostream>
using namespace std;

struct ABA{
    static void print(){
        cout << "ABA" << endl;
        ABB::print();
    }
};