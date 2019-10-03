# MIPS-helpers
Some quality of life stuff for MIPS. Kinda like language extensions in a big ugly python script.

## Usage: 
emips.py inputfilename

emips.py

If the input file ends in .fs, it automatically sets the output file, with a .s extension.
Otherwise it asks for the output file name.


Helps you automatically set up stack frames and allows aliasing of registers.

Also includes Notepad++ language files for the small language extensions

# Commands:

## @FUNCTION/@function and !FUNCTION/!function
  Designate a block of code as a function.
  Without the @FUNCTION designation, other things won't run.
  Requires argument: name=fname

## .alias
  Alias a register. See demo images.
  
## .stacksave 
  Saves certain registers to the stack, and then resets them when tearing the stack down. (Use for S registers)
  Example usage: .stacksave $s0 $s1

## .stackalloc
  Sets up and tears down a stack frame with aliased stack variables of specified sizes.

## lstk (Load Stack)
  Load an aliased stack variable. Compiles to lw with an offset.
  
## sstk (Store Stack)
  Store an aliased stack variable. Compiles to sw with an offset.

# Demos

Aliasing demo. Left: Before, Right: After
![demo 1](https://github.com/mass2010chromium/MIPS-helpers/blob/master/images/demo.png)

StackAlloc demo. Left: Before, Right: After
![demo 2](https://github.com/mass2010chromium/MIPS-helpers/blob/master/images/demo2.png)
