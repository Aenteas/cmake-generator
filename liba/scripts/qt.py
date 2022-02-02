import os
import inspect

cmake_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def has_ui_file(rpath):
    include_path = os.path.join(cmake_root, rpath, "include", rpath)
    if os.path.exists(include_path):
        return len([name for name in os.listdir(include_path) if name.endswith(".ui")]) > 0
    return False

def find_package_content():
    return """
    # Find the QtWidgets library
    find_package(Qt5 REQUIRED COMPONENTS Widgets)
    """

def add_qt_lib_content(rpath):
    return inspect.cleandoc(f"""
    # create qt libraries
    file(GLOB QTFILES "include/{rpath}/*.ui")
    foreach(QTFILE ${{QTFILES}})
      cmake_path(GET QTFILE STEM NAME)
      add_library(ui_{{NAME}} apps/${{NAME}}.ui)
      )
    endforeach()""") + "\n\n"

