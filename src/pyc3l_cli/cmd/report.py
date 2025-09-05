#!/usr/bin/env python

import click

import sqlite3
import time

from sact.epoch import Time, TzLocal
import os
import re
import sys
import pickle
import itertools
from collections import defaultdict

from typing import Optional, List

from pyc3l import Pyc3l, store
from .. import common


spinner = "⣷⣯⣟⡿⢿⣻⣽⣾"



def process_multiple_option(value):
    new_value = set()
    for v in value:
        if "," in v:
            new_value.update(v.split(","))
        else:
            new_value.add(v)
    return new_value


def click_process_multiple_options():
    ctx = click.get_current_context()
    multiple_options = (
        param.name
        for param in ctx.command.params
        if isinstance(param, click.Option) and param.multiple
    )
    for option in multiple_options:
        value = ctx.params.get(option)
        if value:
            ctx.params[option] = process_multiple_option(value)
    return ctx.params


def check_normalize_currencies(pyc3l, currencies):
    all_currencies = set(pyc3l.ipfs_endpoint.config.get("list.json").values())

    if currencies:
        new_currency = set()
        for c in currencies:
            if not re.fullmatch("^[a-zA-Z-_]+$", c):
                raise click.ClickException(
                    f"Invalid argument {c!r} for currency (only letters, - and _ are allowed)"
                )
            found = False
            for r in all_currencies:
                if re.fullmatch("^((la|le|monnaie)-?)?" + c.lower(), r.lower()):
                    found = True
                    new_currency.add(r)
                    break
            if not found:
                raise click.ClickException(
                    f"Provided currency {c!r} is not known, please use one of:\n  - %s"
                    % "\n  - ".join(all_currencies)
                )
        currencies = new_currency
    else:
        currencies = all_currencies

    return currencies


def get_block_nb_from_idx(current_ranges, idx):
    for s, e in current_ranges:
        if idx <= e - s:
            return s + idx
        idx -= e - s + 1
    return None


def get_idx_from_block_nb(current_ranges, block_nb):
    """Return the index of the block in the current_ranges

    Example:

        >>> get_idx_from_block_nb([(5, 6)], 5)
        0

    As if we consider all numbers from 5 to 6 (ie: 5, 6), the index of 5 is 0.

    ``current_ranges`` is a list of segments of block numbers, ie:
    [(1, 5), (7, 10)], and this function will return the index of the
    block number in the list of all block numbers in the segments:

        >>> get_idx_from_block_nb([(1, 5), (7, 10)], 1)
        0

    In the collated segments (1, 5) and (7, 10), the block number 1 is
    the first block.

        >>> get_idx_from_block_nb([(1, 5), (7, 10)], 5)
        4
        >>> get_idx_from_block_nb([(1, 5), (7, 10)], 7)
        5

    If the block number is not in the current_ranges, it will return the
    index of the greater block number in the current_ranges being less
    than the block number looked for. This means:

        >>> get_idx_from_block_nb([(1, 5), (7, 10)], 6)
        4
        >>> get_idx_from_block_nb([(1, 5), (7, 10)], 11)
        9
        >>> get_idx_from_block_nb([(1, 5), (7, 10)], 0)
        >>> get_idx_from_block_nb([], 0)
        >>>


    """
    idx = 0
    if len(current_ranges) == 0:
        return None
    for s, e in current_ranges:
        if block_nb < s:
            return idx - 1 if idx > 0 else None
        if s <= block_nb <= e:
            return idx + block_nb - s
        idx += e - s + 1
    return idx


