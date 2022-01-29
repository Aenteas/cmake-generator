#include "C/CA/CAA/caa.h"

#include <iostream>
using namespace std;

struct BA3{
    static void print(){
        cout << "BA3" << endl;
        CAA::print();
    }
};