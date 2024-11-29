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

from typing import Optional, List

from pyc3l import Pyc3l
from .. import common


spinner = "⣷⣯⣟⡿⢿⣻⣽⣾"


def range_remove(target_range, current_block_ranges):
    """Return the ranges (s, e) of missing blocks in the range [start, end]

    >>> range_remove((1, 10), [(1, 5), (7, 12)])
    [(6, 6)]
    >>> range_remove((1, 10), [(0, 3), (7, 8)])
    [(4, 6), (9, 10)]
    >>> range_remove((1, 10), [(0, 10)])
    []
    >>> range_remove((1, 10), [(6, 6)])
    [(1, 5), (7, 10)]

    """
    (start, end) = target_range
    ## find missing blocks
    missing_block_ranges = []
    for s, e in current_block_ranges:
        if e < start:
            continue
        if start < s:
            if end < s:
                missing_block_ranges.append((start, end))
                return missing_block_ranges
            ## start < s <= end
            missing_block_ranges.append((start, s - 1))
            if e > end:
                return missing_block_ranges
            ## start < s <= e <= end
            start = e + 1
            continue
        ## s <= start <= e
        start = e + 1
        continue
    if start <= end:
        missing_block_ranges.append((start, end))
    return missing_block_ranges


def range_union(*ranges):
    """Return the smallest range union of the given ranges

    >>> range_union()
    []
    >>> range_union((1, 5))
    [(1, 5)]
    >>> range_union((1, 5), (7, 10))
    [(1, 5), (7, 10)]
    >>> range_union((1, 5), (6, 10))
    [(1, 10)]
    >>> range_union((1, 5), (3, 10))
    [(1, 10)]
    >>> range_union((1, 5), (5, 7))
    [(1, 7)]
    >>> range_union((1, 5), (6, 7))
    [(1, 7)]


    """
    ranges = sorted(ranges)
    union = []
    if not ranges:
        return union
    (start, end) = ranges[0]
    for s, e in ranges[1:]:
        if e < start:
            continue
        if s <= end + 1:
            end = max(end, e)
            continue
        union.append((start, end))
        (start, end) = (s, e)
    union.append((start, end))
    return union


def range_intersection(*ranges):
    """Return the smallest range intersection of the given ranges

    >>> range_intersection()
    []
    >>> range_intersection((1, 5))
    [(1, 5)]
    >>> range_intersection((1, 5), (7, 10))
    []
    >>> range_intersection((1, 5), (6, 10))
    []
    >>> range_intersection((1, 5), (3, 10))
    [(3, 5)]
    >>> range_intersection((1, 5), (5, 7))
    [(5, 5)]
    >>> range_intersection((1, 5), (6, 7))
    []

    """
    ranges = sorted(ranges)
    intersection = []
    if len(ranges) == 0:
        return intersection
    if len(ranges) == 1:
        return ranges
    (start, end) = ranges[0]
    for s, e in ranges[1:]:
        if e < start:
            continue
        if s <= end:
            intersection.append((max(start, s), min(end, e)))
            (start, end) = (max(start, s), min(end, e))
    return intersection


def ranges_intersection_2(ranges1, ranges2):
    """Return the smallest range intersection of the given ranges

    >>> ranges_intersection_2([(1, 5)], [(1, 5)])
    [(1, 5)]
    >>> ranges_intersection_2([(1, 5)], [(6, 10)])
    []
    >>> ranges_intersection_2([(1, 5)], [(3, 10)])
    [(3, 5)]
    >>> ranges_intersection_2([(1, 5)], [(5, 7)])
    [(5, 5)]
    >>> ranges_intersection_2([(1, 5)], [(6, 7)])
    []
    >>> ranges_intersection_2([], [(6, 7)])
    []
    >>> ranges_intersection_2([], [])
    []
    >>> ranges_intersection_2([(1, 5), (7, 10)], [(3, 10)])
    [(3, 5), (7, 10)]

    """
    intersection = []
    for r1 in ranges1:
        for r2 in ranges2:
            if r1[1] < r2[0] or r1[0] > r2[1]:
                continue
            intersection.append((max(r1[0], r2[0]), min(r1[1], r2[1])))
    return intersection