def date_block_picker(pyc3l, start_date, end_date):
    start_time = time.time()

    assert start_date <= end_date

    def get_spinner_char():
        return click.style(
            f"{spinner[int((time.time() - start_time) / 0.2) % len(spinner)]}",
            fg="green",
            bold=True,
        )

    def block_picker(ranges, block_dates):
        ## current_ranges is the list of ranges of blocks not already parsed
        current_ranges = ranges
        empty_seg = [None, None]
        block = None

        ## max_idx is the dichotomy index of the block in current_ranges to consider
        ## as the starting block
        max_idx = None

        ## if we have block_dates, produce block segment restriction where
        ## the start block should be

        if block_dates:
            start_boundary = 0
            start_boundary_follower = None
            end_boundary = None
            sorted_block_dates = sorted(block_dates.items())
            for i, (b, d) in enumerate(sorted_block_dates):
                ## As start_date < end_date, we'll find first start_boundary.
                if start_boundary == 0:  ## not set yet
                    if d >= start_date:  ## and found first block above start_date
                        start_boundary = sorted_block_dates[i - 1][0]
                        start_boundary_follower = b
                    else:
                        continue
                if end_boundary is None:  ## not set yet
                    if d > end_date:      ## and found first block above end_date
                        end_boundary = b
                        break

            if end_boundary is None:
                end_boundary = current_ranges[-1][1]
            ## Block segment restriction to current_ranges (
            if (start_boundary > current_ranges[0][0] or
                   end_boundary < current_ranges[-1][1]):
                current_ranges = store.ranges_intersection(
                    current_ranges, [(start_boundary, end_boundary)]
                )
                if start_boundary_follower is not None:
                    max_idx = get_idx_from_block_nb(current_ranges, start_boundary_follower)
                    if max_idx is None:
                        max_idx = -1

        ## first stage, use dichotomy to find the first block
        while True:
            if max_idx is None:
                count_todo = sum(e - s + 1 for s, e in current_ranges)
            else:
                count_todo = max_idx + 1
            if count_todo == 0:
                break

            common.clear_line()
            # print(
            #     get_spinner_char() + " "
            #     f"  Still {count_todo} blocks candidate to check (before founding starting block).",
            #     end="\r",
            #     file=sys.stderr,
            # )
            if max_idx is None:
                max_idx = count_todo - 1
            next_idx = max_idx // 2
            next_block_nb = get_block_nb_from_idx(current_ranges, next_idx)
            if block is None:
                msg_jump = "first jump"
            else:
                jump = next_block_nb - block.number
                if jump < 0:
                    msg_jump = f"back {-jump} blocks"
                else:
                    msg_jump = f"forward {jump} blocks"
            common.clear_line()
            block = pyc3l.BlockByNumber(next_block_nb)
            print(
                "  " + click.style("‥", fg="yellow") + " " +
                click.style("jump to", fg="black") + " " +
                click.style(f"{next_block_nb}", fg="yellow") + " " +
                click.style(f"{block.collated_iso}", fg="cyan") + " " +
                click.style("by", fg="black") + " " +
                click.style(msg_jump, fg="black"),
                file=sys.stderr,)
            yield block
            print(
                get_spinner_char()
                + " "
                + click.style(f"{block.number}", fg="yellow")
                + ": "
                + click.style(f"{block.collated_iso}", fg="cyan"),
                end="\r",
                file=sys.stderr,
            )
            if next_idx == 0:
                break
            max_idx_block_nb = get_block_nb_from_idx(current_ranges, max_idx)
            current_range_to_remove = []
            if block.collated_ts >= start_date and next_block_nb > current_ranges[0][0]:
                current_range_to_remove.append(
                    (current_ranges[0][0], next_block_nb - 1)
                )
            if next_block_nb < current_ranges[-1][1]:
                current_range_to_remove.append(
                    (next_block_nb + 1, current_ranges[-1][1])
                )
            current_ranges = store.ranges_intersection(
                current_range_to_remove,
                current_ranges,
            )
            max_idx = get_idx_from_block_nb(current_ranges, max_idx_block_nb)
            if max_idx is None:
                break
            if block.collated_ts >= start_date:
                max_idx = next_idx - 1
            if max_idx <= 1:
                break
            common.clear_line()
            print(
                get_spinner_char() + " "
                f"  still {max_idx} blocks to check for possible starting block.",
                end="\r",
                file=sys.stderr,
            )
        for block_nb in itertools.chain(
            *(range(r[0], r[1] + 1) for r in current_ranges)
        ):
            block = pyc3l.BlockByNumber(block_nb)
            if block.collated_ts > end_date:
                break

            empty = len(block.bc_txs) == 0
            if empty and (
                empty_seg[1] is None or (empty_seg[1].number + 1) == block.number
            ):
                if empty_seg[0] is None:
                    empty_seg[0] = block
                empty_seg[1] = block
                print(end="\r", file=sys.stderr)
                common.clear_line()
                print(
                    get_spinner_char()
                    + " "
                    + common.pp_empty_seg_blocks(empty_seg[1], empty_seg[0]),
                    end="\r",
                    file=sys.stderr,
                )
            elif empty_seg[1] is not None:
                common.clear_line()
                print(
                    get_spinner_char()
                    + " "
                    + common.pp_empty_seg_blocks(empty_seg[1], empty_seg[0]),
                    end="\r",
                    file=sys.stderr,
                )
                empty_seg = [None, None]

            yield block

    return block_picker


