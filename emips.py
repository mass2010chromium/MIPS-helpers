import re
import sys

class Function:
    def __init__(self, name, codeLines, attributes=[]):
        self._name = name
        self._codeLines = codeLines
        self._attributes = attributes

'''
Pass me a list of lines in a file! 
For now not compatible with inliner.py.
'''
def buildStackFrames(file):
    functions = {} # Key: function name, value: the function
    i = 0
    while (i < len(file)):
        line = file[i]
        line = line.strip();
        if line.startswith(("@FUNCTION", "@function")):
            func_start = i;
            fname_match = re.search('\s+name\s*=\s*[a-zA-Z][^\s#]*', line)
            function_name = -1
            if (fname_match):
                function_name = fname_match.group(0).split("=", 1)[1].strip()
                # print(function_name)
            else:
                print(i, ": Syntax error: Expected function name after @FUNCTION declaration, declare name=<fname>")
                return
            useStack = False
            stack = {"ra": 0} # Key: localName, value: offset
            stack_varnames = ["ra"]
            aliases = []
            stackSize = 4
            code_lines = []
            i += 1
            line = file[i]
            function_head = -1
            while (not line.strip().startswith(("!FUNCTION", "!function"))):
                interpret = line.strip()
                if interpret.startswith(".stackalloc"):
                    useStack = True
                    stack_vars = re.findall('[^\s]+', line)[1:]
                    # stack_vars = re.findall('\s+[(]\d+[)][a-zA-Z][^\s#]*', line)
                    for x in stack_vars:
                        split_var = re.match("([(]\d+[)])([a-zA-Z][^\s#]*)", x.strip())
                        if split_var:
                            size = split_var[1][1:-1]
                            name = split_var[2]
                            stack[name] = size
                            try:
                                if int(size) % 4:
                                    print(i, ": Syntax error: Stack allocations must be in multiples of 4, support may be added later")
                                    return
                            except:
                                print(i, ": Syntax error: Stack allocation size must be an integer, found ", size)
                                return
                            stackSize += int(size)
                            stack_varnames.append(name)
                        else:
                            print(i, ": Syntax error: Bad stack alloc declaration ", x, ", expected [ (bytesize)vname ]")
                            return
                elif interpret.startswith(".alias"):
                    alias_vars = re.findall('[^\s]+', line)[1:]
                    for x in alias_vars:
                        split_var = re.match("([(]\$[^)]+[)])([a-zA-Z][^\s#]*)", x.strip())
                        if split_var:
                            reg = split_var[1][1:-1]
                            name = split_var[2]
                            aliases.append((name, reg))
                        else:
                            print(i, ": Syntax error: Bad alias declaration ", x, ", expected [ (register)vname ]")
                            return
                    
                elif interpret.startswith(function_name + ":"):
                    if function_head != -1:
                        print(i, ": Syntax error: Duplicate function label declaration, first seen at ", str(function_head))
                        return
                    function_head = i
                i += 1
                if i == len(file):
                    print(i, ": Syntax error: Expected closing !FUNCTION tag for @FUNCTION declaration at ", func_start)
                    return
                line = file[i]
                
            if function_head == -1:
                print(i, ": Syntax error: Did not find function start for @FUNCTION declaration at ", func_start)
                return
            
            
            # Replacing all the things
            
            for j in range(func_start + 1, i):
                line = file[j]
                interpret = line.strip()
                if interpret.startswith(".stackalloc") or interpret.startswith(".alias"):
                    continue
                lstk = re.match("[^#]:*\s*lstk\s+", line)
                if lstk:
                    if not useStack:
                        print(j, ": Syntax error: lstk (Load Stack) pseudoinstruction used without a stack initialization")
                        return
                    lstk_inst = re.search("lstk\s+(\$[^\s,]+),\s+([^\s#]*)", line)
                    if not lstk_inst:
                        print(j, ": Syntax error: lstk (Load Stack) pseudoinstruction is malformed")
                        return
                    var = lstk_inst[2]
                    if var in stack:
                        code_lines.append("\tlw\t{}, {}($sp)\n".format(lstk_inst[1], stack[var]))
                    else:
                        print(j, ": Syntax error: lstk (Load Stack): could not find stack variable by name", var)
                        return
                    continue;
                
                sstk = re.match("[^#]:*\s*sstk\s+", line)
                if sstk:
                    if not useStack:
                        print(j, ": Syntax error: sstk (Store Stack) pseudoinstruction used without a stack initialization")
                        return
                    sstk_inst = re.search("sstk\s+(\$[^\s,]+),\s+([^\s#]*)", line)
                    if not sstk_inst:
                        print(j, ": Syntax error: sstk (Store Stack) pseudoinstruction is malformed")
                        return
                    var = sstk_inst[2]
                    if var in stack:
                        code_lines.append("\tsw\t{}, {}($sp)\n".format(sstk_inst[1], stack[var]))
                    else:
                        print(j, ": Syntax error: sstk (Store Stack): could not find stack variable by name", var)
                        return
                    continue;
                    
                for alias in aliases:
                    line = re.sub("\${}(?=[\s#,)]|$)".format(alias[0]), alias[1], line);
                
                code_lines.append(line)
            if (re.match("(?:[^#]*:)?\s*jr\s+", code_lines[-1])):
                print(i, ": Warning: code tagged with @FUNCTION tag ends with a jump instruction")
            
            head_idx = function_head - func_start
            if len(aliases) > 0:
                code_lines.insert(head_idx, "\t## End aliases\t-- stackFrameHelper.py\n\n")
                code_lines.insert(head_idx, "\t##\n")
                
                for x in aliases:
                    code_lines.insert(head_idx, "\t##\t{} = {}\n".format(x[1], x[0]))
                
                code_lines.insert(head_idx, "\t##\n")
                code_lines.insert(head_idx, "\t## Aliases\t-- stackFrameHelper.py\n")
            
            if useStack:
                code_lines.insert(head_idx, "\t## End stack setup\t-- stackFrameHelper.py\n\n")
                code_lines.insert(head_idx, "\tsw\t$ra, 0($sp)\n")
                code_lines.insert(head_idx, "\taddi\t$sp, $sp, -{}\n".format(str(stackSize)))
                
                for x in stack_varnames:
                    code_lines.insert(head_idx, "\t# Index {}\tVariable {}\n".format(str(stack[x]), x))
                    
                code_lines.insert(head_idx, "\t## Stack setup\t-- stackFrameHelper.py\n")
            
                code_lines.append("\n\t## Stack teardown\t-- stackFrameHelper.py\n")
                code_lines.append("\tlw\t$ra, 0($sp)\n")
                code_lines.append("\taddi\t$sp, $sp, {}\n".format(str(stackSize)))
                code_lines.append("\t## End stack teardown\t-- stackFrameHelper.py\n\n")
            
            
            code_lines.append("\tjr\t$ra\n")
            functions[function_name] = code_lines
            original_length = i - func_start + 1
            len_diff = original_length - len(code_lines)
            
            file[func_start:i + 1] = code_lines;
            i -= len_diff
        i += 1
    return file

if __name__ == "__main__":
    inputFName = -1
    no_debug = False

    for arg in sys.argv:
        if arg == __file__:
            continue;
        if arg == '--no-debug':
            no_debug = True
            continue;
        inputFName = arg;

    if inputFName == -1:
        inputFName = input("Input file: ")
    print("Reading file:", inputFName)

    inputFile = open(inputFName, 'r')
    fileLines = []
    line = inputFile.readline()
    while (line):
        fileLines.append(line)
        line = inputFile.readline()
    
    outputFileLines = buildStackFrames(fileLines)
    if outputFileLines:
        outputFName = re.sub(".fs$", ".s", inputFName);
        if inputFName.endswith(".s"):
            outputFName = input("Enter name for output file: ")
        
        outputFile = open(outputFName, 'w')
        outputFile.write(''.join(outputFileLines))