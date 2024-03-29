import sys
import parse_includes
import glob, os
import re
import inspect
import textwrap
import traceback
import argparse
import shutil

argparser = argparse.ArgumentParser()

argparser.add_argument('--clean', action='store_true', required=False, default=False, help="clean project")

argparser.add_argument('--swig_python', action='store_true', required=False, default=False, help="generating python-swig content")

argparser.add_argument('--qt', action='store_true', required=False, default=False, help="support Qt project")

argparser.add_argument('--googletest', action='store_true', required=False, default=False, help="add googletest")

argparser.add_argument('--cpp_version', type=int, required=False, choices = [11, 14, 17], default=17, help="C++ version, 11, 14 or 17")

args = vars(argparser.parse_args())

cmake_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

use_swig_python = args["swig_python"]
use_qt = args["qt"]
use_googletest = args["googletest"]
if use_qt: import qt
cpp_version = args["cpp_version"]

def determine_project_folders():
    # search in folders to generate CMakeLists.txt files
    folders = {name for name in os.listdir(cmake_root) if os.path.isdir(os.path.join(cmake_root, name))}
    hidden_folders = {os.path.basename(p) for p in glob.glob(os.path.join(cmake_root, ".*"))}
    # special folder names (see README)
    folders.discard("external")
    folders.discard("build")
    folders.discard("scripts")
    folders.discard("python")
    folders.discard("apps")
    folders.discard("cmake")
    return list(folders - hidden_folders)

subdirs = determine_project_folders()

def get_lib_dirs():
    # find root directories with the C++ source and header files
    lib_dirs = []
    for dir in subdirs:
        lib_dirs.extend([os.path.relpath(path, cmake_root)[:-8] 
        for path in glob.glob(os.path.join(cmake_root, dir, "**", "include"), recursive=True)
        if not os.path.sep + "external" + os.path.sep in path])
    for dir in subdirs:
        lib_dirs.extend([os.path.relpath(path, cmake_root)[:-5] 
        for path in glob.glob(os.path.join(cmake_root, dir, "**", "apps"), recursive=True)
        if not os.path.sep + "external" + os.path.sep in path and not os.path.relpath(path, cmake_root)[:-5] in lib_dirs])
    return lib_dirs

def buildTree(dirs):
    # builds project directory tree
    tree = {}
    for dir in dirs:
        folders = dir.split(os.path.sep)
        subtree = tree
        for folder in folders:
            if not folder in subtree:
                subtree[folder] = {}
            subtree = subtree[folder]
    return tree

def add_indents(text, num=1):
    # indent text (one indent equals to 2 spaces in each line)
    return textwrap.indent(text, ' ' * 2 * num)

def source_path(rpath, name):
    # source files are supposed to be placed under src or apps (executable) folders
    src_path = os.path.join(cmake_root, rpath, "src", name) + ".cpp"
    if os.path.exists(src_path): return src_path
    else: return os.path.join(cmake_root, rpath, "apps", name) + ".cpp"

def header_path(rpath, name):
    # header files should be under include folder
    return os.path.join(cmake_root, rpath, "include", rpath, name) + ".h"

def get_path(rpath, name, is_header):
    # returns path to header/source file given its name
    return header_path(rpath, name) if is_header else source_path(rpath, name)

def remove_extension(path):
    return ".".join(path.split(".")[:-1])

def get_file_names(rpath):
    # returns list of source file names
    res = []
    if os.path.exists(os.path.join(cmake_root, rpath, "src")):
        res = [remove_extension(p) for p in os.listdir(os.path.join(cmake_root, rpath, "src"))]
    if os.path.exists(os.path.join(cmake_root, rpath, "apps")):
        res += [remove_extension(p) for p in os.listdir(os.path.join(cmake_root, rpath, "apps"))]
    return  res

def include_to_rpath(include):
    return os.path.sep.join(include.split("/")[:-1])

def include_to_name(include):
    return include.split("/")[-1]

