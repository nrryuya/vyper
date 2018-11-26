import binascii
import re

from collections import OrderedDict
from vyper.exceptions import InvalidLiteralException
from vyper.opcodes import opcodes

try:
    from Crypto.Hash import keccak
    sha3 = lambda x: keccak.new(digest_bits=256, data=x).digest()
except ImportError:
    import sha3 as _sha3
    sha3 = lambda x: _sha3.sha3_256(x).digest()


# Converts four bytes to an integer
def fourbytes_to_int(inp):
    return (inp[0] << 24) + (inp[1] << 16) + (inp[2] << 8) + inp[3]


# Converts string to bytes
def string_to_bytes(str):
    bytez = b''
    for c in str:
        if ord(c) >= 256:
            raise InvalidLiteralException("Cannot insert special character %r into byte array" % c)
        bytez += bytes([ord(c)])
    bytez_length = len(bytez)
    return bytez, bytez_length


# Converts a provided hex string to an integer
def hex_to_int(inp):
    if inp[:2] == '0x':
        inp = inp[2:]
    return bytes_to_int(binascii.unhexlify(inp))


# Converts bytes to an integer
def bytes_to_int(bytez):
    o = 0
    for b in bytez:
        o = o * 256 + b
    return o


# Encodes an address using ethereum's checksum scheme
def checksum_encode(addr):  # Expects an input of the form 0x<40 hex chars>
    assert addr[:2] == '0x' and len(addr) == 42
    o = ''
    v = bytes_to_int(sha3(addr[2:].lower().encode('utf-8')))
    for i, c in enumerate(addr[2:]):
        if c in '0123456789':
            o += c
        else:
            o += c.upper() if (v & (2**(255 - 4 * i))) else c.lower()
    return '0x' + o


# Returns lowest multiple of 32 >= the input
def ceil32(x):
    return x if x % 32 == 0 else x + 32 - (x % 32)


