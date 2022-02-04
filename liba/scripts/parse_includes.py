import re
import os

def get_uncommented_lines(string):
    # remove all occurrences streamed comments (/*COMMENT */) from string
    string = re.sub(re.compile("/\*.*?\*/",re.DOTALL ) ,"" ,string)
    # remove all occurrence single-line comments (//COMMENT\n ) from string
    string = re.sub(re.compile("//.*?\n" ) ,"" ,string)
    return [line for line in string.split("\n") if not re.match(r'^\s*$', line)]

def find_includes(file_path):
    with open(file_path) as f:
        regex = "^\\s*#\\s*include\\s+[<\"][^>\"]*[>\"]\\s*"
        text = "\n".join(f.readlines())
        lines = get_uncommented_lines(text)
        includes = []
        for line in lines:
            match = re.match(regex, line)
            if match:
                include = match.group(0)
                if re.match('.*".*".*', include):
                    includes.append('"' + include.split('"')[1] + '"')
                elif re.match('.*<.*>.*', include):
                    includes.append(include[include.index('<'):include.index('>') + 1])
        return includes

if __name__ == "__main__":
    import argparse

    argparser = argparse.ArgumentParser()
    argparser.add_argument('--path', type=str, required=False, help="path to file to parse")
    args = vars(argparser.parse_args())
    file_path = args["path"]
    
    includes = find_includes(file_path)
    print(includes)