def add_to_build_info(prefix, install):
    """
    a header file will be generated with cmake macros of the format:
    USE_(<PROJECT_NAME>)<RELPATH_TO_LIBRARY_ROOT>

    for example <prefix>/A/AA/AAA will be USE_A_AA_AAA
    each library can be built optionally using the -DFORCE_(NO_)BUILD cmake arguments
    each will be defined if the library is built

    these macros can be included to other source files to access build information
    """
    str_install = "_install" if install else ""
    os.umask(0)
    os.makedirs(os.path.join(cmake_root, "build", "include"), mode=0o777, exist_ok=True)
    location = os.path.join(cmake_root, "build", "include", f"build_info{str_install}.h.in")
    # C++ comment with //
    content = ""
    macro = "_".join(prefix.upper().split(os.path.sep))
    project_name = cmake_root.split(os.path.sep)[-1]
    str_project_name = f"{project_name}_" if install else ""
    content += f"#cmakedefine USE_{str_project_name}{macro}\n"
    with open(location, 'a') as f:
        f.write(content)

def header_content():
    return f"cmake_minimum_required (VERSION 3.22.0)\n\n"

def path_to_ns(postfix):
    return '.'.join(postfix.split(os.path.sep)) + '.'

def caller_content(prefix, dirs):
    # non-library directories call the add_subdirectory command on each subfolder
    prefix_macro = "_".join(prefix.upper().split(os.path.sep))
    if prefix_macro != "": prefix_macro += '_'
    calls = ""
    for dir in dirs:
        message = ""
        if os.path.exists(os.path.join(cmake_root, prefix, dir, "include")):
            lib_path = os.path.join(cmake_root, prefix, dir)
            message_content = f"Configuring library at {lib_path} ..."
            message = f'  message(STATUS "{message_content}")\n'
        elif os.path.exists(os.path.join(cmake_root, prefix, dir, "apps")):
            lib_path = os.path.join(cmake_root, prefix, dir)
            message_content = f"Configuring application at {lib_path} ..."
            message = f'  message(STATUS "{message_content}")\n'
        macro = prefix_macro + dir.upper()
        calls += f"if(USE_{macro})\n" + message + f"  add_subdirectory({dir})\nendif()\n"

    return calls + "\n"

def init_content(postfix):
    # setup project name, namespace etc
    project_name = postfix.split(os.path.sep)[-1]
    folder_name = postfix.split(os.path.sep)[0]
    install_namespace = path_to_ns(postfix)
    return inspect.cleandoc(f"""
    project({project_name})

    # export public include directory path
    # we are using INSTALL(DIRECTORY) in the top level CMakeLists.txt file so we need to include the folder {folder_name} as well.
    # include/{postfix}/*.h -> <install_prefix>/include/{postfix}/*.h
    set(INCLUDE_DIRS "${{INCLUDE_DIRS}};${{CMAKE_CURRENT_SOURCE_DIR}}/include/{folder_name}" CACHE INTERNAL "")

    # you can not use alias for install targets but the name should be unique so we use a namespace variable
    # see https://stackoverflow.com/questions/67757157/change-exported-target-name-in-cmake-install-alias-to-a-target
    set(NS ${{MAIN_PROJECT}}.{install_namespace})
    """)

def add_lib_content(postfix):
    # CMake script to setup local libraries
    install_namespace = path_to_ns(postfix)
    local = f"""
      PUBLIC
        $<BUILD_INTERFACE:${{CMAKE_CURRENT_SOURCE_DIR}}/include>
        $<INSTALL_INTERFACE:include>
      PRIVATE
        $<BUILD_INTERFACE:${{CMAKE_CURRENT_SOURCE_DIR}}/include/{postfix}>
        $<INSTALL_INTERFACE:include/{postfix}>"""

    exported = f"""
      INTERFACE
        $<BUILD_INTERFACE:${{CMAKE_CURRENT_SOURCE_DIR}}/include>
        $<INSTALL_INTERFACE:include>"""

    glob_include = f"include_directories(${{ROOT_BINARY_DIR}}/include)"
    return f"\n# Global include directory\n{glob_include}\n\n" + inspect.cleandoc(f"""
    # create shared libraries
    # interface library to provide path to the include dir
    add_library(${{NS}}INTERFACE INTERFACE)
    add_library({install_namespace}INTERFACE ALIAS ${{NS}}INTERFACE)

    set(TARGETS "${{TARGETS}};${{NS}}INTERFACE" CACHE INTERNAL "")

    target_include_directories(${{NS}}INTERFACE{exported}
    )

    file(GLOB SOURCES "src/*.cpp")
    foreach(SOURCE ${{SOURCES}})
      cmake_path(GET SOURCE STEM NAME)
      add_library(${{NS}}${{NAME}} SHARED include/{postfix}/${{NAME}}.h src/${{NAME}}.cpp)
      add_library({install_namespace}${{NAME}} ALIAS ${{NS}}${{NAME}})
      # add to the exported targets
      set(TARGETS "${{TARGETS}};${{NS}}${{NAME}}" CACHE INTERNAL "")

      target_include_directories(${{NS}}${{NAME}} {add_indents(local)}
      )
    endforeach()
    """) + "\n\n"