def ranges_intersection(*ranges):
    """Return the smallest range intersection of the given ranges

    >>> ranges_intersection([(1, 5), (7, 10)], [(3, 10)], [(2, 6)])
    [(3, 5)]
    >>> ranges_intersection([(1, 5), (7, 10)], [(3, 10)], [(5, 8)], [(1, 10)])
    [(5, 5), (7, 8)]
    >>> ranges_intersection()
    []
    >>> ranges_intersection([(1, 5)])
    [(1, 5)]
    >>> ranges_intersection([(1, 5)], [(7, 10)])
    []

    """
    if not ranges:
        return []
    intersection = ranges[0]
    for r in ranges[1:]:
        intersection = ranges_intersection_2(intersection, r)
    return intersection


def curate_block_date(block_dates, ranges):
    """Return the block-date dict curated for the given ranges

    It will remove all key/value where the key is not in one of
    the boundary of a range.

    >>> curate_block_date({}, [])
    {}
    >>> curate_block_date({}, [(1, 3), (5, 5)])
    {}
    >>> curate_block_date({1: 1}, [(1, 3), (5, 5)])
    {1: 1}
    >>> curate_block_date({2: 2}, [(1, 3), (5, 5)])
    {}
    >>> curate_block_date({3: 3}, [(1, 3), (5, 5)])
    {3: 3}
    >>> curate_block_date({4: 4}, [(1, 3), (5, 5)])
    {}
    >>> curate_block_date({5: 5}, [(1, 3), (5, 5)])
    {5: 5}
    >>> curate_block_date({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, [(1, 3), (5, 5)])
    {1: 1, 3: 3, 5: 5}
    >>> curate_block_date({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, [(2, 2), (3, 5)])
    {2: 2, 3: 3, 5: 5}
    >>> curate_block_date({1: 1, 2: 2, 3: 3, 4: 4, 5: 5}, [(1, 1), (2, 2), (3, 5)])
    {1: 1, 2: 2, 3: 3, 5: 5}

    """
    def walk_block_date_iter():
        wbri = walk_block_range_iter()
        try:
            r = next(wbri)
        except StopIteration:
            return
        for b, d in sorted(block_dates.items()):
            while True:
                if b in r:
                    yield b, d
                    break
                if b < r[1]:
                    break
                try:
                    r = wbri.send(b)
                except StopIteration:
                    break

    def walk_block_range_iter():
        b = 0
        for r in ranges:
            if b > r[1]:
                continue
            # if b < r[0]:
            #     break
            b = yield r

    return dict(walk_block_date_iter())


