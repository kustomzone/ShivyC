"""Classes representing IL commands.

Each IL command is represented by a class that inherits from the ILCommand
interface. The implementation provides code that generates ASM for each IL
command.

For arithmetic commands like Add or Mult, the arguments and output must all be
pre-cast to the same type. In addition, this type must be size `int` or greater
per the C spec. The Set command is exempt from this requirement, and can be
used to cast.

"""

import ctypes
import spots
from il_gen import CType
from spots import Spot


class ILCommand:
    """Base interface for all IL commands."""

    def input_values(self):
        """Return list of values read by this command."""
        raise NotImplementedError

    def output_values(self):
        """Return list of values modified by this command."""
        raise NotImplementedError

    def make_asm(self, spotmap, asm_code):
        """Generate assembly code for this command.

        Generated assembly can read any of the values returned from
        input_values, may overwrite any values returned from output_values, and
        may change the value of any spots returned from clobber_spots.

        asm_code (ASMCode) - Object to which to save generated code.
        spotmap - Dictionary mapping each input/output value to a spot.

        """
        raise NotImplementedError

    def assert_same_ctype(self, il_values):
        """Raise ValueError if all IL values do not have the same type."""
        ctype = None
        for il_value in il_values:
            if ctype and ctype != il_value.ctype:
                raise ValueError("different ctypes")  # pragma: no cover

    def to_str(self, name, inputs, output=None):  # pragma: no cover
        """Given the name, inputs, and outputs return its string form."""
        RED = '\033[91m'
        ENDC = '\033[0m'
        BOLD = '\033[1m'

        input_str = "".join(str(input).ljust(40) for input in inputs)
        output_str = (str(output) if output else "").ljust(40)
        return output_str + RED + BOLD + str(name).ljust(10) + ENDC + " " + \
               input_str


class Add(ILCommand):
    """ADD - adds arg1 and arg2, then saves to output.

    IL values output, arg1, arg2 must all have the same type. No type
    conversion or promotion is done here.

    """

    def __init__(self, output, arg1, arg2): # noqa D102
        self.output = output
        self.arg1 = arg1
        self.arg2 = arg2

        self.assert_same_ctype([output, arg1, arg2])

    def input_values(self): # noqa D102
        return [self.arg1, self.arg2]

    def output_values(self): # noqa D102
        return [self.output]

    def make_asm(self, spotmap, asm_code): # noqa D102
        ctype = self.arg1.ctype
        arg1_asm = spotmap[self.arg1].asm_str(ctype.size)
        arg2_asm = spotmap[self.arg2].asm_str(ctype.size)
        output_asm = spotmap[self.output].asm_str(ctype.size)
        rax_asm = spots.RAX.asm_str(ctype.size)

        # We can just use "mov" without sign extending because these will be
        # same size.
        asm_code.add_command("mov", rax_asm, arg1_asm)
        asm_code.add_command("add", rax_asm, arg2_asm)
        asm_code.add_command("mov", output_asm, rax_asm)

    def __str__(self):    # pragma: no cover
        return self.to_str("ADD", [self.arg1, self.arg2], self.output)


class Mult(ILCommand):
    """MULT - multiplies arg1 and arg2, then saves to output.

    IL values output, arg1, arg2 must all have the same type. No type
    conversion or promotion is done here.

    """

    def __init__(self, output, arg1, arg2):  # noqa D102
        self.output = output
        self.arg1 = arg1
        self.arg2 = arg2

        self.assert_same_ctype([output, arg1, arg2])

    def input_values(self): # noqa D102
        return [self.arg1, self.arg2]

    def output_values(self): # noqa D102
        return [self.output]

    def make_asm(self, spotmap, asm_code): # noqa D102
        ctype = self.arg1.ctype
        arg1_asm = spotmap[self.arg1].asm_str(ctype.size)
        arg2_asm = spotmap[self.arg2].asm_str(ctype.size)
        output_asm = spotmap[self.output].asm_str(ctype.size)
        rax_asm = spots.RAX.asm_str(ctype.size)

        asm_code.add_command("mov", rax_asm, arg1_asm)

        if ctype.signed:
            # If ctype is signed, then use signed multiplication
            asm_code.add_command("imul", rax_asm, arg2_asm)
        elif spotmap[self.arg2].spot_type == Spot.LITERAL:
            # If ctype is unsigned and literal, move to register and multiply
            arg2_final_asm = spots.RSI.asm_str(ctype.size)
            asm_code.add_command("mov", arg2_final_asm, arg2_asm)
            asm_code.add_command("mul", arg2_final_asm)
        else:
            # If ctype is unsigned and not literal, just multiply
            asm_code.add_command("mul", arg2_asm)

        asm_code.add_command("mov", output_asm, rax_asm)

    def __str__(self):    # pragma: no cover
        return self.to_str("MULT", [self.arg1, self.arg2], self.output)


