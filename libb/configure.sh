#! /bin/sh

mkdir -p build
rm -rf build/*
sudo cmake -B build -S . -DCMAKE_INSTALL_PREFIX="/home/david/projects/cmake/liba/_install"