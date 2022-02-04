import inspect
import os

def find_package_content():
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "extra_libs.txt")) as f:
        find_commands = ""
        for line in f.readlines():
            parts = line.split("Qt5::")
            if len(parts) == 2:
                lib = parts[1].replace('\n','')
                find_commands += f"find_package(Qt5 REQUIRED COMPONENTS {lib})\n"
        return "# Find the QtWidgets library\n" + find_commands + "set(CMAKE_AUTOMOC ON)\nset(CMAKE_AUTOUIC ON)\nset(CMAKE_AUTORCC ON)\n"

def add_qt_lib_content(rpath):
    return inspect.cleandoc(f"""
    # create qt libraries
    file(GLOB QTFILES "src/*.ui")
    foreach(QTFILE ${{QTFILES}})
      cmake_path(GET QTFILE STEM NAME)
      add_library(ui_${{NAME}} src/${{NAME}}.ui)
    endforeach()
    
    file(GLOB QTFILES "apps/*.ui")
    foreach(QTFILE ${{QTFILES}})
      cmake_path(GET QTFILE STEM NAME)
      add_library(ui_${{NAME}} apps/${{NAME}}.ui)
    endforeach()""") + "\n\n"