def add_swig_content(postfix):
    # CMake script to create swig targets. They will be installed from the top CMakeLists.txt file
    install_namespace = path_to_ns(postfix)
    python_prefixes = [os.path.sep]
    for folder in postfix.split(os.path.sep):
        python_prefixes.append(python_prefixes[-1] + folder + os.path.sep)
    python_prefixes = ";".join(python_prefixes)
    content = inspect.cleandoc(f"""
    # setting up python modules

    # find SWIG module and include it
    find_package(SWIG)
    include(UseSWIG)

    # find python libraries
    find_package(PythonLibs)

    # the generated cxx file myVectorPYTHON_wrap.cxx uses the python library #include <Python.h> )
    include_directories(${{PYTHON_INCLUDE_PATH}})

    file(GLOB SWIG_INTERFACES "swig/*.i")

    if(SWIG_INTERFACES)
      make_directory(${{ROOT_BINARY_DIR}}/python/${{MAIN_PROJECT}}/{postfix})
      set(PYTHON_PREFIXES {python_prefixes})
      foreach(PYTHON_PREFIX ${{PYTHON_PREFIXES}})
        file(TOUCH ${{ROOT_BINARY_DIR}}/python/${{MAIN_PROJECT}}${{PYTHON_PREFIX}}__init__.py)
      endforeach()
    endif()

    # creating/linking swig targets
    foreach(SWIG_INTERFACE ${{SWIG_INTERFACES}})
      cmake_path(GET SWIG_INTERFACE STEM NAME)
      set_source_files_properties(swig/${{NAME}}.i PROPERTIES CPLUSPLUS ON)
      set_source_files_properties(swig/${{NAME}}.i PROPERTIES INCLUDE_DIRECTORIES ${{CMAKE_CURRENT_SOURCE_DIR}}/include/{postfix})

      swig_add_library(${{NAME}}SWIG 
        LANGUAGE python
        OUTPUT_DIR ${{ROOT_BINARY_DIR}}/python/${{MAIN_PROJECT}}/{postfix}
        OUTFILE_DIR ${{ROOT_BINARY_DIR}}/python/${{MAIN_PROJECT}}/{postfix}
        SOURCES swig/${{NAME}}.i)

      target_include_directories(${{NAME}}SWIG PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}}/include/{postfix})

      add_library({install_namespace}${{NAME}}SWIG ALIAS ${{NAME}}SWIG)

      swig_link_libraries(${{NAME}}SWIG {install_namespace}${{NAME}} ${{PYTHON_LIBRARIES}})

      # LIBRARY_OUTPUT_DIRECTORY will be the location for _<libname>SWIG.so
      SET_TARGET_PROPERTIES(${{NAME}}SWIG PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${{ROOT_BINARY_DIR}}/python/${{MAIN_PROJECT}}/{postfix})

      # Files to install with Python
      set(PYTHON_INSTALL_FILES "${{PYTHON_INSTALL_FILES}};${{ROOT_BINARY_DIR}}/python/${{MAIN_PROJECT}}/{postfix}/${{NAME}}.py" CACHE INTERNAL "")
      set(PYTHON_INSTALL_FILES "${{PYTHON_INSTALL_FILES}};${{ROOT_BINARY_DIR}}/python/${{MAIN_PROJECT}}/{postfix}/_${{NAME}}SWIG.so" CACHE INTERNAL "")

      set(PYTHON_INSTALL_RPATHS "${{PYTHON_INSTALL_RPATHS}};${{MAIN_PROJECT}}/{postfix}" CACHE INTERNAL "")
      set(PYTHON_INSTALL_RPATHS "${{PYTHON_INSTALL_RPATHS}};${{MAIN_PROJECT}}/{postfix}" CACHE INTERNAL "")

      set(SWIG_TARGETS "${{SWIG_TARGETS}};{install_namespace}${{NAME}}SWIG" CACHE INTERNAL "")
      
    endforeach()
    """)
    return content