# Calculates amount of gas needed for memory expansion
def calc_mem_gas(memsize):
    return (memsize // 32) * 3 + (memsize // 32) ** 2 // 512


# Specific gas usage
GAS_IDENTITY = 15
GAS_IDENTITYWORD = 3

# A decimal value can store multiples of 1/DECIMAL_DIVISOR
DECIMAL_DIVISOR = 10000000000


# Number of bytes in memory used for system purposes, not for variables
class MemoryPositions:
    ADDRSIZE = 32
    MAXNUM = 64
    MINNUM = 96
    MAXDECIMAL = 128
    MINDECIMAL = 160
    FREE_VAR_SPACE = 192
    FREE_VAR_SPACE2 = 224
    BLANK_SPACE = 256
    FREE_LOOP_INDEX = 288
    RESERVED_MEMORY = 320


# Sizes of different data types. Used to clamp types.
class SizeLimits:
    ADDRSIZE = 2**160
    MAXNUM = 2**127 - 1
    MINNUM = -2**127
    MAXDECIMAL = (2**127 - 1) * DECIMAL_DIVISOR
    MINDECIMAL = (-2**127) * DECIMAL_DIVISOR
    MAX_UINT256 = 2**256 - 1

    @classmethod
    def in_bounds(cls, type_str, value):
        assert isinstance(type_str, str)
        if type_str == 'decimal':
            return float(cls.MINDECIMAL) <= value <= float(cls.MAXDECIMAL)
        if type_str == 'uint256':
            return 0 <= value <= cls.MAX_UINT256
        elif type_str == 'int128':
            return cls.MINNUM <= value <= cls.MAXNUM
        else:
            raise Exception('Unknown type "%s" supplied.' % type_str)


# Map representing all limits loaded into a contract as part of the initializer
# code.
LOADED_LIMIT_MAP = OrderedDict((
    (MemoryPositions.ADDRSIZE, SizeLimits.ADDRSIZE),
    (MemoryPositions.MAXNUM, SizeLimits.MAXNUM),
    (MemoryPositions.MINNUM, SizeLimits.MINNUM),
    (MemoryPositions.MAXDECIMAL, SizeLimits.MAXDECIMAL),
    (MemoryPositions.MINDECIMAL, SizeLimits.MINDECIMAL),
))


RLP_DECODER_ADDRESS = hex_to_int('0x5185D17c44699cecC3133114F8df70753b856709')

# Instructions for creating RLP decoder on other chains
# First send 10**17 wei to 0x39ba083c30fCe59883775Fc729bBE1f9dE4DEe11
# Publish this tx to create the contract: 0xf9035b808506fc23ac0083045f788080b903486103305660006109ac5260006109cc527f0100000000000000000000000000000000000000000000000000000000000000600035046109ec526000610a0c5260006109005260c06109ec51101515585760f86109ec51101561006e5760bf6109ec510336141558576001610a0c52610098565b60013560f76109ec51036020035260005160f66109ec510301361415585760f66109ec5103610a0c525b61022060016064818352015b36610a0c511015156100b557610291565b7f0100000000000000000000000000000000000000000000000000000000000000610a0c5135046109ec526109cc5160206109ac51026040015260016109ac51016109ac5260806109ec51101561013b5760016109cc5161044001526001610a0c516109cc5161046001376001610a0c5101610a0c5260216109cc51016109cc52610281565b60b86109ec5110156101d15760806109ec51036109cc51610440015260806109ec51036001610a0c51016109cc51610460013760816109ec5114156101ac5760807f01000000000000000000000000000000000000000000000000000000000000006001610a0c5101350410151558575b607f6109ec5103610a0c5101610a0c5260606109ec51036109cc51016109cc52610280565b60c06109ec51101561027d576001610a0c51013560b76109ec510360200352600051610a2c526038610a2c5110157f01000000000000000000000000000000000000000000000000000000000000006001610a0c5101350402155857610a2c516109cc516104400152610a2c5160b66109ec5103610a0c51016109cc516104600137610a2c5160b66109ec5103610a0c510101610a0c526020610a2c51016109cc51016109cc5261027f565bfe5b5b5b81516001018083528114156100a4575b5050601f6109ac511115155857602060206109ac5102016109005260206109005103610a0c5261022060016064818352015b6000610a0c5112156102d45761030a565b61090051610a0c516040015101610a0c51610900516104400301526020610a0c5103610a0c5281516001018083528114156102c3575b50506109cc516109005101610420526109cc5161090051016109005161044003f35b61000461033003610004600039610004610330036000f31b2d4f
# This is the contract address: 0x5185D17c44699cecC3133114F8df70753b856709

# Available base types
base_types = ['int128', 'decimal', 'bytes32', 'uint256', 'bool', 'address']

# Keywords available for ast.Call type
valid_call_keywords = ['uint256', 'int128', 'decimal', 'address', 'contract', 'indexed']

# Valid base units
valid_units = ['wei', 'sec']

# Valid attributes for global variables
valid_global_keywords = ['public', 'modifying', 'event', 'constant'] + valid_units + valid_call_keywords

# Cannot be used for variable or member naming
reserved_words = [
    'int128', 'uint256', 'address', 'bytes32',
    'if', 'for', 'while', 'until',
    'pass', 'def', 'push', 'dup', 'swap', 'send', 'call',
    'selfdestruct', 'assert', 'stop', 'throw',
    'raise', 'init', '_init_', '___init___', '____init____',
    'true', 'false', 'self', 'this', 'continue',
    'ether', 'wei', 'finney', 'szabo', 'shannon', 'lovelace', 'ada', 'babbage', 'gwei', 'kwei', 'mwei', 'twei', 'pwei', 'contract',
    'units',
    'zero_address', 'max_int128', 'min_int128', 'max_decimal', 'min_decimal', 'max_uint256',  # constants
]

# List of valid LLL macros.
valid_lll_macros = [
    'assert', 'break', 'ceil32', 'clamp', 'clamp', 'clamp_nonzero', 'clampge',
    'clampgt', 'clample', 'clamplt', 'codeload', 'continue', 'debugger', 'ge',
    'if', 'le', 'lll', 'ne', 'pass', 'repeat', 'seq', 'set', 'sge', 'sha3_32',
    'sha3_64', 'sle', 'uclampge', 'uclampgt', 'uclample', 'uclamplt', 'with',
    '~codelen', 'label', 'goto'
]


# Is a variable or member variable name valid?
# Same conditions apply for function names and events
def is_varname_valid(varname, custom_units):
    from vyper.functions import dispatch_table, stmt_dispatch_table
    built_in_functions = [x for x in stmt_dispatch_table.keys()] + \
      [x for x in dispatch_table.keys()]
    if custom_units is None:
        custom_units = []
    if varname.lower() in [cu.lower() for cu in custom_units]:
        return False
    if varname.lower() in base_types:
        return False
    if varname.lower() in valid_units:
        return False
    if varname.lower() in reserved_words:
        return False
    if varname.upper() in opcodes:
        return False
    if varname.lower() in built_in_functions:
        return False
    if not re.match('^[_a-zA-Z][a-zA-Z0-9_]*$', varname):
        return False
    return True
