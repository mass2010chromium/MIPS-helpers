import re
import sys

class Node:
    def __init__(self, value, level, left=None, right=None, extras=None):
        self.val = value
        self.level = level
        self.extras = extras
        self.left = left
        self.right = right
        if left:
            left.parent = self
        if right:
            right.parent = self
        self.parent = None
    
    def is_leaf(self):
        return self.left == None and self.right == None

class Tokenizer:
    def __init__(self, text):
        self.text = text
        self.next_type = None
        self.next = self.get_next_token()

    def advance(self):
        self.next = self.get_next_token()

    def get_next_token(self):
        self.text = self.text.strip()
        text = self.text
        operator_match = re.match(">::|>:|>|\*::|\*:|\*;;|\*;|[()+*/%&|^~-]|~\||<<|>>>|>>", text)
        if operator_match:
            self.next_type = "operator"
            self.text = self.text[len(operator_match[0]):]
            return operator_match[0]
        register_match = re.match("\$[^\s#()+*/%&|^~-]+", text)
        if register_match:
            self.next_type = "register"
            self.text = self.text[len(register_match[0]):]
            return register_match[0]
        hex_number_match = re.match("0x[\da-fA-F]+", text)
        if hex_number_match:
            self.next_type = "number"
            self.text = self.text[len(hex_number_match[0]):]
            return int(hex_number_match[0], 16)
        binary_number_match = re.match("0b[10]+", text)
        if binary_number_match:
            self.next_type = "number"
            self.text = self.text[len(binary_number_match[0]):]
            return int(binary_number_match[0], 2)
        number_match = re.match("\d+", text)
        if number_match:
            self.text = self.text[len(number_match[0]):]
            self.next_type = "number"
            return int(number_match[0])
        if text.startswith("#"):
            self.next_type = "comment"
            return "#"
        self.next_type = "EOL"
        return None

"""

expr_store:
    > number ( expr )           ((store word))
    > expr
    >: number ( expr )          ((store halfword))
    >: expr
    >:: number ( expr )         ((store byte))
    >:: expr
    expr

expr:
    expr_13

expr_13:
    expr_12 | expr_13
    expr_12 ~| expr_13
    expr_12

expr_12:
    expr_11 ^ expr_12
    expr_11

expr_11:
    expr_7 & expr_11
    expr_7

expr_7:
    expr_6 << expr_7
    expr_6 >> expr_7
    expr_6 >>> expr_7
    expr_6

expr_6:
    expr_5 + expr_6
    expr_5 - expr_6
    expr_5

expr_5:
    expr_3 * expr_5
    expr_3 / expr_5
    expr_3 % expr_5
    expr_3

expr_3:
    ~expr_3
    -expr_3
    * expr_3    ((dereference word))
    *; expr_3   ((dereference halfword, signed))
    *;; expr_3  ((dereference byte, signed))
    *: expr_3   ((dereference halfword, unsigned))
    *:: expr_3  ((dereference byte, unsigned))

    expr_base

expr_base:
    number
    register
    ( expr )
"""

def expr_store(tokenizer):
    op_token = tokenizer.next
    if op_token in [">", ">:", ">::"]:
        tokenizer.advance()
        if tokenizer.next_type == "number":
            number = tokenizer.next
            tokenizer.advance()
            next_token = tokenizer.next
            if next_token != "(":
                print("FAIL1")
                return None
            tokenizer.advance()
            node = expr(tokenizer)
            next_token = tokenizer.next
            tokenizer.advance()
            if next_token != ")":
                print("FAIL2")
                return None
            return Node("unary" + op_token, "expr_store", right=node, extras=number)
        else:
            node = expr(tokenizer)
            return Node("unary" + op_token, "expr_store", right=node, extras=0)
    return expr(tokenizer)

def expr(tokenizer):
    # print("expr " + tokenizer.text)
    node = expr_13(tokenizer)
    return node

def tree_rotate(node):
    while node.left.level == node.left.right.level:
        tmp = node.left
        node.left = node.left.right
        tmp.right = node.left.left
        node.left.left = tmp
        node = tmp

