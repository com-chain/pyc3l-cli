
from pyc3l.lib.dt import utc_ts_to_local_iso, dt_to_local_iso

import time
import logging
import click
import sys
import tty
import termios
import shutil
import textwrap
import os

logger = logging.getLogger(__name__)


def file_get_contents(filename):
    with open(filename, "r") as f:
        return f.read()


def readCSV(file_path):
    import csv

    with open(file_path, newline="") as csvfile:
        for record in csv.DictReader(csvfile):
            yield record


def filepicker(title):
    import tkinter.filedialog
    import tkinter

    filename = tkinter.filedialog.askopenfilename(title=title)
    if not filename:
        raise Exception("Filepicker was canceled.")
    return filename


def load_wallet(filename):
    import json

    logger.info("Opening file %r", filename)
    wallet = json.loads(file_get_contents(filename))
    logger.info(
        "  File contains wallet with address 0x%s on server %r",
        wallet["address"],
        wallet["server"]["name"],
    )
    return wallet


def unlock_account(wallet, password):
    from eth_account import Account

    account = Account.privateKeyToAccount(Account.decrypt(wallet, password))
    logger.info("Account %s opened.", account.address)
    return account


def load_password(filename):
    import re

    password = file_get_contents(filename)
    password = re.sub(r"\r?\n?$", "", password)  ## remove ending newline if any
    return password


def pp_duration(seconds):
    """Pretty print a duration in seconds

    >>> pp_duration(30)
    '30s'
    >>> pp_duration(60)
    '1m00s'
    >>> pp_duration(3601)
    '1h00m01s'

    """

    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    fmt = "%dh%02dm%02ds" if h else "%dm%02ds" if m else "%ds"
    return "".join(
        [
            fmt % (h, m, s) if h else fmt % (m, s) if m else fmt % s,
        ]
    )

def wait_for_transactions(pyc3l, transactions_hash, wait=5):
    print("Waiting for all transaction to be mined:")
    start = time.time()
    transactions_hash = transactions_hash.copy()
    while transactions_hash:
        for h, address in list(transactions_hash.items()):
            msg = f"  Transaction {h[0:8]} to {address[0:8]}"
            if pyc3l.getTransactionBlock(h) is not None:
                msg += " has been mined !"
                del transactions_hash[h]
            else:
                msg += " still not mined"
            print(f"{msg} ({pp_duration(time.time() - start)} elapsed)")
            time.sleep(wait)

    print("All transaction have been mined, bye!")

def pp_tx(tx, currency=True, raw=False):
    try:
        msg = ""
        abi_fn = tx.bc_tx.abi_fn
        bc_tx = tx.bc_tx
        caller = tx.bc_tx_data["from"][2:]
        if raw:
            msg += f"hash: {tx.hash}\n"
            msg += f"received:\n"
            msg += f"  ts: {tx.time_ts}\n"
            msg += f"  iso: {tx.time_iso or 'null'}\n"
            msg += f"pending: {'true' if tx.pending else 'false'}\n"
            msg += f"call:\n"
            msg += f"  caller: {bc_tx.data['from']}\n"
            msg += f"  contract:\n"
            msg += f"    hex: {bc_tx.data['to']}\n"
            if not abi_fn[0].startswith('['):
                msg += f"    abi: {abi_fn[0]}\n"
            msg += f"  fn:\n"
            msg += f"    hex: 0x{tx.bc_tx.fn}\n"
            if not abi_fn[1].startswith('<'):
                msg += f"    abi: {abi_fn[1]}\n"
            input_hex = tx.input_hex[10:]
            msg += f"  input:"
            while input_hex:
                msg += f"\n  - 0x{input_hex[:64]}"
                input_hex = input_hex[64:]
            msg += "\n"
            msg += "  gas:\n"
            msg += f"    limit:\n"
            msg += f"      hex: {bc_tx.gas}\n"
            msg += f"      dec: {bc_tx.gas_limit}\n"
            msg += f"    price:\n"
            msg += f"      hex: {hex(bc_tx.gas_price)}\n"
            msg += f"      dec:\n"
            msg += f"        wei: {bc_tx.gas_price_wei}\n"
            msg += f"        gwei: {bc_tx.gas_price_gwei}\n"
            return msg

        date_iso = dt_to_local_iso(tx.time)
        msg += click.style(f"{date_iso}", fg='cyan') + " "

        status = " " if tx.pending else click.style("✔", fg='green', bold=True)
        msg += click.style(f"{status:1s}", fg='white', bold=True) + " "

        msg += click.style(f"{caller[:6]:6s}‥", fg='magenta') + " "
        if currency:
            msg += click.style(f"{abi_fn[0]:>10}.{abi_fn[1]:22}", fg='bright_white') + " "
        else:
            assert abi_fn[0].startswith(tx.currency.symbol)
            msg += click.style(f"{abi_fn[1]:22}", fg='bright_white') + " "

        adds = [add[2:] if add.startswith('0x') else add for add in [tx.add1, tx.add2]]
        adds = ["" if add == "Admin" else
                add for add in adds]
        adds = [f"{add[:6]}‥" if add else "" for add in adds]
        adds = [
            click.style(f"{add:7s}", fg='magenta', dim=(add == "caller"))
            for add in adds
        ]
        msg += f"{adds[1]}"

        if tx.direction == 1:
            sign = "-"
        else:
            sign = "+"

        sent_formatted = f"{sign}{float(tx.sent) / 100:.2f}"
        msg += click.style(f"{sent_formatted:>9}", fg='green' if sign == "+" else 'red')
        if currency:
            msg += " " + click.style(f" {tx.currency.symbol:7}", fg='white', bold=True)
        if not tx.pending:
            block_info = click.style(tx.block.number, fg='yellow')
            msg += "  " + block_info
        return msg + "\n"
    except:
        import pprint
        pprint.pprint(tx.data)
        raise