class Div(ILCommand):
    """DIV - divides arg1 and arg2, then saves to output.

    IL values output, arg1, arg2 must all have the same type of size at least
    int. No type conversion or promotion is done here.

    """

    def __init__(self, output, arg1, arg2): # noqa D102
        self.output = output
        self.arg1 = arg1
        self.arg2 = arg2

        self.assert_same_ctype([output, arg1, arg2])

    def input_values(self): # noqa D102
        return [self.arg1, self.arg2]

    def output_values(self): # noqa D102
        return [self.output]

    def make_asm(self, spotmap, asm_code): # noqa D102
        ctype = self.arg1.ctype
        arg1_asm = spotmap[self.arg1].asm_str(ctype.size)
        arg2_asm = spotmap[self.arg2].asm_str(ctype.size)
        output_asm = spotmap[self.output].asm_str(ctype.size)
        rax_asm = spots.RAX.asm_str(ctype.size)

        # If the divisor is a literal, we must move it to a register.
        if spotmap[self.arg2].spot_type == Spot.LITERAL:
            arg2_final_asm = spots.RSI.asm_str(ctype.size)
            asm_code.add_command("mov", arg2_final_asm, arg2_asm)
        else:
            arg2_final_asm = arg2_asm

        asm_code.add_command("mov", rax_asm, arg1_asm)

        if ctype.signed:
            if ctype.size == 4:
                asm_code.add_command("cdq")  # sign extend EAX into EDX
            elif ctype.size == 8:
                asm_code.add_command("cqo")  # sign extend RAX into RDX
            asm_code.add_command("idiv", arg2_final_asm)
        else:
            # zero out RDX register
            rdx_asm = spots.RDX.asm_str(ctype.size)
            asm_code.add_command("xor", rdx_asm, rdx_asm)
            asm_code.add_command("div", arg2_final_asm)

        asm_code.add_command("mov", output_asm, rax_asm)

    def __str__(self):  # pragma: no cover
        return self.to_str("DIV", [self.arg1, self.arg2], self.output)


class _GeneralEqualCmp(ILCommand):
    """_GeneralEqualCmp - base class for EqualCmp and NotEqualCmp.

    IL value output must have int type. arg1, arg2 must have types that can
    be compared for equality bit-by-bit. No type conversion or promotion is
    done here.

    """

    def __init__(self, output, arg1, arg2): # noqa D102
        self.output = output
        self.arg1 = arg1
        self.arg2 = arg2

    def input_values(self): # noqa D102
        return [self.arg1, self.arg2]

    def output_values(self): # noqa D102
        return [self.output]

    def make_asm(self, spotmap, asm_code): # noqa D102
        output_asm = spotmap[self.output].asm_str(self.output.ctype.size)
        arg1_spot = spotmap[self.arg1]
        arg2_spot = spotmap[self.arg2]

        asm_code.add_command("mov", output_asm, self.equal_value)

        # If both LITERAL or both MEM, move one to a register
        if ((arg1_spot.spot_type == Spot.LITERAL and
             arg2_spot.spot_type == Spot.LITERAL) or
            (arg1_spot.spot_type == Spot.MEM and
             arg2_spot.spot_type == Spot.MEM)):
            rax_asm = spots.RAX.asm_str(self.arg1.ctype.size)
            asm_code.add_command("mov", rax_asm,
                                 arg1_spot.asm_str(self.arg1.ctype.size))
            arg1_spot = spots.RAX

        # If either arg is 64-bit immediate, move to a register
        if ((arg1_spot.spot_type == Spot.LITERAL and
             self.arg1.ctype.size == 8)):
            rdx_asm = spots.RDX.asm_str(self.arg1.ctype.size)
            asm_code.add_command("mov", rdx_asm,
                                 arg1_spot.asm_str(self.arg1.ctype.size))
            arg1_spot = spots.RDX
        elif ((arg2_spot.spot_type == Spot.LITERAL and
               self.arg2.ctype.size == 8)):
            rdx_asm = spots.RDX.asm_str(self.arg2.ctype.size)
            asm_code.add_command("mov", rdx_asm,
                                 arg2_spot.asm_str(self.arg2.ctype.size))
            arg2_spot = spots.RDX

        label = asm_code.get_label()
        asm_code.add_command("cmp", arg1_spot.asm_str(self.arg1.ctype.size),
                             arg2_spot.asm_str(self.arg2.ctype.size))
        asm_code.add_command("je", label)
        asm_code.add_command("mov", output_asm, self.not_equal_value)
        asm_code.add_label(label)