def expr_13(tokenizer):
    # print("expr13 " + tokenizer.text)
    node1 = expr_12(tokenizer)
    next_token = tokenizer.next
    if next_token in ["|", "~|"]:
        tokenizer.advance()
        node2 = expr_13(tokenizer)
        if node2:
            if node2.level == "expr_13":
                retval = node2
                # HACK tree rotations are bad.
                node2.left = Node(next_token, "expr_13", left=node1, right=node2.left)
                tree_rotate(node2)
                return retval
            return Node(next_token, "expr_13", left=node1, right=node2)
        else:
            return None
    return node1

def expr_12(tokenizer):
    # print("expr12 " + tokenizer.text)
    node1 = expr_11(tokenizer)
    next_token = tokenizer.next
    if next_token == "^":
        tokenizer.advance()
        node2 = expr_12(tokenizer)
        if node2:
            if node2.level == "expr_12":
                retval = node2
                # HACK tree rotations are bad.
                node2.left = Node(next_token, "expr_12", left=node1, right=node2.left)
                tree_rotate(node2)
                return retval
            return Node(next_token, "expr_12", left=node1, right=node2)
        else:
            return None
    return node1

def expr_11(tokenizer):
    # print("expr11 " + tokenizer.text)
    node1 = expr_7(tokenizer)
    next_token = tokenizer.next
    if next_token == "&":
        tokenizer.advance()
        node2 = expr_11(tokenizer)
        if node2:
            if node2.level == "expr_11":
                retval = node2
                # HACK tree rotations are bad.
                node2.left = Node(next_token, "expr_11", left=node1, right=node2.left)
                tree_rotate(node2)
                return retval
            return Node(next_token, "expr_11", left=node1, right=node2)
        else:
            return None
    return node1

def expr_7(tokenizer):
    # print("expr7 " + tokenizer.text)
    node1 = expr_6(tokenizer)
    next_token = tokenizer.next
    if next_token in ["<<", ">>", ">>>"]:
        tokenizer.advance()
        node2 = expr_7(tokenizer)
        if node2:
            if node2.level == "expr_7":
                retval = node2
                # HACK tree rotations are bad.
                node2.left = Node(next_token, "expr_7", left=node1, right=node2.left)
                tree_rotate(node2)
                return retval
            return Node(next_token, "expr_7", left=node1, right=node2)
        else:
            return None
    return node1

def expr_6(tokenizer):
    # print("expr6 " + tokenizer.text)
    node1 = expr_5(tokenizer)
    next_token = tokenizer.next
    if next_token in ["+", "-"]:
        tokenizer.advance()
        node2 = expr_6(tokenizer)
        if node2:
            if node2.level == "expr_6":
                retval = node2
                # HACK tree rotations are bad.
                node2.left = Node(next_token, "expr_6", left=node1, right=node2.left)
                tree_rotate(node2)
                return retval
            return Node(next_token, "expr_6", left=node1, right=node2)
        else:
            return None
    return node1

def expr_5(tokenizer):
    # print("expr5 " + tokenizer.text)
    node1 = expr_3(tokenizer)
    next_token = tokenizer.next
    if next_token in ["*", "%", "/"]:
        tokenizer.advance()
        node2 = expr_5(tokenizer)
        if node2:
            if node2.level == "expr_5":
                retval = node2
                # HACK tree rotations are bad.
                node2.left = Node(next_token, "expr_5", left=node1, right=node2.left)
                tree_rotate(node2)
                return retval
            return Node(next_token, "expr_5", left=node1, right=node2)
        else:
            return None
    return node1

def expr_3(tokenizer):
    # print("expr3 " + tokenizer.text)
    op_token = tokenizer.next
    if op_token in ["~", "-", "*", "*:", "*::", "*;", "*;;"]:
        tokenizer.advance()
        node = expr_3(tokenizer)
        ret = Node("unary" + op_token, "expr_3", right=node)
        return ret
    return expr_base(tokenizer)

def expr_base(tokenizer):
    # print("expr_base " + tokenizer.text)
    next_token = tokenizer.next
    next_type = tokenizer.next_type
    tokenizer.advance()
    if next_token == "(":
        node = expr(tokenizer)
        node.level = "expr_base" # TODO maybe change?
        next_token = tokenizer.next
        tokenizer.advance()
        if next_token != ")":
            return None
        return node
    elif next_type == "register" or next_type == "number":
        return Node((next_token, next_type), "expr_base")
    else:
        return None

def load_imm(target_reg, imm):
    return "li      {}, {}\n".format(target_reg, imm)