def add_exe_content(postfix):
    # CMake script content for adding executable targets
    local = f"""
      PRIVATE
        $<BUILD_INTERFACE:${{CMAKE_CURRENT_SOURCE_DIR}}/include/{postfix}>
        $<INSTALL_INTERFACE:include/{postfix}>"""
    
    return inspect.cleandoc(f"""
    # create executables
    file(GLOB EXES "apps/*.cpp")
    foreach(EXE ${{EXES}})
      cmake_path(GET EXE STEM NAME)
      add_executable(${{NS}}${{NAME}} apps/${{NAME}}.cpp)
      target_include_directories(${{NS}}${{NAME}} {add_indents(local)}
      )
    endforeach()""") + "\n\n"

def is_local(include):
    # include is local when it is inside the same lib directory as the file it is included into
    return include.count('/') == 0

def link_contents(project_rpath):

    def rpath_sets_to_interface_alias_sets(missing_include_dirs):
        aliases = {"PRIVATE": set(), "PUBLIC": set()}
        for k, v in missing_include_dirs.items():
            for rpath in v:
                name = path_to_ns(rpath) + "INTERFACE"
                aliases[k].add(f"$<TARGET_PROPERTY:{name},INTERFACE_INCLUDE_DIRECTORIES>")
        return aliases

    def deps_content(deps, specifier):
        if deps:
            content = "\n".join(deps) + "\n"
            return f"  {specifier}\n" + add_indents(content, 2)
        else:
            return ""

    def to_macro(name):
        macro = "_".join(name.upper().split(".")[:-1])
        return f"USE_{macro}"

    def read_extra_links():
        path = os.path.join(cmake_root, "scripts", "extra_libs.txt")
        res = {}
        with open(path, 'r') as f:
            lines = f.readlines()
            for line in lines:
                if not line.startswith("#"):
                    items = line.split(" ")
                    if len(items) <= 1:
                        raise ValueError(line + f" in {path} has wrong format.")
                    # remove .h extension
                    res[items[0][:-2]] = items[1:]
        return res

    def extract_includes(rpath, name, is_header = True):
        
        includes = parse_includes.find_includes(get_path(rpath, name, is_header))

        # include "path_to_header/header_name.h" -> path_to_header/header_name
        regex = '.*".*".*'
        user_includes = set()
        qt_includes = set()
        for incl in includes:
            if not re.search(regex, incl) is None:
                name = incl.split('"')[1][:-2]
                if use_qt and incl.split('"')[1].startswith("ui_"):
                    if not is_local(incl):
                        header_location = os.path.join(cmake_root, rpath, "include", rpath, name)
                        raise ValueError(f"Error. One of your UI files included to {header_location} from an other include directory.")
                    qt_includes.add(name)
                elif not "build_info.h" in incl:
                    user_includes.add(name)

        regex = '.*<.*>.*'
        extra_includes = {incl.split('<')[-1].split('>')[0][:-2] for incl in includes 
        if not re.search(regex, incl) is None and incl.split('<')[-1].split('>')[0][:-2] in extra_links}

        return (user_includes, extra_includes, qt_includes)

    def target_link_extra_libraries_content():
        content = ""
        # these are libraries that are not defined in the project and not linked by CMake automatically like the cmath library
        # and other libraries like qt
        # merge dependencies
        if use_qt and qt_deps["PUBLIC"] | qt_deps["PRIVATE"]:
            qt_deps["PRIVATE"].add("Qt5::Widgets")
        extra_deps["PUBLIC"] |= qt_deps["PUBLIC"]
        extra_deps["PRIVATE"] |= qt_deps["PRIVATE"]
        if extra_deps:
            command = f"target_link_libraries(${{NS}}{target}\n"
            for k, v in extra_deps.items():
                content += add_indents(deps_content(list(v), k))
            if content:
                content = command + content + ")\n\n"
        return content

    def target_link_libraries_content():
        if deps:
            content = ""
            for k, v in deps.items():
                for name in v:
                    content += f"if({to_macro(name)})\n"
                    content += f"  target_link_libraries(${{NS}}{target}\n{add_indents(deps_content([name], k))}"
                    content += "  )\n"
                    content += "endif()\n\n"
            return content
        else:
            return ""

    def target_include_directories_content():
        if project_interfaces:
            content = ""
            for k, v in project_interfaces.items():
                if v:
                    content += deps_content(list(v), k)
            return f"target_include_directories(${{NS}}{target}\n" + content + ")\n\n" if content else ""
        return ""

    def try_get_source_ns(include, rpath):
        is_local_link = is_local(include)
        folders = rpath.split('/') if is_local_link else include.split('/')[:-1]
        name = include.split('/')[-1]
        if os.path.exists(os.path.join(cmake_root, *folders, "src", f"{name}.cpp")):
            return ".".join(folders) + f".{name}"
        else: # return None if included file does not have a source
            return None

    def merge_deps():
        # merging public/private links and include statements

        missing_include_dirs = {
            "PRIVATE": required_include_dirs["PRIVATE"] - included_dirs["PRIVATE"],
            "PUBLIC": required_include_dirs["PUBLIC"] - included_dirs["PUBLIC"],
        }
        # if we have the same dependency as private and public its just public
        missing_include_dirs["PRIVATE"] -= missing_include_dirs["PUBLIC"]
        deps["PRIVATE"] -= deps["PUBLIC"]
        extra_deps["PRIVATE"] -= extra_deps["PUBLIC"]

        project_interfaces.update(rpath_sets_to_interface_alias_sets(missing_include_dirs))

    def check_circular_dependency(collector):
        # decorator to prevent infinite recursion while finding linking relationships
        def check(rpath, name, is_header, access):
            dep = os.path.join(rpath, name)
            # we could detect general dependency cycles but they would be detected by cmake anyway
            # header-only dependency cycle would cause infinite recursion that is why we should detect it
            # it is better to not have it at the first place but forward declaration can make it work
            if dep in dependencies:
                # stop search
                return
            else:
                if is_header:
                    dependencies.add(dep)
                # getting the collected dependencies
                res = collector(rpath, name, is_header, access)
                if is_header:
                    dependencies.remove(dep)
                # returning the collected dependencies
                return res
    
        return check
    
    @check_circular_dependency
    def collect_dependecies(rpath, name, is_header, access):
        # find sources for each target to link (private/interface/public) in CMake script
        includes, extra_includes, qt_includes = extract_includes(rpath, name, is_header)
        qt_deps[access] |= qt_includes
        for include in extra_includes:
            extra_deps[access].update(extra_links[include])
        for include in includes:
            is_target_header_include = include == name and not is_header
            source = None if include == name else try_get_source_ns(include, rpath)
            prefix = rpath if is_local(include) else include_to_rpath(include)
            global_include = prefix.replace(os.path.sep, "/")
            # header only dependency, search recursively for its library dependencies
            if source is None:
                if is_target_header_include:
                    collect_dependecies(prefix, include_to_name(include), True, "PUBLIC")
                else:
                    required_include_dirs[access].add(global_include)
                    collect_dependecies(prefix, include_to_name(include), True, access)
            # library dependency, link to target
            else:
                included_dirs[access].add(global_include)
                deps[access].add(source)
    
    extra_links = read_extra_links()
    sys.setrecursionlimit(500)
    content = ""
    targets = get_file_names(project_rpath)
    project_interfaces = {"PUBLIC": set(), "PRIVATE": set()}
    for target in targets:
        # reset variables
        dependencies = set()
        included_dirs = {"PUBLIC": set([project_rpath]), "PRIVATE": set([project_rpath])}
        required_include_dirs = {"PUBLIC": set(), "PRIVATE": set()}
        deps = {"PUBLIC": set(), "PRIVATE": set()}
        extra_deps = {"PUBLIC": set(), "PRIVATE": set()}
        qt_deps = {"PUBLIC": set(), "PRIVATE": set()}
        try:
            collect_dependecies(project_rpath, target, False, "PRIVATE")
            merge_deps()
            content += target_link_libraries_content()
            content += target_link_extra_libraries_content()
            content += target_include_directories_content()
        except Exception as e:
            _, _, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(e, fname, exc_tb.tb_lineno + "\n\n")
            print("deleting generated CMakeLists.txt files ...")
            clean()
            print("stack trace:\n", traceback.format_exc() + "\n\n")
            sys.exit()
    if content != "": content = "# link libraries\n" + content
    return content

