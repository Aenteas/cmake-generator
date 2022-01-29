#! /bin/sh

mkdir -p build
rm -rf build/*
sudo cmake -B build -S . -DFORCE_NO_BUILD:STRING="B" -DCMAKE_INSTALL_PREFIX="/home/david/projects/cmake/liba/_install"