immediate_symmetric = {"+", "&", "|", "~|", "^"}
immediate_any = {"+", "-", "&", "|", "~|","^", ">>", "<<", ">>>"}
immediate_logical = {"&", "|", "~|","^"}
immediate_right = {"-", "<<", ">>", ">>>"}
immediate_map = {"+"  : "addi    ",
                 "&"  : "andi    ",
                 "|"  : "ori     ",
                 "~|" : "nori    ",
                 "^"  : "xori    ",
                 "<<" : "sll     ",
                 ">>" : "sra     ",
                 ">>>": "srl     "}
unary_imm = {"unary-", "unary~"}
unary_store = {"unary>", "unary>:", "unary>::"}
unary_map = {"unary-" : "sub     {}, $0, {}",
             "unary~" : "nor     {}, $0, {}",
             "unary*" : "lw      {}, 0({})",
            "unary*:" : "lh      {}, 0({})",
           "unary*::" : "lb      {}, 0({})",
            "unary*;" : "lhu     {}, 0({})",
           "unary*;;" : "lbu     {}, 0({})",
             "unary>" : "sw      {}, {}({})",
            "unary>:" : "sh      {}, {}({})",
           "unary>::" : "sb      {}, {}({})"}
inst_map = {     "+"  : "add     ",
                 "-"  : "sub     ",
                 "&"  : "and     ",
                 "|"  : "or      ",
                 "^"  : "xor     ",
                 "<<" : "sllv    ",
                 ">>" : "srav    ",
                 ">>>": "srlv    "}
pseudoinst_group1 = {"*":"*", "/":"//", "%":"%"}
pseudoinst_group1_map = {
                 "*"  : ("mult    ", "mflo    "),
                 "/"  : ("div     ", "mflo    "),
                 "%"  : ("div     ", "mfhi    ")}

def get_next_unused_register(used_registers):
    return "$et{}".format(len(used_registers))

def help_add(regval, used_set):
    if "et" in regval:
        used_set.add(regval)