def clean():
    # delete generated files/directories
    files = []
    top_cmake_file = os.path.join(cmake_root, "CMakeLists.txt")
    if os.path.exists(top_cmake_file):
        os.remove(top_cmake_file)
    for dir in subdirs:
        files.extend([path for path in glob.glob(os.path.join(cmake_root, dir, "**", "CMakeLists.txt"), recursive=True)])
    files.extend([path for path in glob.glob(os.path.join(cmake_root, "**", "*.h.in"), recursive=True)])
    if os.path.exists(os.path.join(cmake_root, "build")):
        shutil.rmtree(os.path.join(cmake_root, "build"))
    if os.path.exists(os.path.join(cmake_root, "_install")):
        shutil.rmtree(os.path.join(cmake_root, "_install"))
    files.append(os.path.join(cmake_root, "cmake", "Config.cmake.in"))
    for file in files:
        # do not touch external libraries
        if not os.path.sep + "external" + os.path.sep in file and os.path.exists(file):
            os.remove(file)

def create_top_cmakelists():
    subdir_content = caller_content("", subdirs)
    main_project = os.path.basename(cmake_root)
    content = header_content() + inspect.cleandoc(f"""
    project({main_project} VERSION 1.2.3)
    # we need it so we can output generated files under ROOT_BINARY_DIR/python (python modules) and ROOT_BINARY_DIR/lib (C++ libraries)
    set(ROOT_BINARY_DIR ${{PROJECT_BINARY_DIR}})
    set(MAIN_PROJECT ${{PROJECT_NAME}})

    # set C++ compiler version

    set(CMAKE_CXX_STANDARD {cpp_version} CACHE STRING "The C++ standard to use")
    set(CMAKE_CXX_STANDARD_REQUIRED ON)
    set(CMAKE_CXX_EXTENSIONS OFF)
    """)

    if use_googletest:
        content += "\n\n"
        content += "find_package(GTest REQUIRED)"

    if use_qt:
        content += "\n\n"
        content += qt.find_package_content()

    content += "\n"

    content += inspect.cleandoc(f"""
    # external projects could see target libraries by just calling find_package in CMake script instead of calling 
    # export LD_LIBRARY_PATH=<project_root>/cmake/liba/_install/lib/ which is not the best practice
    set(CMAKE_INSTALL_RPATH "${{CMAKE_INSTALL_PREFIX}}/lib")
    set(CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE)

    # build options
    set(FORCE_BUILD "" CACHE STRING "List of relative paths to build")
    set(FORCE_NO_BUILD "" CACHE STRING "List of relative paths to not build")

    # build options will be processed by python script to check logical/spelling errors
    # it will output option variables
    set(OPTION_PY_IN ${{CMAKE_CURRENT_SOURCE_DIR}}/scripts/create_cmake_options.py.in)
    set(OPTION_PY_OUT ${{CMAKE_CURRENT_BINARY_DIR}}/scripts/create_cmake_options.py)

    # python fsting uses the curly brackets so we need to aply @ONLY to insert CMake variables
    configure_file(${{OPTION_PY_IN}} ${{OPTION_PY_OUT}} @ONLY)

    # call python script
    execute_process(
    COMMAND python3 ${{OPTION_PY_OUT}}
    OUTPUT_STRIP_TRAILING_WHITESPACE
    OUTPUT_VARIABLE OPTIONS
    RESULT_VARIABLE EXIT_STATUS)

    # if script runs without errors
    if(EXIT_STATUS EQUAL "0")
      foreach(OPTION_STR ${{OPTIONS}})
        # parsing python output to get build options
        string(REPLACE ":" ";" BUILD_OPTION ${{OPTION_STR}})
        # format is <option name>:<description>:<ON/OFF>
        list (GET BUILD_OPTION 0 OPTION_NAME)
        list (GET BUILD_OPTION 1 OPTION_DESC)
        list (GET BUILD_OPTION 2 OPTION_FLAG)
        option(USE_${{OPTION_NAME}} "${{OPTION_DESC}}" ${{OPTION_FLAG}})
        set(USE_${{OPTION_NAME}} ${{OPTION_FLAG}} CACHE INTERNAL "")

        option(USE_${{MAIN_PROJECT}}_${{OPTION_NAME}} "${{OPTION_DESC}}" ${{OPTION_FLAG}})
      endforeach()
      # saving build options to header files 
      set(BUILD_CONFIG_IN ${{CMAKE_CURRENT_BINARY_DIR}}/include/build_info.h.in)
      set(BUILD_CONFIG_OUT ${{CMAKE_CURRENT_BINARY_DIR}}/include/build_info.h)
      configure_file(${{BUILD_CONFIG_IN}} ${{BUILD_CONFIG_OUT}})

      set(INSTALL_CONFIG_IN ${{CMAKE_CURRENT_BINARY_DIR}}/include/build_info_install.h.in)
      set(INSTALL_CONFIG_OUT ${{CMAKE_CURRENT_BINARY_DIR}}/include/build_info_install.h)
      configure_file(${{INSTALL_CONFIG_IN}} ${{INSTALL_CONFIG_OUT}})

      # declare lists for targets and include dirs so subdirectories can update them
      # INTERNAL creates a make-shift global variable that can be updated from subdirectories
      set(TARGETS "" CACHE INTERNAL "")
      set(INCLUDE_DIRS "" CACHE INTERNAL "")
      """)

    content += "\n"

    if use_swig_python:
        content += add_indents(inspect.cleandoc("""
      # files/locations to install for python interface/modules
      set(PYTHON_INSTALL_FILES "" CACHE INTERNAL "")
      set(PYTHON_INSTALL_RPATHS "" CACHE INTERNAL "")
      set(SWIG_TARGETS "" CACHE INTERNAL "")
      """))

        content += "\n\n"
    
    content += add_indents(inspect.cleandoc(subdir_content))

    content += "\n\n"

    content += add_indents(inspect.cleandoc(f"""
      # includes for install/exporting
      include(GenerateExportHeader)
      include(GNUInstallDirs)
      include(CMakePackageConfigHelpers)

      # Configuration

      set(CONFIG_INSTALL_DIR "${{CMAKE_INSTALL_LIBDIR}}/cmake/${{PROJECT_NAME}}")

      set(VERSION_CONFIG "${{CMAKE_CURRENT_BINARY_DIR}}/cmake/${{PROJECT_NAME}}ConfigVersion.cmake")
      set(PROJECT_CONFIG "${{CMAKE_CURRENT_BINARY_DIR}}/cmake/${{PROJECT_NAME}}Config.cmake")

      # generate the version file for the config file
      # if VERSION argument is not set it uses PROJECT_VERSION
      write_basic_package_version_file(
        "${{VERSION_CONFIG}}"
        COMPATIBILITY SameMajorVersion
      )

      configure_package_config_file(
        "cmake/Config.cmake.in"
        "${{PROJECT_CONFIG}}"
        INSTALL_DESTINATION "${{CONFIG_INSTALL_DIR}}"
      )

      # <install_prefix>/lib/cmake/<project_name>/
      install(
        FILES "${{PROJECT_CONFIG}}" "${{VERSION_CONFIG}}"
        DESTINATION "${{CONFIG_INSTALL_DIR}}"
      )

      # remove leading ;
      string(SUBSTRING "${{TARGETS}}" 1 -1 TARGETS)
      string(SUBSTRING "${{INCLUDE_DIRS}}" 1 -1 INCLUDE_DIRS)
      
      # <install_prefix>/lib/<target_name>
      foreach(TARGET ${{TARGETS}})
        install(
          TARGETS ${{TARGET}}
          EXPORT ${{PROJECT_NAME}}_Targets
          LIBRARY DESTINATION "${{CMAKE_INSTALL_LIBDIR}}"
          ARCHIVE DESTINATION "${{CMAKE_INSTALL_LIBDIR}}"
          RUNTIME DESTINATION "${{CMAKE_INSTALL_BINDIR}}"
          INCLUDES DESTINATION "${{CMAKE_INSTALL_INCLUDEDIR}}"
        )
      endforeach()

      # there is no namespace as the target names are already contain make-shift namespaces
      # see https://stackoverflow.com/questions/67757157/change-exported-target-name-in-cmake-install-alias-to-a-target
      install(
        EXPORT "${{PROJECT_NAME}}_Targets"
        DESTINATION "${{CONFIG_INSTALL_DIR}}"
      )

      # <install_prefix>/include/<rel_path_to_header_file>
      foreach(ITEM ${{INCLUDE_DIRS}})
        install(
          DIRECTORY ${{ITEM}}
          DESTINATION "${{CMAKE_INSTALL_INCLUDEDIR}}"
          FILES_MATCHING PATTERN "*.h"
        )
      endforeach()

      # export build info
      # we need to attach the project name to build macros to prevent conflicts to happen in downstream libraries
      install(FILES ${{CMAKE_CURRENT_BINARY_DIR}}/include/build_info_install.h DESTINATION "${{CMAKE_INSTALL_INCLUDEDIR}}")
      install(FILES ${{CMAKE_CURRENT_BINARY_DIR}}/include/build_info.h DESTINATION "${{CMAKE_INSTALL_INCLUDEDIR}}")
    """))

    if use_swig_python:
        content += "\n"
        content += add_indents(inspect.cleandoc(f"""
      # remove leading ;
      string(SUBSTRING "${{PYTHON_INSTALL_FILES}}" 1 -1 PYTHON_INSTALL_FILES)
      string(SUBSTRING "${{PYTHON_INSTALL_RPATHS}}" 1 -1 PYTHON_INSTALL_RPATHS)

      string(SUBSTRING "${{SWIG_TARGETS}}" 1 -1 SWIG_TARGETS)

      # Configure setup.py and copy to output directory
      # we input PYTHON_INSTALL_FILES and PYTHON_INSTALL_RPATHS to install.py
      set(INSTALL_PY_IN ${{CMAKE_CURRENT_SOURCE_DIR}}/scripts/install.py.in)
      set(INSTALL_PY_OUT ${{CMAKE_CURRENT_BINARY_DIR}}/scripts/install.py)
      configure_file(${{INSTALL_PY_IN}} ${{INSTALL_PY_OUT}})

      # add custom target that is available after every swig target is built
      # you can use it by running cmake --build build --target install-python
      add_custom_target(install-python
      DEPENDS ${{SWIG_TARGETS}}
      COMMAND python3 ${{INSTALL_PY_OUT}} install)

      """))

    # if python script processing the options failed
    message = f'message(FATAL_ERROR "${{OPTIONS}} Forcing cmake to stop.")'
    content += "\nelse()\n" + add_indents(inspect.cleandoc(message)) + "\nendif()"
    with open(os.path.join(cmake_root, "CMakeLists.txt"), 'w') as f:
        f.write(content)