class NotEqualCmp(_GeneralEqualCmp):
    """NotEqualCmp - checks whether arg1 and arg2 are not equal.

    IL value output must have int type. arg1, arg2 must all have the same
    type. No type conversion or promotion is done here.

    """

    equal_value = "0"
    not_equal_value = "1"

    def __str__(self):  # pragma: no cover
        return self.to_str("NEQ", [self.arg1, self.arg2], self.output)


class EqualCmp(_GeneralEqualCmp):
    """EqualCmp - checks whether arg1 and arg2 are equal.

    IL value output must have int type. arg1, arg2 must all have the same
    type. No type conversion or promotion is done here.

    """

    equal_value = "1"
    not_equal_value = "0"

    def __str__(self):  # pragma: no cover
        return self.to_str("NEQ", [self.arg1, self.arg2], self.output)


class Set(ILCommand):
    """SET - sets output IL value to arg IL value.

    The output IL value and arg IL value need not have the same type. The SET
    command will generate code to convert them as necessary.

    """

    def __init__(self, output, arg): # noqa D102
        self.output = output
        self.arg = arg

    def input_values(self): # noqa D102
        return [self.arg]

    def output_values(self): # noqa D102
        return [self.output]

    def make_asm(self, spotmap, asm_code): # noqa D102
        if self.output.ctype == ctypes.bool_t:
            self._set_bool(spotmap, asm_code)
        else:
            arg_spot = spotmap[self.arg]
            output_spot = spotmap[self.output]
            output_asm = output_spot.asm_str(self.output.ctype.size)

            both_stack = (arg_spot.spot_type == Spot.MEM and
                          output_spot.spot_type == Spot.MEM)

            if both_stack:
                temp = spots.RAX.asm_str(self.output.ctype.size)
            else:
                temp = output_asm

            # TODO: This is getting /really/ messy.
            if self.output.ctype.size <= self.arg.ctype.size:
                asm_code.add_command("mov", temp,
                                     arg_spot.asm_str(self.output.ctype.size))
            elif self.output.ctype.size > self.arg.ctype.size:
                if arg_spot.spot_type == Spot.LITERAL:
                    temp2 = temp
                    mov = "mov"
                elif (self.output.ctype.size == 8 and
                      self.arg.ctype.size == 4 and
                      not self.arg.ctype.signed):
                    temp2 = spots.RAX.asm_str(4)
                    mov = "mov"
                elif self.arg.ctype.signed:
                    temp2 = temp
                    mov = "movsx"
                else:
                    temp2 = temp
                    mov = "movzx"

                asm_code.add_command(mov, temp2,
                                     arg_spot.asm_str(self.arg.ctype.size))

            if both_stack:
                # We can move because rax_asm has same size as output_asm
                asm_code.add_command("mov", output_asm, temp)

    def _set_bool(self, spotmap, asm_code):
        """Emit code for SET command if arg is boolean type."""
        # When any scalar value is converted to _Bool, the result is 0 if the
        # value compares equal to 0; otherwise, the result is 1
        arg_asm_old = spotmap[self.arg].asm_str(self.arg.ctype.size)
        if spotmap[self.arg].spot_type == Spot.LITERAL:
            rax_asm = spots.RAX.asm_str(self.arg.ctype.size)
            asm_code.add_command("mov", rax_asm, arg_asm_old)
            arg_asm = rax_asm
        else:
            arg_asm = arg_asm_old

        label = asm_code.get_label()
        output_asm = spotmap[self.output].asm_str(self.output.ctype.size)
        asm_code.add_command("mov", output_asm, "0")
        asm_code.add_command("cmp", arg_asm, "0")
        asm_code.add_command("je", label)
        asm_code.add_command("mov", output_asm, "1")
        asm_code.add_label(label)

    def __str__(self):  # pragma: no cover
        return self.to_str("SET", [self.arg], self.output)


class Return(ILCommand):
    """RETURN - returns the given value from function.

    For now, arg must have type int.

    """

    def __init__(self, arg): # noqa D102
        # arg must already be cast to return type
        self.arg = arg

    def input_values(self): # noqa D102
        return [self.arg]

    def output_values(self): # noqa D102
        return []

    def make_asm(self, spotmap, asm_code): # noqa D102
        arg_asm = spotmap[self.arg].asm_str(self.arg.ctype.size)
        rax_asm = spots.RAX.asm_str(self.arg.ctype.size)

        asm_code.add_command("mov", rax_asm, arg_asm)
        asm_code.add_command("mov", "rsp", "rbp")
        asm_code.add_command("pop", "rbp")
        asm_code.add_command("ret")

    def __str__(self):  # pragma: no cover
        return self.to_str("RET", [self.arg])


class Label(ILCommand):
    """Label - Analogous to an ASM label."""

    def __init__(self, label): # noqa D102
        """The label argument is an string label name unique to this label."""
        self.label = label

    def input_values(self): # noqa D102
        return []

    def output_values(self): # noqa D102
        return []

    def make_asm(self, spotmap, asm_code): # noqa D102
        asm_code.add_label(self.label)

    def __str__(self):  # pragma: no cover
        return self.to_str("LABEL", [self.label])