def traverse_getlines(target_reg, tree, used_set, used_registers=[]):
    line_list = []
    if tree.is_leaf():
        if tree.val[1] == "register":
            return line_list, tree.val[0], None
        else: # if tree.val[1] == "number"
            num = tree.val[0]
            if num < 65536:
                return line_list, None, tree.val[0]
            else:
                line_list.append(load_imm(target_reg, num))
                return line_list, target_reg, None
    else:
        op = tree.val
        RIGHT_REG = target_reg # We never need a special value
        LEFT_REG = None
        # print("Go Right: ", RIGHT_REG, " = ", hex(id(tree)), "->", hex(id(tree.right)))
        right_lines, rightRegister, rightIMM = traverse_getlines(RIGHT_REG, tree.right, used_set, used_registers)
        # print("Gone Right: ", hex(id(tree)))
        left_lines = []
        leftRegister = ""
        if tree.left:
            if (rightRegister != RIGHT_REG) or (rightIMM and (op in immediate_symmetric or op in unary_map)):
                LEFT_REG = target_reg
                new_used = used_registers
            else:
                LEFT_REG = get_next_unused_register(used_registers)
                new_used = used_registers + [target_reg]
            # print("Go left: ", LEFT_REG, " = ", hex(id(tree)), "->", hex(id(tree.left)), ", ", new_used)
            left_lines, leftRegister, leftIMM = traverse_getlines(LEFT_REG, tree.left, used_set, new_used)
            # print("Gone left: ", hex(id(tree)))
        
        if tree.left and leftIMM:
            line_list.append(load_imm(LEFT_REG, leftIMM))
            leftRegister = LEFT_REG
        if rightIMM:
            if tree.left and leftRegister == rightRegister:
                RIGHT_REG = get_next_unused_register(new_used)
            line_list.append(load_imm(RIGHT_REG, rightIMM))
            rightRegister = RIGHT_REG
        
        if op in immediate_any:
            if leftIMM and rightIMM:
                if op == ">>>":
                    return [], None, leftIMM // (2 ** rightIMM)
                elif op == "~|":
                    return [], None, ~(leftIMM | rightIMM)
                return [], None, eval("{}{}{}\n".format(leftIMM, op, rightIMM))
            if op in immediate_symmetric:
                if leftIMM or rightIMM:
                    IMM = rightIMM
                    regSRC = leftRegister
                    if leftIMM:
                        IMM = leftIMM
                        regSRC = rightRegister
                    if IMM < 65536 and IMM >= -65536:
                        line_list = ["{}{}, {}, {}\n".format(immediate_map[op], target_reg, regSRC, IMM)]
                        used_set.add(target_reg)
                        help_add(regSRC, used_set)
                        return right_lines + left_lines + line_list, target_reg, None
            elif op in immediate_right:
                if rightIMM:
                    IMM = rightIMM
                    if op == "-":
                        # Special case: sub becomes addi
                        op = "+"
                        IMM = -IMM
                    line_list[-1] = "{}{}, {}, {}\n".format(immediate_map[op], target_reg, leftRegister, IMM)
                    used_set.add(target_reg)
                    help_add(leftRegister, used_set)
                    return right_lines + left_lines + line_list, target_reg, None
            line_list.append("{}{}, {}, {}\n".format(inst_map[op], target_reg, leftRegister, rightRegister))
        else:
            if op in unary_map:
                if op in unary_imm and rightIMM:
                    return [], None, eval("{}{}\n".format(op[-1], rightIMM))
                if op in unary_store:
                    line_list = [unary_map[op].format(target_reg, tree.extras, rightRegister) + "\n"]
                else:
                    line_list = [unary_map[op].format(target_reg, rightRegister) + "\n"]
            elif op in pseudoinst_group1:
                if leftIMM and rightIMM:
                    return [], None, eval("{}{}{}\n".format(leftIMM, pseudoinst_group1[op], rightIMM))
                
                IMM = 0
                if rightIMM and op in ["*", "/", "%"]:
                    IMM = rightIMM
                    regSRC = leftRegister
                elif leftIMM and op in ["*"]:
                    IMM = leftIMM
                    regSRC = rightRegister
                if IMM < 65536 and IMM > 0 and (IMM & (IMM-1) == 0): # Bit manipulations! Checking if IMM is a power of two.
                    if op == "%":
                        # Modulo a power of two is like chopping bits.
                        line_list = ["andi    {}, {}, {}\n".format(target_reg, regSRC, IMM - 1)]
                    IMM = IMM.bit_length()
                    if op == "*":
                        line_list = ["sll     {}, {}, {}\n".format(target_reg, regSRC, IMM - 1)]
                    elif op == "/":
                        line_list = ["sra     {}, {}, {}\n".format(target_reg, regSRC, IMM - 1)]
                    used_set.add(target_reg)
                    help_add(regSRC, used_set)
                    return right_lines + left_lines + line_list, target_reg, None

                inst = pseudoinst_group1_map[op]
                line_list.append("{}{}, {}\n".format(inst[0], leftRegister, rightRegister))
                line_list.append("{}{}\n".format(inst[1], target_reg))
            
        used_set.add(target_reg)
        help_add(leftRegister, used_set)
        help_add(rightRegister, used_set)
        return right_lines + left_lines + line_list, target_reg, None

def parse_expr(target_reg, text, needs_extra=False):
    root = expr_store(Tokenizer(text))
    if not needs_extra:
        needs_extra = re.search("\{}(?=[\s#)+*/%&|^~-]|$)".format(target_reg), text)
        # HACKY THING!!!
        if text.startswith(">"):
            needs_extra = True
    result_loc = target_reg
    used_registers = []
    used_set = set()
    if needs_extra:
        result_loc = "$et0"
        used_registers.append(result_loc)
        used_set.add(result_loc)
    
    # Now that we've built the tree, we're going to postorder through it and generate the instructions.
    lines, result_loc2, IMM = traverse_getlines(result_loc, root, used_set, used_registers)
    if IMM:
        lines = [load_imm(target_reg, IMM)]
    else:
        if needs_extra:
            lines[-1] = lines[-1].replace("$et0", target_reg, 1)
        assert result_loc == result_loc2
    if target_reg in used_set:
        used_set.remove(target_reg)
    return lines, used_set