def create_cmakelists(tree):
    def create_cmakelists_helper(tree, rpath):
        for folder in tree.keys():
            curr_rpath = os.path.join(rpath, folder)
            # directory with subdiectories
            if(tree[folder]):
                with open(os.path.join(cmake_root, curr_rpath, "CMakeLists.txt"), 'w') as f:
                    f.write(header_content() + inspect.cleandoc(caller_content(curr_rpath, tree[folder].keys())))
                create_cmakelists_helper(tree[folder], curr_rpath)
            # directory with source and header files
            else:
                add_to_build_info(curr_rpath, True)
                add_to_build_info(curr_rpath, False)
                with open(os.path.join(cmake_root, curr_rpath, "CMakeLists.txt"), 'w') as f:
                    content = init_content(curr_rpath) + add_lib_content(curr_rpath)
                    if os.path.exists(os.path.join(cmake_root, curr_rpath, "apps")):
                        content += add_exe_content(curr_rpath)
                    if use_googletest:
                        content += f"include_directories(${{GTEST_INCLUDE_DIRS}})"
                        content += "\n\n"
                    if use_qt:
                        content += qt.add_qt_lib_content(curr_rpath)
                    content += link_contents(curr_rpath)
                    if use_swig_python:
                        content += add_swig_content(curr_rpath)
                    f.write(content)
    
    create_cmakelists_helper(tree, "")

if __name__ == "__main__":
    if args["clean"]:
        clean()
    else:
        print("Generating CMakeLists.txt files ...")
        lib_dirs = get_lib_dirs()

        tree = buildTree(lib_dirs)

        create_top_cmakelists()

        create_cmakelists(tree)

        print("Generation has been completed.")