def load_currencies_data(pyc3l, tx_stores, range_date, range_block):
    start_block, end_block = range_block
    if start_block > end_block:
        raise ValueError(f"Invalid block range {start_block} > {end_block}")
    start_date, end_date = range_date
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError(f"Invalid date range {start_date} > {end_date}")

    start_date_ts = start_date.timestamp if start_date is not None else 0
    end_date_ts = end_date.timestamp if end_date is not None else Time.now().timestamp

    full_block_ranges = store.ranges_intersection(
        *[tx_store.current_ranges() for tx_store in tx_stores.values()]
    )
    full_block_dates = store.curate_block_date(
        {b: d for tx_store in tx_stores.values() for b, d in tx_store.current_block_dates.items()},
        full_block_ranges,
    )
    missing_block_ranges = store.range_remove((start_block, end_block), full_block_ranges)
    if start_date is not None:
        block_picker = date_block_picker(pyc3l, start_date_ts, end_date_ts)
    else:
        block_picker = lambda ranges, block_dates=None: (
            pyc3l.BlockByNumber(b)
            for r in ranges
            for b in range(*r)
        )
    for block in block_picker(missing_block_ranges, full_block_dates):

        block_tx_stores = [
            tx_store
            for tx_store in tx_stores.values()
            if not tx_store.has_block(block.number)
        ]
        for tx in block.bc_txs:
            save_icon = click.style("⭳", fg="green")
            full_tx = tx.full_tx
            if full_tx is None:
                raise ValueError(f"Unexpected transaction for tx {tx.hash}")
            if not full_tx.is_cc_transaction:
                save_icon = click.style("-", fg="black")
            else:
                tx_currency = tx.currency
                ## XXXvlab: there are some transactions with no currency
                ## (ie: 0xc13e95a498a24e9272236bcf32a5ae10826044626980b8ec98c8038b2ede9941)
                tx_currency_name = tx_currency.name if tx_currency is not None else None
                if tx_currency_name not in tx_stores:
                    save_icon = click.style("x", fg="red")
                else:
                    tx_store = tx_stores[tx_currency.name]
                    abi_fn = tx.abi_fn
                    try:
                        data = {
                            "hash": tx.hash,
                            "block": block.number,
                            "received_at": int(full_tx.received_at.timestamp()),
                            "caller": tx.data["from"],
                            "contract": tx.data["to"],
                            "contract_abi": abi_fn[0],
                            "type": full_tx.type,
                            "sender": full_tx.addr_from,
                            "receiver": full_tx.addr_to,
                            "amount": full_tx.sent,
                            "fn": tx.fn,
                            "fn_abi": abi_fn[1],
                            "status": "",
                        }
                    except Exception:
                        click.echo(f"Error while processing tx {tx.hash}", err=True)
                        raise
                    try:
                        tx_store.add_tx(data)
                    except sqlite3.IntegrityError as e:
                        if e.args[0] == "UNIQUE constraint failed: transactions.hash":
                            ## we need to check that our values are the same than in db
                            cols = tuple(data.keys())
                            tx_store.execute(
                                f"SELECT {','.join(cols)} FROM transactions WHERE hash = ?", (tx.hash,)
                            )
                            db_data = tx_store._sqlite3_cursor.fetchone()
                            db_data = dict(zip(cols, db_data))
                            diff_cols = [k for k in cols if db_data[k] != data[k]]
                            if not diff_cols:
                                continue
                            click.echo(
                                f"Error while adding tx {tx.hash} to store {tx_store.currency}",
                                err=True,
                            )
                            for k in diff_cols:
                                click.echo(
                                    f"  {k}: {db_data[k]} (DB) != {data[k]} (NEW)",
                                    err=True,
                                )

                        raise
                    except Exception:
                        click.echo(
                            f"Error while adding tx {tx.hash} to store {tx_store.currency}",
                            err=True,
                        )
                        raise

            common.clear_line()
            click.echo(
                save_icon
                + " "
                + click.style(f"{block.number}", fg="yellow")
                + " "
                + common.pp_bc_tx(tx),
                nl=False,
                err=True,
            )

        for tx_store in block_tx_stores:
            tx_store.commit()
            tx_store.add_block(block.number, block.collated_ts)