def pp_bc_tx(bc_tx, raw=False, exclude=None):
    exclude = exclude or []
    msg = ""
    tx = bc_tx.full_tx
    try:
        abi_fn = bc_tx.abi_fn
        caller = bc_tx.data["from"][2:]
        if raw:
            if "hash" not in exclude:
                msg += f"hash: {bc_tx.hash}\n"
            if "block" not in exclude:
                msg += f"block:\n"
                msg += f"  hash: {bc_tx.blockHash}\n"
                msg += f"  number:\n"
                msg += f"    dec: {bc_tx.block.number_hex}\n"
                msg += f"    hex: {bc_tx.block.number}\n"
            if tx and tx.time and "received" not in exclude:
                msg += "received:\n"
                msg += f"  ts: {tx.time_ts or 'null'}\n"
                msg += f"  iso: {tx.time_iso or 'null'}\n"
            msg += f"pending: {'true' if tx.pending else 'false'}\n"
            msg += "call:\n"
            msg += f"  caller: {bc_tx.data['from']}\n"
            msg += "  contract:\n"
            msg += f"    hex: {bc_tx.data['to']}\n"
            if not abi_fn[0].startswith('['):
                msg += f"    abi: {abi_fn[0]}\n"
            if bc_tx.to is None:
                msg += "  fn:\n"
                msg += f"    hex: 0x{bc_tx.fn}\n"
                if not abi_fn[1].startswith('['):
                    msg += f"    abi: {abi_fn[1]}\n"
                input_hex = tx.input_hex
                msg += "  input_words:"
                while input_hex:
                    msg += f"\n  - 0x{input_hex[:64]}"
                    input_hex = input_hex[64:]
                msg += "\n"
            else:
                msg += "  fn:\n"
                msg += f"    hex: 0x{bc_tx.fn}\n"
                if not abi_fn[1].startswith('['):
                    msg += f"    abi: {abi_fn[1]}\n"
                input_hex = tx.input_hex[10:]
                msg += "  input_words:"
                while input_hex:
                    msg += f"\n  - 0x{input_hex[:64]}"
                    input_hex = input_hex[64:]
                msg += "\n"
            msg += "  gas:\n"
            msg += f"    limit:\n"
            msg += f"      hex: {bc_tx.gas}\n"
            msg += f"      dec: {bc_tx.gas_limit}\n"
            msg += f"    price:\n"
            msg += f"      hex: {hex(bc_tx.gas_price)}\n"
            msg += f"      dec:\n"
            msg += f"        wei: {bc_tx.gas_price_wei}\n"
            msg += f"        gwei: {bc_tx.gas_price_gwei}\n"
            return msg

        date_iso = dt_to_local_iso(tx.time) if tx and tx.is_cc_transaction else '????-??-?? ??:??:??+????'
        msg += click.style(f"{date_iso}", fg='black' if date_iso.startswith("?") else 'cyan') + " "

        status = "*" if bc_tx.blockNumber is None else " "
        msg += click.style(f"{status:1s}", fg='white', bold=True) + " "

        msg += click.style(f"{caller[:6]:6s}‥", fg='magenta') + " "

        msg += click.style(f"{abi_fn[0]:>10}.{abi_fn[1]:22}", fg='bright_white') + " "

        if bc_tx.to is None:
            msg += click.style(f"({bc_tx.data['to'][:6]}B)", fg='magenta') + " "
        if tx and tx.is_cc_transaction:
            adds = [add.lstrip("0x") for add in [tx.add1, tx.add2]]
            adds = ["" if add == "Admin" else
                    "caller" if add == caller else
                    add for add in adds]
            adds = [add[:6] for add in adds]
            adds = [
                click.style(f"{add:6s}"+ (" " if add == "caller" else "‥"),
                            fg='magenta', dim=(add == "caller"))
                for add in adds
            ]

            sent_formatted = f"{float(tx.sent) / 100:.2f}"
            msg += (
                f"{adds[0]} → {adds[1]}" +
                click.style(f"{sent_formatted:>9}", fg='bright_white') +
                click.style(f" {tx.currency.symbol if tx.currency else '???':7} ", fg='white', bold=True)
            )

        msg += "\n"
        return msg
    except:
        import pprint
        pprint.pprint(bc_tx.data)
        pprint.pprint(tx.data)
        raise

