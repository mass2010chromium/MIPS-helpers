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
def buildStackFrames(file_lines, filename, debug):
    functions = {} # Key: function name, value: the function. TODO: Possible inlining?
    i = 0
    fline = 1
    while (i < len(file_lines)):
        line = file_lines[i]
        line = line.strip()
        if line.startswith(("#include", "#INCLUDE")):
            include_match = re.match("#(include|INCLUDE)\s+([^\s#]+)", line)
            if include_match:
                included_file_name = include_match[2]
                if debug:
                    print("{}:{}: [DEBUG] #include {}".format(filename, fline, included_file_name))
                fileLines = []
                with open(included_file_name, 'r') as inputFile:
                    line = inputFile.readline()
                    while (line):
                        fileLines.append(line)
                        line = inputFile.readline()
                if included_file_name.endswith(".fs"):
                    fileLines = buildStackFrames(fileLines, included_file_name, debug)
                if fileLines:
                    file_lines[i:i+1] = fileLines
                    i += len(fileLines) - 1
                else:
                    print("{}:{}: Failed to parse included file {}".format(filename, fline, included_file_name))
                    return
                
            else:
                print(fline, ": Syntax error: Malformed #include statement")
                return
        elif line.startswith(("@FUNCTION", "@function")):
            func_start = i
            fline_func_start = fline
            fname_match = re.search('\s+name\s*=\s*[a-zA-Z][^\s#]*', line)
            function_name = -1
            if (fname_match):
                function_name = fname_match.group(0).split("=", 1)[1].strip()
                # print(function_name)
            else:
                print("{}:{}: Syntax error: Expected function name after @FUNCTION declaration, declare name=<fname>".format(filename, fline))
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
                if debug:
                    print("{}:{}: [DEBUG] Interrupt handler found".format(filename, fline))
                interrupt_handler = True
                space = interrupt_handler_match.group(0).split("=", 1)[1].strip()
                
                if space == "auto":
                    ih_space = -1
                else:
                    try:
                        if int(space) % 4:
                            print("{}:{}: Syntax error: Stack allocations (for IH space) must be in multiples of 4, support for byte allocations may be added later".format(filename, fline))
                            return
                    except:
                        print('{}:{}: Syntax error: Stack allocation size (for IH space) must be an integer or "auto", found {}'.format(filename, fline, size))
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
            fline += 1
            line = file_lines[i]
            function_head = -1
            while (not line.strip().startswith(("!FUNCTION", "!function"))):
                interpret = line.strip()
                if interpret.startswith(("#include", "#INCLUDE")):
                    print("{}:{}: Syntax error: #include symbol found inside a function block".format(filename, fline))
                    return
                if interpret.startswith(".stacksave "):
                    if (function_head == -1):
                        print("{}:{}: Syntax error: .stacksave symbol found before function_head".format(filename, fline))
                        return
                    useStack = True
                    stack_vars = re.findall('[^\s]+', line)[1:]
                    for x in stack_vars:
                        if not x.startswith("$"):
                            print("{}:{}: Syntax error: .stacksave requires a list of registers to save but found {}".format(filename, fline, x))
                            return
                        stack_varnames.append(x)
                        stack[x] = stackSize
                        stackSize += 4
                        stack_inserts.append(x)
                elif interpret.startswith(".stackalloc"):
                    if (function_head == -1):
                        print("{}:{}: Syntax error: .stackalloc symbol found before function_head".format(filename, fline))
                        return
                    useStack = True
                    stack_vars = re.findall('[^\s]+', line)[1:]
                    # stack_vars = re.findall('\s+[(]\d+[)][a-zA-Z][^\s#]*', line)
                    for x in stack_vars:
                        split_var = re.match("([(]\d+[)])([a-zA-Z_][^\s#]*)", x.strip())
                        if split_var:
                            size = split_var[1][1:-1]
                            name = split_var[2]
                            if name in stack:
                                print("{}:{}: Syntax error: Duplicate stack variable, name {}".format(filename, fline, name))
                            try:
                                if int(size) % 4:
                                    print("{}:{}: Syntax error: Stack allocations must be in multiples of 4, support for byte allocations may be added later".format(filename, fline))
                                    return
                            except:
                                print("{}:{}: Syntax error: Stack allocation size must be an integer, found {}".format(filename, fline, size))
                                return
                            stack[name] = stackSize
                            stackSize += int(size)
                            stack_varnames.append(name)
                        else:
                            print("{}:{}: Syntax error: Bad stack alloc declaration {}, expected [ (bytesize)vname ]".format(filename, fline, x))
                            return
                elif interpret.startswith(".alias "):
                    if (function_head == -1):
                        print("{}:{}: Syntax error: .alias symbol found before function_head".format(filename, fline))
                        return
                    alias_vars = re.findall('[^\s]+', line)[1:]
                    for x in alias_vars:
                        split_var = re.match("([(]\$[^)]+[)])([a-zA-Z_][^\s#]*)", x.strip())
                        if split_var:
                            reg = split_var[1][1:-1]
                            name = split_var[2]
                            aliases.append((name, reg))
                        else:
                            print("{}:{}: Syntax error: Bad alias declaration {}, expected [ (register)vname ]".format(filename, fline, x))
                            return

                elif interpret.startswith(function_name + ":"):
                    if function_head != -1:
                        print("{}:{}: Syntax error: Duplicate function label declaration, first seen at {}".format(filename, fline, function_head))
                        return
                    function_head = i
                i += 1
                fline += 1
                if i == len(file_lines):
                    print("{}:{}: Syntax error: Expected closing !FUNCTION tag for @FUNCTION declaration at {}".format(filename, fline, fline_func_start))
                    return
                line = file_lines[i]

            if function_head == -1:
                print("{}:{}: Syntax error: Did not find function start for @FUNCTION declaration at {}".format(filename, fline, fline_func_start))
                return


            # Replacing all the things, and local aliasing

            local_alias = []
            
            stkptr = "sp"
            k0_warning = 0 # Bit 0: Interrupt handler or not. Bit 1: Seen $k0 or not. Bit 2: Seen lstk/sstk or not.
            if interrupt_handler:
                stkptr = "k0"
                k0_warning = 1
            func_fline = fline_func_start
            for j in range(func_start + 1, i):
                func_fline += 1
                line = file_lines[j]
                interpret = line.strip()
                if interpret.startswith(".stackalloc") or interpret.startswith(".alias ") or interpret.startswith(".stacksave "):
                    continue
                
                if interpret.startswith(".aliaslocal "):
                    alias_vars = re.findall('[^\s]+', line)[1:]
                    for x in alias_vars:
                        split_var = re.match("([(]\$[^)]+[)])([a-zA-Z_][^\s#]*)", x.strip())
                        if split_var:
                            reg = split_var[1][1:-1]
                            name = split_var[2]
                            local_alias.append((name, reg))
                        else:
                            print("{}:{}: Syntax error: Bad aliaslocal declaration {}, expected [ (register)vname ]".format(filename, func_fline, x))
                            return

                    continue
                elif interpret.startswith(".clear"):
                    local_alias = []
                    continue

                la = re.match("[^#]:*\s*la\s+", line)
                if la:
                    # Process special la command!
                    la_inst = re.search("la\s+(\$[^\s,]+),\s+([a-zA-Z_][^\s#()]*)", line)
                    if la_inst:
                        var = la_inst[2]
                        if var in stack:
                            if debug:
                                print("{}:{}: [DEBUG] Found load stack address instruction, loading stack address {}".format(filename, func_fline, var))
                            line = "    addi    {}, ${}, {} # {}\n".format(la_inst[1], stkptr, stack[var], line.strip())


                lstk = re.match("[^#]:*\s*lstk\s+", line)
                if lstk:
                    if not useStack:
                        print("{}:{}: Syntax error: lstk (Load Stack) pseudoinstruction used without a stack initialization".format(filename, func_fline))
                        return
                    lstk_inst = re.search("lstk\s+(\$[^\s,]+),\s+(\d+[(][^\s#()]*[)]|[^\s#()]*)", line)
                    if not lstk_inst:
                        print("{}:{}: Syntax error: lstk (Load Stack) pseudoinstruction is malformed".format(filename, func_fline))
                        return
                    var = lstk_inst[2]
                    if var in stack:
                        line = "    lw      {}, {}(${}) # {}\n".format(lstk_inst[1], stack[var], stkptr, line.strip())
                    else:
                        lstk_offset = re.search("(\d+)[(]([^\s#()]*)[)]", var)
                        if lstk_offset:
                            extra_offset = int(lstk_offset[1])
                            line = "    lw      {}, {}(${}) # {}\n".format(lstk_inst[1], stack[lstk_offset[2]] + extra_offset, stkptr, line.strip())
                        else:
                            print("{}:{}: Syntax error: lstk (Load Stack): could not find stack variable by name {}".format(filename, func_fline, var))
                            return
                    k0_warning |= 4

                sstk = re.match("[^#]:*\s*sstk\s+", line)
                if sstk:
                    if not useStack:
                        print("{}:{}: Syntax error: sstk (Store Stack) pseudoinstruction used without a stack initialization".format(filename, func_fline))
                        return
                    sstk_inst = re.search("sstk\s+(\$[^\s,]+),\s+([^\s#]*)", line)
                    if not sstk_inst:
                        print("{}:{}: Syntax error: sstk (Store Stack) pseudoinstruction is malformed".format(filename, func_fline))
                        return
                    var = sstk_inst[2]
                    if var in stack:
                        line = "    sw      {}, {}(${}) # {}\n".format(sstk_inst[1], stack[var], stkptr, line.strip())
                    else:
                        sstk_offset = re.search("(\d+)[(]([^\s#()]*)[)]", var)
                        if sstk_offset:
                            line = "    sw      {}, {}(${}) # {}\n".format(sstk_inst[1], stack[sstk_offset[2]] + extra_offset, stkptr, line.strip())
                        else:
                            print("{}:{}: Syntax error: sstk (Store Stack): could not find stack variable by name {}".format(filename, func_fline, var))
                            return
                    k0_warning |= 4

                for alias in local_alias:
                    line = re.sub("\${}(?=[\s#,)]|$)".format(alias[0]), alias[1], line)
                for alias in aliases:
                    line = re.sub("\${}(?=[\s#,)]|$)".format(alias[0]), alias[1], line)

                if re.search("(\$k0(?=[\s#,)]|$))", line.split("#")[0]):
                    k0_warning |= 2

                code_lines.append(line)
                
            if k0_warning == 7:
                print("{}:{}: Warning: lstk or sstk (Load/Store Stack) command detected in interrupt handler code that uses $k0".format(filename, fline))

            if (re.match("(?:[^#]*:)?\s*jr\s+", code_lines[-1])):
                print(fline, ": Warning: code tagged with @FUNCTION tag ends with a jump instruction")

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
                    if k0_warning & 2:
                        cleanup_code.append("    la      $k0, {}\n".format(ih_address_name))
                    else:
                        # Don't reload $k0 if we haven't even seen it!
                        if debug:
                            print("{}:{}: [DEBUG] Not loading address into $k0, because it wasn't touched in the code.".format(filename, fline))

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
                    elif ih_space < stackSize:
                        print("{}:{}: Warning: Manually allocated instruction handler space is not large enough to fit all allocated local variables".format(filename, fline))
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
                print("{}:{}: Warning: code tagged with @FUNCTION tag does not contain an @RETURN tag".format(filename, fline_func_start))
            
            functions[function_name] = code_lines
            original_length = i - func_start + 1
            len_diff = original_length - len(code_lines)

            file_lines[func_start:i + 1] = code_lines
            i -= len_diff
        i += 1
        fline += 1
    return file_lines