### -------------------------------------------------------------------------------------------------
### -------------------------------------------------------------------------------------------------
### -------------------------------------------------------------------------------------------------
### -------------------------------------------------------------------------------------------------
###                                     BEGIN emips.py
### -------------------------------------------------------------------------------------------------
### -------------------------------------------------------------------------------------------------
### -------------------------------------------------------------------------------------------------
### -------------------------------------------------------------------------------------------------

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
                        split_var = re.match("([(]\$[^)]+[)])([a-zA-Z_][^\s,#]*)", x.strip())
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
                print("{}:{}: Syntax error: Did not find function start for @FUNCTION declaration at {}, expected [{}]".format(filename, fline, fline_func_start, function_name))
                return


            # Replacing all the things, and local aliasing

            local_alias = []
            
            stkptr = "sp"
            k0_warning = 0 # Bit 0: Interrupt handler or not. Bit 1: Seen $k0 or not. Bit 2: Seen lstk/sstk or not.
            if interrupt_handler:
                stkptr = "k0"
                k0_warning = 1
            func_fline = fline_func_start
            free_tmp_registers = ["$at"] + ["$t"+str(i) for i in range(9, -1, -1)]
            free_tmp_registers += ["$v1", "$v0", "$a3", "$a2", "$a1", "$a0"]

            for alias_pair in aliases:
                regname = "$" + alias_pair[1]
                if regname in free_tmp_registers:
                    free_tmp_registers.remove(regname)

            used_tmp_registers = set()
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

                la = re.match("((?:[^#]*:)?\s*)la\s+", line)
                if la:
                    prefix = la[1]
                    # Process special la command!
                    la_inst = re.search("la\s+(\$[^\s,]+)\s*,\s*([a-zA-Z_][^\s#()]*)", line)
                    if la_inst:
                        var = la_inst[2]
                        if var in stack:
                            if debug:
                                print("{}:{}: [DEBUG] Found load stack address instruction, loading stack address {}".format(filename, func_fline, var))
                            line = "{}addi    {}, ${}, {} # {}\n".format(prefix, la_inst[1], stkptr, stack[var], line.strip())

                lstk = re.match("((?:[^#]*:)?\s*)lstk\s+", line)
                if lstk:
                    prefix = lstk[1]
                    if not useStack:
                        print("{}:{}: Syntax error: lstk (Load Stack) pseudoinstruction used without a stack initialization".format(filename, func_fline))
                        return
                    lstk_inst = re.search("lstk\s+(\$[^\s,]+)\s*,\s*(\d+[(][^\s#()]*[)]|[^\s#()]*)", line)
                    if not lstk_inst:
                        print("{}:{}: Syntax error: lstk (Load Stack) pseudoinstruction is malformed".format(filename, func_fline))
                        return
                    var = lstk_inst[2]
                    if var in stack:
                        line = "{}lw      {}, {}(${}) # {}\n".format(prefix, lstk_inst[1], stack[var], stkptr, line.strip())
                    else:
                        lstk_offset = re.search("(\d+)[(]([^\s#()]*)[)]", var)
                        if lstk_offset:
                            extra_offset = int(lstk_offset[1])
                            line = "{}lw      {}, {}(${}) # {}\n".format(prefix, lstk_inst[1], stack[lstk_offset[2]] + extra_offset, stkptr, line.strip())
                        else:
                            print("{}:{}: Syntax error: lstk (Load Stack): could not find stack variable by name {}".format(filename, func_fline, var))
                            return
                    k0_warning |= 4

                sstk = re.match("((?:[^#]*:)?\s*)sstk\s+", line)
                if sstk:
                    prefix = sstk[1]
                    if not useStack:
                        print("{}:{}: Syntax error: sstk (Store Stack) pseudoinstruction used without a stack initialization".format(filename, func_fline))
                        return
                    sstk_inst = re.search("sstk\s+(\$[^\s,]+)\s*,\s*([^\s#]*)", line)
                    if not sstk_inst:
                        print("{}:{}: Syntax error: sstk (Store Stack) pseudoinstruction is malformed".format(filename, func_fline))
                        return
                    var = sstk_inst[2]
                    if var in stack:
                        line = "{}sw      {}, {}(${}) # {}\n".format(prefix, sstk_inst[1], stack[var], stkptr, line.strip())
                    else:
                        sstk_offset = re.search("(\d+)[(]([^\s#()]*)[)]", var)
                        if sstk_offset:
                            line = "{}sw      {}, {}(${}) # {}\n".format(prefix, sstk_inst[1], stack[sstk_offset[2]] + extra_offset, stkptr, line.strip())
                        else:
                            print("{}:{}: Syntax error: sstk (Store Stack): could not find stack variable by name {}".format(filename, func_fline, var))
                            return
                    k0_warning |= 4

                line_parts = line.split("#", 1)
                for alias in local_alias:
                    line_parts[0] = re.sub("\${}(?=[\s#=,)]|$)".format(alias[0]), alias[1], line_parts[0])
                for alias in aliases:
                    line_parts[0] = re.sub("\${}(?=[\s#=,)]|$)".format(alias[0]), alias[1], line_parts[0])
                
                line = "#".join(line_parts)

                if re.search("(\$k0(?=[\s#,)]|$))", line_parts[0]):
                    k0_warning |= 2
                
                for tmp_reg_i in range(len(free_tmp_registers) -1, -1, -1):
                    reg = free_tmp_registers[tmp_reg_i]
                    if re.search("(\${}(?=[\s#,)]|$))".format(reg), line_parts[0]):
                        free_tmp_registers.pop(tmp_reg_i)
                for used_tmp_reg in used_tmp_registers:
                    if re.search("(\${}(?=[\s#,)]|$))".format(used_tmp_reg), line_parts[0]):
                        print("{}:{}: WARNING: tmp register {} (used by Arithmetic Assign) appears later in file, use .alias to ensure registers aren't touched.".format(filename, func_fline, used_tmp_reg))
                        

                assign_statement = re.match("((?:[^#]*:)?\s*)assign\s+", line)
                if assign_statement:
                    prefix = assign_statement[1]
                    spacing = ' ' * len(prefix)
                    assign_inst = re.search("assign\s+(\$[^\s=]+)\s*=\s*([^#]*)", line)
                    if not assign_inst:
                        print("{}:{}: Syntax error: assign (Arithmetic assign) pseudoinstruction is malformed".format(filename, func_fline))
                        return
                    target_reg = assign_inst[1]
                    expr_body = assign_inst[2]
                    assign_lines, assign_used_registers = parse_expr(target_reg, expr_body)
                    if len(assign_used_registers) > len(free_tmp_registers):
                        print("{}:{}: UnsupportedComplexity error: assign (Arithmetic assign) pseudoinstruction uses more temporaries than are available! Try freeing some by using .stacksave or .aliaslocal".format(filename, func_fline))
                        return
                    if len(assign_used_registers) > 0 and len(assign_lines) > 1:
                        code_lines += ["{}.set noat   # {}\n".format(prefix, interpret)]
                    else:
                        code_lines += ["{}# {}\n".format(prefix, interpret)]
                    regmapping = []
                    free_reg_index = 0
                    for regToMap in assign_used_registers:
                        used_tmp_registers.add(free_tmp_registers[len(regmapping)])
                        regmapping.append((regToMap, free_tmp_registers[len(regmapping)]))
                    for assign_line in assign_lines:
                        assign_line = spacing + assign_line
                        for mapping in regmapping:
                            assign_line = re.sub("\${}(?=[\s#,)]|$)".format(mapping[0][1:]), mapping[1], assign_line)
                        code_lines.append(assign_line)
                    if len(assign_used_registers) > 0 and len(assign_lines) > 1:
                        code_lines += ["{}.set at\n".format(prefix)]

                    if debug:
                        print("{}:{}: [DEBUG] assign statement uses {} tmp registers: {}".format(filename, func_fline, len(regmapping), ', '.join([x[1] for x in regmapping])))
                else:
                    code_lines.append(line)
                
            if k0_warning == 7:
                print("{}:{}: Warning: lstk or sstk (Load/Store Stack) command detected in interrupt handler code that uses $k0".format(filename, fline))

            if (re.match("(?:[^#]*:)?\s*jr\s+", code_lines[-1])):
                print(fline, ": Warning: code tagged with @FUNCTION tag ends with a jump register instruction")

            if interrupt_handler and len(used_tmp_registers) > 0:
                if debug:
                    print("{}:{}: [DEBUG] Detected assign statements in interrupt handler, saving tmp registers to interrupt space".format(filename, fline))
                for used_tmp_reg in used_tmp_registers:
                    if used_tmp_reg in stack:
                        continue
                    stack_varnames.append(used_tmp_reg)
                    stack[used_tmp_reg] = stackSize
                    stackSize += 4
                    stack_inserts.append(used_tmp_reg)

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
                        print("{}:{}: SEVERE-Warning: Manually allocated instruction handler space is not large enough to fit all allocated local variables. This is probably an error".format(filename, fline))
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
