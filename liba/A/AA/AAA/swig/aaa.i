%module aaa

%rename(show) AAA::print();

%{
#define SWIG_FILE_WITH_INIT
#include "aaa.h"
%}

%include "aaa.h"