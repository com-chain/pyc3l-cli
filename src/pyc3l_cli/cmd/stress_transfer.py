#!/usr/bin/env python
"""Stress-test the per-account nonce lock with repeated transfers.

This command fires ``count`` back-to-back ``transferNant`` transactions
from a wallet to a target address, with NO artificial delay, relying on
the library's built-in per-account nonce lock + confirmation (every
``send_transaction`` holds the lock and waits for the transaction to be
acknowledged before releasing).

It is meant to be run in *two* shells on the *same host*, against the
*same wallet/account*, on a *test* currency: the two runs contend on
the same per-account lock file, exercising the cross-process
serialization.  Each line printed is ``<run> <i> nonce=<n> hash=<h>``
so the two runs can be merged/sorted to eyeball gaps, duplicates, or
collisions in the nonce sequence.
"""

import os
import sys
import time
import getpass

import click

from pyc3l import Pyc3l
from pyc3l_cli import common


def _tx_nonce(pyc3l, tx_hash):
    """Authoritative nonce of a sent transaction, re-queried by hash.

    ``getTransactionInfo`` returns the raw geth transaction under the
    ``transaction`` key, whose ``nonce`` field is the exact nonce that
    was signed.  Returns an int, or ``None`` if not (yet) resolvable.

    Note: ``getTransactionInfo`` prepends ``0x`` itself, so we must
    pass the *bare* hash -- otherwise the request carries ``0x0x...``
    (66 chars) and geth rejects it ("hex string has length 66").
    """
    bare = tx_hash[2:] if tx_hash.startswith("0x") else tx_hash
    try:
        info = pyc3l.getTransactionInfo(bare)
        return int(info["transaction"]["nonce"], 0)
    except Exception:
        return None


def _pinned_node(pyc3l, address):
    """Best-effort read of the node pinned for ``address`` by the lock.

    ``send_transaction`` stores the elected node URL in the per-account
    nonce lock file.  Read it back as the authoritative "node used";
    fall back to the current endpoint if the file is unavailable.
    """
    try:
        with open(pyc3l._nonce_lock_path(address)) as f:
            node = f.read().strip()
        if node:
            return node
    except (OSError, AttributeError):
        pass
    try:
        return str(pyc3l.endpoint)
    except Exception:
        return None


def _print_pending_pool(pyc3l, address):
    """Print, per node, the txpool entries for ``address`` only.

    Queries ``pool.php`` on every known endpoint and filters both the
    ``pending`` and ``queued`` sets to our wallet address.  ``queued``
    entries are the smoking gun for a nonce gap (transactions geth
    cannot execute because an earlier nonce is missing).
    """
    import requests

    want = address.lower()
    want = want[2:] if want.startswith("0x") else want

    print("")
    print(f"Pending pool for 0x{want} across all nodes:")
    for endpoint in pyc3l.endpoints:
        url = str(endpoint)
        try:
            resp = requests.post(f"{url}/pool.php", timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", {})
        except Exception as e:
            print(f"  {url}: ERROR ({e})")
            continue

        def mine(section):
            ## Section is {address: {nonce: tx, ...}} when populated, but
            ## geth/api may serialize an empty section as [] instead of
            ## {}; treat anything non-dict as empty.
            if not isinstance(section, dict):
                return []
            out = []
            for addr, txs in section.items():
                a = addr.lower()
                a = a[2:] if a.startswith("0x") else a
                if a == want:
                    out.extend(int(n) for n in txs.keys())
            return sorted(out)

        pending = mine(data.get("pending"))
        queued = mine(data.get("queued"))
        if not pending and not queued:
            print(f"  {url}: (none)")
        else:
            print(f"  {url}: pending={pending} queued={queued}")


@click.command()
@click.option("-w", "--wallet-file", help="wallet path")
@click.option("-p", "--password-file", help="wallet password path")
@click.option("-e", "--endpoint", help="Force com-chain endpoint.")
@click.option("-n", "--count", help="number of transfers to send", default=10)
@click.option(
    "-a", "--amount", help="amount per transfer", default=0.01, type=float
)
@click.option(
    "-r",
    "--run",
    help="run label to tag this shell's output (default: PID)",
    default=None,
)
@click.option(
    "-y",
    "--no-confirm",
    help="Bypass confirmation and always assume 'yes'",
    is_flag=True,
)
@click.argument("address", type=str, required=True)
def run(wallet_file, password_file, endpoint, count, amount, run, no_confirm,
        address):
    """Send COUNT transfers of AMOUNT to ADDRESS, hammering the nonce lock.

    Run the same command in two shells (same host, same wallet) to test
    cross-process nonce serialization on a test currency.
    """
    run = run or str(os.getpid())

    pyc3l = Pyc3l(endpoint)

    wallet = pyc3l.Wallet.from_file(
        wallet_file or common.filepicker("Select Wallet")
    )
    wallet.unlock(
        common.load_password(password_file)
        if password_file
        else getpass.getpass()
    )

    if not wallet.isActive:
        print("Error: The Sender Wallet is locked!", file=sys.stderr)
        sys.exit(1)

    print(
        f"run={run}: about to send {count} transfer(s) of {amount} "
        f"to {address} from 0x{wallet.address}"
    )
    if not no_confirm and input("Continue? (y/n) ") != "y":
        sys.exit()

    nonces = []
    for i in range(count):
        t0 = time.time()
        tx_hash = wallet.transferNant(address, amount)
        elapsed = time.time() - t0

        ## Recover the AUTHORITATIVE nonce actually signed into the
        ## transaction by re-querying it by hash (the raw geth tx under
        ## "transaction" carries its real nonce).  This is the only
        ## reliable value under concurrency -- a pre-send read would be
        ## the node's pending count, not necessarily what we signed.
        real_nonce = _tx_nonce(pyc3l, tx_hash)
        node = _pinned_node(pyc3l, wallet.address)

        nonces.append(real_nonce)
        print(
            f"run={run} i={i} nonce={real_nonce} node={node} "
            f"hash={tx_hash} elapsed={elapsed:.1f}s",
            flush=True,
        )

    print(f"run={run}: done, {count} transfer(s) sent")
    print(f"run={run}: nonces (authoritative, from tx info): {nonces}")

    _print_pending_pool(pyc3l, wallet.address)


if __name__ == "__main__":
    run()