class TxStore:
    def __init__(self, pyc3l, currency, safe_wallet_add):
        self.pyc3l = pyc3l
        self.inited = False
        self.currency = currency
        self._current_ranges = None
        self._current_block_dates = None
        self._sqlite3_conn = None
        self._sqlite3_cursor = None
        self._sqlite3_transaction_started = False
        self._safe_wallet_add = safe_wallet_add

    def _init(self):
        if not self.inited:
            PYC3L_CACHE_DIR = common.init_cache_dirs()

            self.cache_tx_db_state = os.path.join(
                PYC3L_CACHE_DIR, f"tx_db_{self.currency}_state"
            )  ## pickled state
            self.cache_block_dates_state = os.path.join(
                PYC3L_CACHE_DIR, f"block_db_{self.currency}_state"
            )  ## pickled state
            self.cache_tx_db = os.path.join(
                PYC3L_CACHE_DIR, f"tx_db_{self.currency}.sqlite"
            )  ## sqlite db

            ## init if not exists

            self._sqlite3_conn = sqlite3.connect(self.cache_tx_db)
            self._sqlite3_cursor = self._sqlite3_conn.cursor()
            self.init_db()
        self.inited = True

    def execute(self, *args):
        """Enforce transactionality of sqlite3 execute

        an explicit commit is required to effectively apply previous
        changes.
        """
        if not self._sqlite3_transaction_started:
            self._sqlite3_cursor.execute("BEGIN TRANSACTION")
            self._sqlite3_transaction_started = True
        self._sqlite3_cursor.execute(*args)

    def commit(self):
        """Commit the transaction to the database"""
        self._sqlite3_conn.commit()
        self._sqlite3_transaction_started = False

    def _create_db(self):
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                hash text NOT NULL UNIQUE,
                block integer,
                received_at integer,
                caller text,
                contract text,
                contract_abi text,
                fn text,
                fn_abi text,
                type text,
                sender text,
                receiver text,
                amount integer,
                status text
            )
        """
        )
        self.commit()

    def init_db(self):
        self._create_db()

    def current_ranges(self):
        """Return the ranges (s, e) of fullfilled blocks"""
        if self._current_ranges is None:
            self._init()
            ## load current block from pickled state file
            if os.path.exists(self.cache_tx_db_state):
                self._current_ranges = pickle.load(open(self.cache_tx_db_state, "rb"))
            else:
                self._current_ranges = []
        return self._current_ranges

    def has_block(self, block_number):
        """Return True if the block is in the current ranges"""
        return any(s <= block_number <= e for s, e in self.current_ranges())

    @property
    def current_block_dates(self):
        if self._current_block_dates is None:
            self._init()
            ## get block-date cache
            if os.path.exists(self.cache_block_dates_state):
                self._current_block_dates = pickle.load(open(self.cache_block_dates_state, "rb"))
            else:
                self._current_block_dates = {}
        return self._current_block_dates

    def add_block(self, block_number, collated_ts):
        """Add a block to the current ranges"""

        ## update block range cache

        self._current_ranges = range_union(
            (block_number, block_number), *self.current_ranges()
        )

        pickle.dump(self._current_ranges, open(self.cache_tx_db_state, "wb"))


        ## update block-date cache

        self.current_block_dates[block_number] = collated_ts
        self._current_block_dates = curate_block_date(self.current_block_dates, self.current_ranges())

        pickle.dump(self.current_block_dates, open(self.cache_block_dates_state, "wb"))

    def add_tx(self, data):
        """Add a transaction to the database"""
        self._init()
        self.execute(
            """
            INSERT INTO transactions VALUES (
                :hash, :block, :received_at, :caller, :contract, :contract_abi,
                :fn, :fn_abi, :type, :sender, :receiver, :amount, :status
            )
        """,
            data,
        )

    def records(self, granularity="%Y-%m"):

        self._init()
        if self._safe_wallet_add is None:
            query = """
                SELECT
                    strftime(?, received_at, 'unixepoch') AS month,
                    SUM(CASE WHEN type = 'pledge' THEN amount ELSE 0 END)/100.0 AS pledge_total,
                    COUNT(CASE WHEN type = 'pledge' THEN 1 ELSE NULL END) AS pledge_nb,
                    SUM(CASE WHEN type = 'transfer' THEN amount ELSE 0 END)/100.0 AS transfer_total,
                    COUNT(CASE WHEN type = 'transfer' THEN 1 ELSE NULL END) AS transfer_nb,
                    0.0 AS reconv_total,
                    0 AS reconv_nb
                FROM
                    transactions
                GROUP BY
                    month
                ORDER BY
                    month;
            """
            params = [granularity]
        else:

            params = [granularity]
            safe_wallets_sql = f"({','.join(['?' for _ in self._safe_wallet_add])})"
            is_topup_sql = f"(type = 'pledge' AND receiver NOT IN {safe_wallets_sql})"
            is_topup_sql += " OR "
            is_topup_sql += f"(type = 'transfer' AND sender IN {safe_wallets_sql})"

            is_transfer_sql = f"(type = 'transfer' AND sender NOT IN {safe_wallets_sql}"
            is_transfer_sql += f" AND receiver NOT IN {safe_wallets_sql})"

            is_reconv_sql = f"(type = 'transfer' AND receiver IN {safe_wallets_sql})"

            params += 10 * list(self._safe_wallet_add)

            query = f"""
                SELECT
                    strftime(?, received_at, 'unixepoch') AS month,
                    SUM(CASE WHEN {is_topup_sql} THEN amount ELSE 0 END)/100.0 AS pledge_total,
                    COUNT(CASE WHEN {is_topup_sql} THEN 1 ELSE NULL END) AS pledge_nb,
                    SUM(CASE WHEN {is_transfer_sql} THEN amount ELSE 0 END)/100.0 AS transfer_total,
                    COUNT(CASE WHEN {is_transfer_sql} THEN 1 ELSE NULL END) AS transfer_nb,
                    SUM(CASE WHEN {is_reconv_sql} THEN amount ELSE 0 END)/100.0 AS reconv_total,
                    COUNT(CASE WHEN {is_reconv_sql} THEN 1 ELSE NULL END) AS reconv_nb
                FROM
                    transactions
                GROUP BY
                    month
                ORDER BY
                    month;
            """

        cursor = self._sqlite3_conn.cursor()

        cursor.execute(query, params)

        # Print the results with formatted output
        for row in cursor:
            month = row[0]
            total_pledge = row[1] or 0.0
            nb_pledge = row[2] or 0
            total_transfer = row[3] or 0.0
            nb_transfer = row[4] or 0
            total_reconv = row[5] or 0.0
            nb_reconv = row[6] or 0

            pledge_minus_reconv = total_pledge - total_reconv
            ## correct float rounding errors:
            pledge_minus_reconv = round(pledge_minus_reconv, 2)
            yield (month, total_pledge, nb_pledge,
                   total_transfer, nb_transfer, total_reconv,
                   nb_reconv, pledge_minus_reconv)




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
    idx = 0
    for s, e in current_ranges:
        if s <= block_nb <= e:
            return idx + block_nb - s
        idx += e - s + 1
    return None


def date_block_picker(pyc3l, start_date):
    start_date = start_date.timestamp
    start_time = time.time()

    def get_spinner_char():
        return click.style(
            f"{spinner[int((time.time() - start_time) / 0.2) % len(spinner)]}",
            fg="green",
            bold=True,
        )

    def block_picker(ranges, block_dates):
        current_ranges = ranges
        empty_seg = [None, None]
        block = None
        max_idx = None
        ## if we have block_dates, produce block segment restriction where
        ## the start block should be
        if block_dates:
            prev_b = 0
            found = False
            for b, d in sorted(block_dates.items()):
                if d >= start_date:
                    found = True
                    break
                prev_b = b
            if found:
                current_ranges = ranges_intersection(
                    current_ranges, [(prev_b, current_ranges[-1][1])]
                )
                max_idx = get_idx_from_block_nb(current_ranges, b)
            else:
                current_ranges = ranges_intersection(
                    current_ranges, [(b, current_ranges[-1][1])]
                )

        ## first stage, use dichotomy to find the first block
        while True:
            count_todo = sum(e - s + 1 for s, e in current_ranges)
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
            current_ranges = ranges_intersection(
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


def load_currencies_data(pyc3l, tx_stores, start_date, range_block):
    start_block, end_block = range_block

    full_block_ranges = ranges_intersection(
        *[tx_store.current_ranges() for tx_store in tx_stores.values()]
    )
    full_block_dates = curate_block_date(
        {b: d for tx_store in tx_stores.values() for b, d in tx_store.current_block_dates.items()},
        full_block_ranges,
    )
    missing_block_ranges = range_remove((start_block, end_block), full_block_ranges)
    if start_date is not None:
        block_picker = date_block_picker(pyc3l, start_date)
    else:
        block_picker = lambda ranges: itertools.chain(range(*r) for r in ranges)
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
                                    f"  {k}: {db_data[k]} != {data[k]}",
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


@click.command()
@click.option("-e", "--endpoint", help="Force com-chain endpoint.")
@click.option(
    "-S",
    "--start-block",
    type=str,
    help="Block number to start considering.",
    default=1,
)
@click.option(
    "-E",
    "--end-block",
    type=str,
    help="Block number to start considering.",
    default=0,
)
@click.option(
    "-s",
    "--start-date",
    type=str,
    help="Block starting date to start considering.",
    default=1,
)
@click.option(
    "--safe-wallets-file",
    type=str,
    help="Block starting date to start considering.",
)
@click.option("-r", "--raw", is_flag=True, help="Print raw values.")
@click.option("-a", "--account", multiple=True, help="Filter by account address.")
@click.option("-c", "--currency", multiple=True, help="Filter by account address.")
@click.option("-g", "--granularity", help="Granularity of the output.")
def run(
    start_block: Optional[str],
    end_block: Optional[str],
    endpoint: Optional[str],
    account: List[str],
    raw: bool,
    currency: List[str],
    start_date: Optional[str],
    safe_wallets_file: Optional[str],
    granularity: Optional[str],
):
    params = click_process_multiple_options()
    start_date = Time(start_date, hint_src_tz=TzLocal())
    pyc3l = Pyc3l(endpoint)

    ## check and normalize currencies
    params["currency"] = check_normalize_currencies(pyc3l, params["currency"])
    start_block = (
        int(start_block, 16) if start_block.startswith("0x") else int(start_block)
    )
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

    end_block = (
        int(params["end_block"], 16)
        if params["end_block"].startswith("0x")
        else int(params["end_block"])
    )
    if end_block == 0:
        end_block = pyc3l.getBlockNumber()

    tx_stores = {c: TxStore(pyc3l, c, safe_wallets.get(c)) for c in params["currency"]}

    ## fill tx_stores sqlite databases and display progress on stderr

    if not raw:
        global load_currencies_data
        load_currencies_data = common.protect_tty(load_currencies_data)

    load_currencies_data(pyc3l, tx_stores, start_date, (start_block, end_block))

    ## Let's output some stats thanks to sqlite databases

    header_printed = False
    headers = [
        "currency",
        "date",
        "topup_total",
        "topup_nb",
        "transfer_total",
        "transfer_nb",
        "reconv_total",
        "reconv_nb",
        "topup_minus_reconv_total",
    ]
    headers_align = {
        "currency": "left",
        "date": "left",
        "topup_total": "right",
        "topup_nb": "right",
        "transfer_total": "right",
        "transfer_nb": "right",
        "reconv_total": "right",
        "reconv_nb": "right",
        "topup_minus_reconv_total": "right",
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
            "topup_minus_reconv_total": "Nant",
            "unit": "",
        }
        values_format = { ## default is "%s"
            "topup_total": "%.2f",
            "topup_nb": "%d",
            "transfer_total": "%.2f",
            "transfer_nb": "%d",
            "reconv_total": "%.2f",
            "reconv_nb": "%d",
            "topup_minus_reconv_total": "%.2f",
        }
    else:
        values_format = { ## default is "%s"
            "topup_total": "  %.2f",
            "topup_nb": " %d |",
            "transfer_total": "  %.2f",
            "transfer_nb": " %d |",
            "reconv_total": "  %.2f",
            "reconv_nb": " %d |",
            "topup_minus_reconv_total": "  %.2f",
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
            "topup_minus_reconv_total": "Nant",
            "unit": "",
        }
    values_style = {
        "date": {"fg": "cyan"},
        "topup_total": {"fg": "white"},
        "topup_nb": {"fg": "black"},
        "transfer_total": {"fg": "white"},
        "transfer_nb": {"fg": "black"},
        "reconv_total": {"fg": "white"},
        "reconv_nb": {"fg": "black"},
        "topup_minus_reconv_total": {"fg": "white"},
        "unit": {"fg": "white", "bold": True},
    }
    values_type = { ## default is str
        "topup_total": float,
        "topup_nb": int,
        "transfer_total": float,
        "transfer_nb": int,
        "reconv_total": float,
        "reconv_nb": int,
        "topup_minus_reconv_total": float,
    }
    join_char = "," if raw else " "
    msgs = [
        [currency] + list(r)
        for currency, tx_store in tx_stores.items()
        for r in tx_store.records(granularity=granularity or "%Y-%m")
    ]
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

    ## format msgs
    msgs = [
        [
            values_format.get(header, "%s") % msg[i]
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
            length_fields[header] = max(len(headers_title.get(header, "")), size)

    for msg in msgs:
        heads = headers[:]
        currency = msg[heads.index("currency")]
        if len(params["currency"]) == 1:
            del msg[heads.index("currency")]
            heads.remove("currency")
        head_titles = [headers_title.get(header, "") for header in heads]
        if not raw:
            ## apply size and alignement
            msg = [
                "%%-%ds" % length_fields[header] % msg[i] if headers_align.get(header, "left") == "left" else
                "%%%ds" % length_fields[header] % msg[i]
                for i, header in enumerate(heads)
            ]
            ## same for head_titles
            head_titles = [
                "%%-%ds" % length_fields[header] % head_titles[i] if headers_align.get(header, "left") == "left" else
                "%%%ds" % length_fields[header] % head_titles[i]
                for i, header in enumerate(heads)
            ]
            ## apply style
            msg = [
                click.style(msg[i], **values_style.get(header, {}))
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