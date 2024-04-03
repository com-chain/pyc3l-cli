# pyc3l-cli

[![Latest Pypi Version](http://img.shields.io/pypi/v/pyc3l-cli.svg?style=flat)](https://pypi.python.org/pypi/pyc3l-cli/)

This project offer a command line interface for interacting with
[ComChain](https://com-chain.org/) from the shell.

## Maturity

This code is in alpha stage. It wasn't tested on Windows.
This is more a draft for an ongoing reflection.

## Features

using ``pyc3l-cli``, through the ``pyc3l`` command line tool, you can:

- monitor block rates with ``pyc3l block_rate``
- check account information with ``pyc3l account_info`` (last
  transactions, type, status, balance, delegations...)
- check a specific transaction ``pyc3l check_transaction``
- issue pledge, transfer, delegate, and transfer on behalf commands
- ... many examples and other specific commands are provided ...

## Requirement

This code is for python3. Some subcommands are using ``tkinter`` for
interactive usage (you can always avoid using ``tkinter`` by providing
necessary arguments on command line).

You can check if ``tkinter`` is installed by running ``python3`` and typing:

```
>>> import tkinter
>>> tkinter._test()
```

## Installation

You don't need to download the git version of the code as ``pyc3l-cli`` is
available on the PyPI. So you should be able to run:

```bash
pip install pyc3l-cli
```

If you have downloaded the GIT sources, then you could add install
the current version via traditional::

```bash
python setup.py install
```

And if you don't have the GIT sources but would like to get the latest
master or branch from github, you could also::

```
pip install git+https://github.com/com-chain/pyc3l-cli
```

Or even select a specific revision (branch/tag/commit)::

```
pip install git+https://github.com/com-chain/pyc3l-cli@master
```

## Usage


### Logging

```bash
PYC3L_CLI_DEBUG=1 pyc3l [COMMAND] ...
```

or

```bash
pyc3l -d [COMMAND] ...
```


or 

```bash
pyc3l --log-handler pyc3l:DEBUG [COMMAND] ...
```

All debugging on:

```bash
pyc3l --log-handler :DEBUG [COMMAND] ...
```

## Contributing

Any suggestions or issues are welcome. Push requests are very welcome,
please check out the guidelines.

### Push Request Guidelines

You can send any code. I'll look at it and will integrate it myself in
the code base and leave you as the author. This process can take time and
it'll take less time if you follow the following guidelines:

- check your code with PEP8 or pylint. Try to stick to 80 columns wide.
- separate your commits per smallest concern.
- each commit should pass the tests (to allow easy bisect)
- each functionality/bugfix commit should contain the code, tests,
  and doc.
- prior minor commit with typographic or code cosmetic changes are
  very welcome. These should be tagged in their commit summary with
  ``!minor``.
- the commit message should follow gitchangelog rules (check the git
  log to get examples)
- if the commit fixes an issue or finished the implementation of a
  feature, please mention it in the summary.

If you have some questions about guidelines which is not answered here,
please check the current ``git log``, you might find previous commit that
shows you how to deal with your issue.

## License

Licensed under the [GNU Affero General Public
License](http://raw.github.com/com-chain/pyc3l-cli/master/LICENSE)