class JumpZero(ILCommand):
    """Jumps to a label if given condition is zero."""

    def __init__(self, cond, label): # noqa D102
        self.cond = cond
        self.label = label

    def input_values(self): # noqa D102
        return [self.cond]

    def output_values(self): # noqa D102
        return []

    def make_asm(self, spotmap, asm_code): # noqa D102
        if spotmap[self.cond].spot_type == Spot.LITERAL:
            cond_asm_old = spotmap[self.cond].asm_str(self.cond.ctype.size)
            rax_asm = spots.RAX.asm_str(self.cond.ctype.size)
            asm_code.add_command("mov", rax_asm, cond_asm_old)
            cond_asm = rax_asm
        else:
            cond_asm = spotmap[self.cond].asm_str(self.cond.ctype.size)

        asm_code.add_command("cmp", cond_asm, "0")
        asm_code.add_command("je", self.label)

    def __str__(self):  # pragma: no cover
        return self.to_str("JZERO", [self.cond, self.label])


class AddrOf(ILCommand):
    """Gets address of given variable.

    `output` must have type pointer to the type of `var`.

    """

    def __init__(self, output, var):  # noqa D102
        self.output = output
        self.var = var

    def input_values(self):  # noqa D102
        return [self.var]

    def output_values(self):  # noqa D102
        return [self.output]

    def make_asm(self, spotmap, asm_code):  # noqa D102
        # TODO: Use permanent spot of var, not spotmap temporary spot
        var_asm = spotmap[self.var].asm_str(0)
        temp = spots.RAX.asm_str(self.output.ctype.size)
        output_asm = spotmap[self.output].asm_str(self.output.ctype.size)

        asm_code.add_command("lea", temp, var_asm)
        asm_code.add_command("mov", output_asm, temp)

    def __str__(self):  # pragma: no cover
        return self.to_str("ADDROF", [self.var], self.output)


class ReadAt(ILCommand):
    """Reads value at given address.

    `addr` must have type pointer to the type of `output`

    """

    def __init__(self, output, addr):  # noqa D102
        self.output = output
        self.addr = addr

    def input_values(self):  # noqa D102
        return [self.addr]

    def output_values(self):  # noqa D102
        return [self.output]

    def make_asm(self, spotmap, asm_code):  # noqa D102
        addr_asm = spotmap[self.addr].asm_str(8)
        rax = spots.RAX.asm_str(8)
        temp = spots.RAX.asm_str(self.output.ctype.size)
        rax_spot = Spot(Spot.MEM, ("rax", 0)).asm_str(self.output.ctype.size)
        output_asm = spotmap[self.output].asm_str(self.output.ctype.size)

        asm_code.add_command("mov", rax, addr_asm)
        asm_code.add_command("mov", temp, rax_spot)
        asm_code.add_command("mov", output_asm, temp)

    def __str__(self):  # pragma: no cover
        return self.to_str("READAT", [self.addr], self.output)


class Call(ILCommand):
    """Call a given function.

    func - Name of the function to call as a function IL value
    args - Arguments of the function, in left-to-right order. Must match the
    parameter types the function expects.
    ret - IL value to save the return value. Must match the function return
    value.

    """

    def __init__(self, func, args, ret): # noqa D102
        self.func = func
        self.args = args
        self.ret = ret

    def input_values(self): # noqa D102
        return [self.func] + self.args

    def output_values(self): # noqa D102
        return [self.ret]

    def make_asm(self, spotmap, asm_code): # noqa D102
        # Registers ordered from first to last for arguments.
        regs = [spots.RDI, spots.RSI, spots.RDX]

        # Reverse the registers to go from last to first, so we can pop() out
        # registers.
        regs.reverse()
        for arg in self.args:
            if arg.ctype.type_type != CType.ARITH:
                raise NotImplementedError("only integer arguments supported")
            elif not regs:
                raise NotImplementedError("too many arguments")

            reg = regs.pop()
            asm_code.add_command("mov", reg.asm_str(arg.ctype.size),
                                 spotmap[arg].asm_str(arg.ctype.size))

        # TODO: Fix this hack! Once pointers are implemented there will
        # hopefully be a better way to call functions.
        asm_code.add_command("call", spotmap[self.func].detail)

        ret_asm = spotmap[self.ret].asm_str(self.func.ctype.ret.size)
        rax_asm = spots.RAX.asm_str(self.func.ctype.ret.size)
        asm_code.add_command("mov", ret_asm, rax_asm)

    def __str__(self):  # pragma: no cover
        return self.to_str("CALL", self.args, self.ret)