def option_get_safe_wallets(safe_wallets_file):
    if not safe_wallets_file:
        safe_wallets_file = os.path.join(os.path.expanduser("~"), ".config", "pyc3l", "safe_wallets.yml")
    safe_wallets = {}
    if os.path.exists(safe_wallets_file):

        ## is a yaml file
        import yaml

        with open(safe_wallets_file, "r") as f:
            safe_wallets = yaml.safe_load(f)

    ## ensure safe wallets are tuples
    for c, addrs in safe_wallets.items():
        if isinstance(addrs, str):
            safe_wallets[c] = (addrs,)
            continue
        if isinstance(addrs, list):
            safe_wallets[c] = tuple(addrs)
            continue
        if isinstance(addrs, dict):
            safe_wallets[c] = tuple(addrs.values())
            continue
        raise ValueError(f"Invalid safe wallet format for currency {c}")

    return safe_wallets


def option_get_address_groups(address_group_file):
    if not address_group_file:
        address_group_file = os.path.join(os.path.expanduser("~"), ".config", "pyc3l", "address_groups.yml")
    address_groups = defaultdict(lambda: defaultdict(list))
    if os.path.exists(address_group_file):

        ## is a yaml file
        import yaml
        address_groups_content = {}
        with open(address_group_file, "r") as f:
            address_groups_content = yaml.safe_load(f)
        for c, groups in address_groups_content.items():
            for g, addrs in groups.items():
                if isinstance(addrs, str):
                    address_groups[c][g] = list((addrs,))
                    continue
                if isinstance(addrs, list):
                    address_groups[c][g] = addrs[:]
                    continue
                if isinstance(addrs, dict):
                    address_groups[c][g] = list(addrs.values())
                    continue
                raise ValueError(f"Invalid address group format for currency {c} and group {g}")

    return address_groups

@click.command()
@click.option("-e", "--endpoint", help="Force com-chain endpoint.")
@click.option(
    "-S",
    "--start-block",
    type=str,
    help="Add constraint on first block to consider. `--start-date` can constrain further",
    default=1,
)
@click.option(
    "-E",
    "--end-block",
    type=str,
    help="Add constraint on last lock to consider. `--end-date` can constrain further",
    default=0,
)
@click.option(
    "-s",
    "--start-date",
    type=str,
    help="starting date of report. `--start-block` can constrain the start date further",
    default=None,
)
@click.option(
    "--end-date",
    type=str,
    help="ending date of report. `--end-block` can constrain the end date further",
    default=None,
)
@click.option(
    "--safe-wallets-file",
    type=str,
    help="Path to safe-wallet file, instead of list from ipfs",
)
@click.option("-r", "--raw", is_flag=True, help="Print raw values")
@click.option("-c", "--currency", multiple=True,
              help="Filter by currency (can be repeated, or multi-valued using comma as separator)")
