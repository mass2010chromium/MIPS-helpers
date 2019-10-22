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
            stack_inserts = []
            stackSize = 4
            
            interrupt_handler = False
            ih_address_name = -1
            ih_space = -1
            interrupt_handler_match = re.search("\s+interrupt_space\s*=\s*((\d+)|(auto))", line)
            if interrupt_handler_match:
                print(i, ": [DEBUG] Interrupt handler found")
                interrupt_handler = True
                space = interrupt_handler_match.group(0).split("=", 1)[1].strip()
                
                if space == "auto":
                    ih_space = -1
                else:
                    try:
                        if int(space) % 4:
                            print(i, ": Syntax error: Stack allocations (for IH space) must be in multiples of 4, support for byte allocations may be added later")
                            return
                    except:
                        print(i, ': Syntax error: Stack allocation size (for IH space) must be an integer or "auto", found ', size)
                        return
                    ih_space = int(space)
                
                ih_address_name = "EMIPS_{}_SPACE".format(function_name)
                
                useStack = True
                stack = {"$at": 0}
                stack_varnames = ["$at"]
                stackSize = 4
                
            
            aliases = []
            code_lines = []
            i += 1
            line = file[i]
            function_head = -1
            while (not line.strip().startswith(("!FUNCTION", "!function"))):
                interpret = line.strip()
                if interpret.startswith(".stacksave "):
                    if (function_head == -1):
                        print(i, ": Syntax error: .stacksave symbol found before function_head")
                        return
                    useStack = True
                    stack_vars = re.findall('[^\s]+', line)[1:]
                    for x in stack_vars:
                        if not x.startswith("$"):
                            print(i, ": Syntax error: .stacksave requires a list of registers to save but found ", x)
                            return
                        stack_varnames.append(x)
                        stack[x] = stackSize
                        stackSize += 4
                        stack_inserts.append(x)
                elif interpret.startswith(".stackalloc"):
                    if (function_head == -1):
                        print(i, ": Syntax error: .stackalloc symbol found before function_head")
                        return
                    useStack = True
                    stack_vars = re.findall('[^\s]+', line)[1:]
                    # stack_vars = re.findall('\s+[(]\d+[)][a-zA-Z][^\s#]*', line)
                    for x in stack_vars:
                        split_var = re.match("([(]\d+[)])([a-zA-Z][^\s#]*)", x.strip())
                        if split_var:
                            size = split_var[1][1:-1]
                            name = split_var[2]
                            try:
                                if int(size) % 4:
                                    print(i, ": Syntax error: Stack allocations must be in multiples of 4, support for byte allocations may be added later")
                                    return
                            except:
                                print(i, ": Syntax error: Stack allocation size must be an integer, found ", size)
                                return
                            stack[name] = stackSize
                            stackSize += int(size)
                            stack_varnames.append(name)
                        else:
                            print(i, ": Syntax error: Bad stack alloc declaration ", x, ", expected [ (bytesize)vname ]")
                            return
                elif interpret.startswith(".alias "):
                    if (function_head == -1):
                        print(i, ": Syntax error: .alias symbol found before function_head")
                        return
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


            # Replacing all the things, and local aliasing

            local_alias = []
            
            stkptr = "sp";
            if interrupt_handler:
                stkptr = "k0"
            
            for j in range(func_start + 1, i):
                line = file[j]
                interpret = line.strip()
                if interpret.startswith(".stackalloc") or interpret.startswith(".alias ") or interpret.startswith(".stacksave "):
                    continue
                if interpret.startswith(".aliaslocal "):
                    alias_vars = re.findall('[^\s]+', line)[1:]
                    for x in alias_vars:
                        split_var = re.match("([(]\$[^)]+[)])([a-zA-Z][^\s#]*)", x.strip())
                        if split_var:
                            reg = split_var[1][1:-1]
                            name = split_var[2]
                            local_alias.append((name, reg))
                        else:
                            print(j, ": Syntax error: Bad aliaslocal declaration ", x, ", expected [ (register)vname ]")
                            return

                    continue
                if interpret.startswith(".clear"):
                    local_alias = []
                    continue;
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
                        line = "    lw      {}, {}(${})\n".format(lstk_inst[1], stack[var], stkptr)
                    else:
                        print(j, ": Syntax error: lstk (Load Stack): could not find stack variable by name", var)
                        return

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
                        line = "    sw      {}, {}(${})\n".format(sstk_inst[1], stack[var], stkptr)
                    else:
                        print(j, ": Syntax error: sstk (Store Stack): could not find stack variable by name", var)
                        return

                for alias in local_alias:
                    line = re.sub("\${}(?=[\s#,)]|$)".format(alias[0]), alias[1], line);
                for alias in aliases:
                    line = re.sub("\${}(?=[\s#,)]|$)".format(alias[0]), alias[1], line);

                code_lines.append(line)
            if (re.match("(?:[^#]*:)?\s*jr\s+", code_lines[-1])):
                print(i, ": Warning: code tagged with @FUNCTION tag ends with a jump instruction")

            head_idx = function_head - func_start
            if len(aliases) > 0:
                code_lines.insert(head_idx, "    ## End aliases  -- emips.py\n\n")
                code_lines.insert(head_idx, "    ##\n")

                for x in aliases:
                    code_lines.insert(head_idx, "    ##    {} = {}\n".format(x[1], x[0]))

                code_lines.insert(head_idx, "    ##\n")
                code_lines.insert(head_idx, "    ## Aliases      -- emips.py\n")

            cleanup_code = []

            if useStack:
                code_lines.insert(head_idx, "    ## End stack setup  -- emips.py\n\n")
                code_lines.insert(head_idx, "    ##\n")
                
                if interrupt_handler:
                    code_lines.insert(head_idx, "    sw      $k1, 0($k0)\n")

                cleanup_code.append("\n    ## Stack teardown       -- emips.py\n")
                cleanup_code.append("    ##\n")
                
                if interrupt_handler:
                    cleanup_code.append("    la      $k0, {}\n".format(ih_address_name))

                for x in stack_inserts:
                    code_lines.insert(head_idx, "    sw      {}, {}(${})\n".format(x, str(stack[x]), stkptr))
                    cleanup_code.append("    lw      {}, {}(${})\n".format(x, str(stack[x]), stkptr))

                if not interrupt_handler:
                    code_lines.insert(head_idx, "    sw      $ra, 0($sp)\n")
                    code_lines.insert(head_idx, "    addi    $sp, $sp, -{}\n".format(str(stackSize)))

                for x in stack_varnames:
                    code_lines.insert(head_idx, "    ## Index {}\tVariable {}\n".format(str(stack[x]), x))
                
                if interrupt_handler:
                    code_lines.insert(head_idx, "    la      $k0, {}\n".format(ih_address_name))
                    code_lines.insert(head_idx, ".set at\n")
                    code_lines.insert(head_idx, "    move    $k1, $at\n")
                    code_lines.insert(head_idx, ".set noat\n")

                code_lines.insert(head_idx, "    ##\n")
                code_lines.insert(head_idx, "    ## Stack setup      -- emips.py\n")
                
                if interrupt_handler:
                    if ih_space == -1:
                        ih_space = stackSize
                    code_lines.insert(0, "{}:  .space {}\n".format(ih_address_name, ih_space))
                    code_lines.insert(0, ".kdata\n")


                if interrupt_handler:
                    cleanup_code.append(".set noat\n")
                    cleanup_code.append("    lw      $at, 0($k0)\n")
                    cleanup_code.append(".set at\n")
                else:
                    cleanup_code.append("    lw      $ra, 0($sp)\n")
                    cleanup_code.append("    addi    $sp, $sp, {}\n".format(str(stackSize)))
                
                cleanup_code.append("    ##\n")
                cleanup_code.append("    ## End stack teardown   -- emips.py\n\n")

            if interrupt_handler:
                cleanup_code.append("    eret\n")
            else:
                cleanup_code.append("    jr      $ra\n")

            hasReturn = False
            for k in range(len(code_lines) - 1, -1, -1):
                if code_lines[k].strip().lower().startswith("@return"):
                    code_lines[k:k+1] = cleanup_code
                    hasReturn = True
            
            if not hasReturn:
                print(func_start, ": Warning: code tagged with @FUNCTION tag does not contain an @RETURN tag")
            
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
