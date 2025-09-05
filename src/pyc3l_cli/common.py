
from pyc3l.lib.dt import utc_ts_to_local_iso, dt_to_local_iso
from pyc3l.ApiHandling import APIErrorNoMessage


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
        try:
            bc_tx = tx.bc_tx
        except APIErrorNoMessage as e:
            return f""

        abi_fn = bc_tx.abi_fn
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

        if tx.time:
            date_iso = dt_to_local_iso(tx.time)
            msg += click.style(f"{date_iso}", fg='cyan') + " "
        else:
            msg += click.style("????-??-?? ??:??:??", fg='black') + " "


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
            if "block" not in exclude and bc_tx.block is not None:
                msg += f"block:\n"
                msg += f"  hash: {bc_tx.block.hash}\n"
                msg += f"  number:\n"
                msg += f"    dec: {bc_tx.block.number_hex}\n"
                msg += f"    hex: {bc_tx.block.number}\n"
            if tx and tx.time and "received" not in exclude:
                msg += "received:\n"
                msg += f"  ts: {tx.time_ts or 'null'}\n"
                msg += f"  iso: {tx.time_iso or 'null'}\n"
            msg += f"pending: {'true' if tx.pending else 'false'}\n"
            msg += "call:\n"
            if "caller" not in exclude:
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

        if "status" not in exclude:
            status = "*" if bc_tx.blockNumber is None else " "
            msg += click.style(f"{status:1s}", fg='white', bold=True) + " "

        if "caller" not in exclude:
            msg += click.style(f"{caller[:6]:6s}‥", fg='magenta') + " "

        msg += click.style(f"{abi_fn[0]:>10}.{abi_fn[1]:22}", fg='bright_white') + " "

        if bc_tx.to is None:
            msg += click.style(f"({int(len(bc_tx.data['input'][2:])/2)}B)", fg='magenta') + " "
        if tx and tx.is_cc_transaction:
            adds = [add[2:] if add.startswith('0x') else add for add in [tx.add1, tx.add2]]
            adds = ["" if add == "Admin" else
                    "caller" if add == caller else
                    add for add in adds]
            adds = [add[:6] for add in adds]
            adds = [
                click.style(f"{add:6s}"+ (" " if add in ("caller", "") else "‥"),
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


def pp_address(add, raw=False):
    if raw:
        return add
    add = add[2:] if add.startswith('0x') else add
    add = add[:6]
    return click.style(f"{add:6s}" + "‥", fg='magenta')



def pp_block(block, raw=False):
    msg = ""
    if raw:
        msg += f"hash: {block.hash}\n"
        msg += "number:\n"
        msg += f"  dec: {block.number}\n"
        msg += f"  hex: {block.number_hex}\n"
        msg += "collated:\n"
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


def pp_account(account, raw=False, exclude=None, nb_tx=None):
    if nb_tx is None:
        nb_tx = 0 if raw else 5
    exclude = exclude or []
    msg = ""
    if raw:
        msg += f"hash: {account.address}\n"
        msg += f"nonce:\n"
        msg += f"  hex: {account.nonce_hex}\n"
        msg += f"  dec: {account.nonce_dec}\n"
        msg += f"balance:\n"
        msg += f"  eth: {account.eth_balance}\n"
        msg += f"  gwei: {account.eth_balance_gwei}\n"
        msg += f"  wei: {account.eth_balance_wei}\n"
        msg += "wallet:\n"
        msg += "  currency:\n"
        msg += f"    name: {account.currency.name}\n"
        msg += f"    symbol: {account.currency.symbol}\n"
        msg += f"  status:\n"
        for label in ["active", "owner"]:
            msg += f"    {label}: {str(getattr(account, label)).lower()}\n"
        msg += f"    role:\n"
        msg += f"      value: {account.type}\n"
        msg += f"      label: {account.role}\n"
        msg += "  balance:\n"
        msg += f"    total: {account.globalBalance:.2f}\n"
        msg += f"    accounts:\n"
        msg += f"      nant: {account.nantBalance:.2f}\n"
        msg += "      cm:\n"
        msg += f"        current: {account.cmBalance:.2f}\n"
        msg += f"        min: {account.cmLimitMin:.2f}\n"
        msg += f"        max: {account.cmLimitMax:.2f}\n"
        for label in [
            "allowances",
            "requests",
            "my_requests",
            "delegations",
            "my_delegations",
            "accepted_requests",
            "rejected_requests",
        ]:
            lst = getattr(account, label)
            if len(lst) == 0:
                msg += f"  {label}: []\n"
                continue
            msg += f"  {label}:\n"
            for address, amount in lst.items():
                msg += f"  - {{address: {address}, amount: {amount:.2f}}}\n"
    else:
        msg = ""
        currency = account.currency
        symbol = currency.symbol
        print(click.style("Address:", bold=True) + " " +
              click.style(f"0x{account.address}", fg='magenta'), end=" ")
        if account.active:
            msg += click.style("ACTIVE", fg='green') + " "
        else:
            msg += click.style("DISABLED", fg='red') + " "
        ## Account type 4 = Property Admin, 3 = Pledge Admin, 2 = Super Admin, 1 = Business, 0 = Personal
        role_color = 'blue' if account.role.endswith("admin") else \
            'yellow' if account.role == 'business' else \
            'cyan'
        msg += click.style(
            "".join(word.capitalize()
                    for word in account.role.split(" ")
                    ), fg=role_color) + " "

        if account.isOwner:
            msg += click.style("OWNER", fg='white', bold=True)
        msg += "\n"

        msg += f"  Nonce: {account.nonce_hex} ({account.nonce_dec})\n"
        msg += f"  Balance: {account.globalBalance:10.2f} {symbol}\n"
        msg += f"    Nant : {account.nantBalance:10.2f} {symbol}\n"
        msg += (
            f"    CM   : {account.cmBalance:10.2f} {symbol} "
            f"({account.cmLimitMin} to {account.cmLimitMax} {symbol})\n"
        )
        msg += f"  ETH balance = {account.eth_balance_wei} Wei (={account.eth_balance} Ether)\n"

        for label in [
            "allowances",
            "requests",
            "my_requests",
            "delegations",
            "my_delegations",
            "accepted_requests",
            "rejected_requests",
        ]:
            lst = getattr(account, label)
            if len(lst) == 0:
                continue
            msg += f"  {label}:\n"
            for address, amount in lst.items():
                msg += f"    - from {address} for {amount} {symbol}\n"
        has_content = False
        msg += click.style(f"Last transactions in {currency.name}:", fg='white', bold=True) + "\n"
        other_currencies = set()
        notes = []
        count_tx = 0
        for idx, tx in enumerate(account.transactions):
            ## tx here is incomplete (doesn't contain always the bc_tx), and
            ## the currency given there could not be the one advertised in
            ## current list of currencies.

            tx_cur_name = tx.currency.name
            ## By launching the next line, we force the resolution of bc_tx and
            ## switch to using the contract info to reverse infer the currency

            ## yeahh..

            tx_msg = pp_tx(tx, currency=True, raw=False)
            tx_cur = tx.currency
            if tx_cur.name != tx_cur_name:
                note = ("inconsistent_currency_name", tx_cur.name, tx_cur_name)
                if note not in notes:
                    notes.append(note)
                note_idx = notes.index(note)
                tx_msg = tx_msg[0:-1] + click.style(f" [{note_idx}]", fg='red') + "\n"
            if tx_cur.name != currency.name:
                other_currencies.add(tx_cur)
                continue
            has_content = True

            msg += "  " + tx_msg
            count_tx += 1
            if count_tx + 1 >= nb_tx:
                break
        if notes:
            msg += click.style("  Notes:", fg='white', bold=True) + "\m"
            for idx, note in enumerate(notes):
                if note[0] == "inconsistent_currency_name":
                    msg += (click.style(f"    [{idx}]", fg='red') +
                            f" inconsistent currency name between " +
                            f"transaction info {note[1]!r} and contract {note[2]!r}") + "\n"
        if not has_content:
            msg += "    No transactions found in this currency.\n"
        if len(other_currencies) > 0:
            msg += "  Other transactions exist in currencies:\n"
            for cur in other_currencies:
                msg += f"    - {cur}\n"

    return msg

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
