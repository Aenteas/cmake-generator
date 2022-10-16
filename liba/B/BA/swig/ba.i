%module ba

%rename(show) BA::print();

%{
#define SWIG_FILE_WITH_INIT
#include "ba.h"
%}

%include "ba.h"