def pp_block(block, raw=False):
    msg = ""
    if raw:
        msg += f"hash: {block.data['hash']}\n"
        msg += "number:\n"
        msg += f"  dec: {block.number}\n"
        msg += f"  hex: {block.number_hex}\n"
        msg += f"collated:\n"
        msg += f"  ts: {block.collated_ts}\n"
        msg += f"  iso: {block.collated_iso}\n"
        indent="- "
    else:
        msg += (
            click.style(f"{block.number}", fg='yellow') + ": " +
            click.style(utc_ts_to_local_iso(int(block.data['timestamp'], 16)),
                        fg='cyan') + "\n")
        indent="  "

    if not block.bc_txs:
        if raw:
            msg += "txs: []\n"
        else:
            msg += f"{indent}" + click.style("No transaction in this block.", fg='black') + "\n"
    else:
        if raw:
            msg += "txs:\n"
        else:
            msg += "\n"
        for bc_tx in block.bc_txs:
            content = textwrap.indent(pp_bc_tx(bc_tx, raw, exclude=["block"]), ' ' * len(indent))
            content = indent + content.lstrip()
            msg += f"{content}"

    return msg.rstrip()


def pp_empty_seg_blocks(block_start, block_end) -> str:
    msg = ""
    if block_start.number == block_end.number:
        msg += (
            click.style(f"{block_start.number}", fg='yellow') + ": " +
            click.style(block_start.collated_iso, fg='cyan') +
            click.style(" empty block", fg='black'))
    else:
        msg += (
            click.style(f"{block_end.number}", fg='yellow') + "‥" +
            click.style(f"{block_start.number}", fg='yellow') + ": " +
            click.style(block_end.collated_iso, fg='cyan') + "‥" +
            click.style(block_start.collated_iso, fg='cyan') +
            click.style(f" {block_start.number - block_end.number} empty blocks", fg='black'))

    return msg.rstrip()


def pp_seg_blocks(block, count: int, raw: bool = False, skip_empty: bool = False):
    block_nb = block.number - 1
    non_empty_block = 0
    if not skip_empty:
        empty_seg = [None, None]
    first = True
    stop_condition = (
        (lambda : block_nb - block.number < count - 1) if raw and not skip_empty else
        (lambda : non_empty_block < count)
    )
    while block.number > 0 and stop_condition():
        block = block.prev
        empty = len(block.bc_txs) == 0
        if skip_empty and empty:
            continue
        if not empty:
            non_empty_block += 1
        if raw:
            print(("" if first else "---\n") + pp_block(block, raw))
            first = False
            continue

        if empty:
            if empty_seg[0] is None:
                empty_seg[0] = block
            empty_seg[1] = block
            print(end="\r")
            clear_line()
            print(pp_empty_seg_blocks(empty_seg[0], empty_seg[1]), end="\r")
            continue

        if not skip_empty and empty_seg[1] is not None:
            print(pp_empty_seg_blocks(empty_seg[0], empty_seg[1]))
            empty_seg = [None, None]
        print(pp_block(block, raw) + "\n")
    if empty:
        print()


def disable_echo():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    return old_settings


def enable_echo(old_settings):
    fd = sys.stdin.fileno()
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def get_terminal_width():
    size = shutil.get_terminal_size()
    return size.columns


def clear_line():
    sys.stdout.write('\033[K')


def hide_cursor():
    click.echo('\033[?25l', nl=False)  ## Hide the cursor


def show_cursor():
    click.echo('\033[?25h', nl=False)  ## Show the cursor


def protect_tty(f):
    def wrapper(*args, **kwargs):
        old_tty_settings = disable_echo()
        hide_cursor()
        try:
            return f(*args, **kwargs)
        except KeyboardInterrupt:
            pass
        finally:
            clear_line()
            enable_echo(old_tty_settings)
            show_cursor()
    return wrapper


def init_cache_dirs():
    """Create the cache directory if it doesn't exist and returns it's path."""

    if os.environ.get("PYC3L_CACHE_DIR"):
        PYC3L_CACHE_DIR = os.environ.get("PYC3L_CACHE_DIR")
    else:
        if os.geteuid() == 0:
            PYC3L_CACHE_DIR = "/var/cache/pyc3l"
        else:
            PYC3L_CACHE_DIR = os.path.expanduser("~/.cache/pyc3l")

    if not os.path.exists(PYC3L_CACHE_DIR):
        os.makedirs(PYC3L_CACHE_DIR)
    return PYC3L_CACHE_DIR