if __name__ == "__main__":
    inputFName = -1
    outputFName = -1
    debug = False
    i = 0
    while i < len(sys.argv):
        arg = sys.argv[i]
        i += 1
        if arg == __file__:
            continue
        if arg == '--debug':
            debug = True
            continue
        if arg == '-o':
            if i == len(sys.argv):
                print("Missing command line argument for output file name, ignoring '-o'")
            else:
                arg = sys.argv[i]
                i += 1
                outputFName = arg
                print("    -o {}".format(outputFName))
            continue
        if inputFName == -1:
            inputFName = arg
            continue
        print("ignoring extra argument " + arg);

    if inputFName == -1:
        inputFName = input("Input file: ")
    print("Reading file:", inputFName)

    with open(inputFName, 'r') as inputFile:
        fileLines = []
        line = inputFile.readline()
        while (line):
            fileLines.append(line)
            line = inputFile.readline()

    outputFileLines = buildStackFrames(fileLines, inputFName, debug)
    if outputFileLines:
        if outputFName == -1:
            if inputFName.endswith(".fs"):
                outputFName = re.sub(".fs$", ".s", inputFName)
            else:
                outputFName = input("Enter name for output file: ")

        with open(outputFName, 'w') as outputFile:
            outputFile.write(''.join(outputFileLines))