@click.option("-g", "--granularity", help="Granularity of the output")
@click.option("-G", "--address-group-file", help="Address group file for each currency")
def run(
    start_block: Optional[str],
    end_block: Optional[str],
    endpoint: Optional[str],
    raw: bool,
    currency: List[str],
    start_date: Optional[str],
    end_date: Optional[str],
    safe_wallets_file: Optional[str],
    address_group_file: Optional[str],
    granularity: Optional[str],
):
    params = click_process_multiple_options()
    if start_date:
        start_date = Time(start_date, hint_src_tz=TzLocal())
    if end_date:
        end_date = Time(end_date, hint_src_tz=TzLocal())
    pyc3l = Pyc3l(endpoint)

    ## check and normalize currencies
    params["currency"] = check_normalize_currencies(pyc3l, params["currency"])
    start_block = (
        int(start_block, 16) if start_block.startswith("0x") else int(start_block)
    )
    end_block = (
        int(params["end_block"], 16)
        if params["end_block"].startswith("0x")
        else int(params["end_block"])
    )
    if end_block == 0:
        end_block = pyc3l.getBlockNumber()
    if safe_wallets_file:
        safe_wallets = option_get_safe_wallets(safe_wallets_file)
    else:
        safe_wallets = {
            c: pyc3l.Currency(c).technicalAccounts
            for c in params["currency"]
        }
    address_groups = option_get_address_groups(address_group_file)
    ## make safe wallets a "national currency" address group
    for c in params["currency"]:
        address_groups[c]["national currency"].extend(safe_wallets.get(c, []))

    tx_stores = {c: store.TxStore(pyc3l, c, safe_wallets.get(c)) for c in params["currency"]}

    ## fill tx_stores sqlite databases and display progress on stderr

    if not raw:
        global load_currencies_data
        load_currencies_data = common.protect_tty(load_currencies_data)

    load_currencies_data(pyc3l, tx_stores, (start_date, end_date), (start_block, end_block))

    ## Let's output some stats thanks to sqlite databases

    groups_currency = defaultdict(lambda: {"national currency", None})
    for c in params["currency"]:
        address_group_currency = address_groups.get(c,{})
        groups_currency[c] |= address_group_currency.keys()

    groups_complete_set = {g for c, groups in groups_currency.items() for g in groups}
    groups_vectors = list(itertools.product(groups_complete_set, repeat=2))
    groups_vectors.remove(("national currency", "national currency"))

    header_printed = False
    headers = [
        "currency",
        "date",
        # "topup_total",
        # "topup_nb",
        # "transfer_total",
        # "transfer_nb",
        # "reconv_total",
        # "reconv_nb",
        # "topup_minus_reconv_total",
    ]
    for groups in groups_vectors:
        group_name = '->'.join(["%s" % g for g in groups])
        if group_name == "national currency->None":
            group_name = "topup"
        elif group_name == "None->national currency":
            group_name = "reconv"
        elif group_name == "None->None":
            group_name = "transfer"
        group_name.replace("national currency", "NC")
        headers += [
            f"{group_name}_total",
            f"{group_name}_nb",
        ]

    headers_align = {
        "currency": "left",
        "date": "left",
        "_total": "right",
        "_nb": "right",
        "topup_minus_reconv_total": "right",
    }
    values_conversion = {
        "_total": lambda v: round(v / 100, 2)
    }
    if raw:
        headers_title = {
            "currency": "Currency",
            "date": "Date",
            "topup_total": "Topup",
            "topup_nb": "#",
            "transfer_total": "Transfer",
            "transfer_nb": "#",
            "reconv_total": "Reconv",
            "reconv_nb": "#",
            "unit": "",
        }
        values_format = { ## default is "%s"
            "_total": "%.2f",
            "_nb": "%d",
        }
    else:
        values_format = { ## default is "%s"
            "_total": "  %.2f",
            "_nb": " %d |",
        }
        headers_title = {
            "currency": "Currency",
            "date": "Date",
            "topup_total": "Topup",
            "topup_nb": "# |",
            "transfer_total": "Transfer",
            "transfer_nb": "# |",
            "reconv_total": "Reconv",
            "reconv_nb": "# |",
            "unit": "",
        }
    values_style = {
        "date": {"fg": "cyan"},
        "_total": {"fg": "white"},
        "_nb": {"fg": "black"},
        "unit": {"fg": "white", "bold": True},
    }
    values_type = { ## default is str
        "_total": float,
        "_nb": int,
    }
    join_char = "," if raw else " "

    msgs = [
        [currency] + list(r)
        for currency, tx_store in tx_stores.items()
        for r in tx_store.records(
                granularity=granularity or "%Y-%m",
                start_date=start_date or None,
                end_date=end_date or None,
                address_groups=address_groups.get(currency, {}),
                pledge_group="national currency"
        )
    ]

    ## transform msgs to vector list
    new_msgs = []
    for currency, group_unit, matrix in msgs:
        new_msg = [currency, group_unit]
        for src, dst in groups_vectors:
            for k in ["total", "nb"]:
                new_msg.append(matrix[src][dst][k])
        new_msgs.append(new_msg)

    msgs = new_msgs

    ## add unit if not raw
    if not raw:
        currency_unit = {
            c: pyc3l.Currency(c).symbol for c in params["currency"]
        }
        insert_todo = [h for h in headers if h.endswith("_total")]
        while insert_todo:
            h = insert_todo.pop()
            i = headers.index(h)
            for msg in msgs:
                currency = msg[headers.index("currency")]
                unit = currency_unit.get(currency)
                msg.insert(i + 1, unit)
            headers.insert(i + 1, "unit")

    def get_value(dct, header, default=None):
        for k, v in dct.items():
            if k.startswith('_') and header.endswith(k):
                return v
            if k == header:
                return v
        return default

    ## conversion
    msgs = [
        [
            get_value(values_conversion, header, lambda v: v)(msg[i])
            for i, header in enumerate(headers)
        ]
        for msg in msgs
    ]

    ## format msgs
    msgs = [
        [
            get_value(values_format, header, "%s") % msg[i]
            for i, header in enumerate(headers)
        ]
        for msg in msgs
    ]

    length_fields = {}
    if not raw:
        length_fields = {
            header: max(len(msg[i]) for msg in msgs)
            for i, header in enumerate(headers)
        }
        for header, size in length_fields.items():
            length_fields[header] = max(len(headers_title.get(header, header)), size)

    for msg in msgs:
        heads = headers[:]
        currency = msg[heads.index("currency")]
        if len(params["currency"]) == 1:
            del msg[heads.index("currency")]
            heads.remove("currency")
        head_titles = [headers_title.get(header, header) for header in heads]
        if not raw:
            ## apply size and alignement
            msg = [
                "%%-%ds" % length_fields[header] % msg[i] if get_value(headers_align, header, "left") == "left" else
                "%%%ds" % length_fields[header] % msg[i]
                for i, header in enumerate(heads)
            ]
            ## same for head_titles
            head_titles = [
                "%%-%ds" % length_fields[header] % head_titles[i] if get_value(headers_align, header, "left") == "left" else
                "%%%ds" % length_fields[header] % head_titles[i]
                for i, header in enumerate(heads)
            ]
            ## apply style
            msg = [
                click.style(msg[i], **get_value(values_style, header, {}))
                for i, header in enumerate(heads)
            ]
            len_heads = sum(len(h) for h in head_titles)
            head_titles = [
                click.style(h, fg="black", bold=True)
                for h in head_titles
            ]
        if not header_printed:
            print(join_char.join(head_titles))
            if not raw:
                print("-" * (len_heads + len(heads) - 1))
            header_printed = True
        print(join_char.join([str(m) for m in msg]))


if __name__ == "__main__":
    run()
