
import os
import sys
import logging

import click


CONTEXT_SETTINGS = {
    "auto_envvar_prefix": "PYC3L_CLI",
}

class Environment:
    def __init__(self):
        self._verbose = False
        self._debug = False

    def stderr(self, msg, *args):
        """Logs a message to stderr."""
        if args:
            msg %= args
        click.echo(msg, file=sys.stderr)

    def err(self, msg, *args):
        self.stderr(click.style("Error: ", fg='red', bold=True) + msg, *args)

    def verbose(self, msg, *args):
        """Logs a message to stderr only if verbose is enabled."""
        if self._verbose:
            self.stderr(msg, *args)


pass_environment = click.make_pass_decorator(Environment, ensure=True)
cmd_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "cmd"))


class Pyc3lCLI(click.MultiCommand):

    def list_commands(self, ctx):
        return sorted(filename[0:-3] for filename in os.listdir(cmd_folder)
                      if filename.endswith(".py") and filename != "__init__.py")

    def get_command(self, ctx, name):
        if name not in self.list_commands(ctx):
            return None
        @click.command(
            name,
            context_settings={
                "ignore_unknown_options": True
            },
            add_help_option=False,
        )
        @click.argument('args', nargs=-1)
        @pass_environment
        def cmd(sub_ctx, args, **kwargs):
            try:
                sys.argv = ["%s.py" % name, ] + list(args)
                mod = __import__(f"pyc3l_cli.cmd.{name}", None, None, ["run"])
            except ImportError:
                raise Exception("Failed to load command %r" % name)
            if hasattr(mod, "run") and callable(mod.run):
                try:
                    return mod.run(parent=ctx)
                except Exception as e:
                    if sub_ctx._debug:
                        raise
                    sub_ctx.err(str(e))
                    sub_ctx.stderr("  (You can provide ``--debug`` or ``-d`` to show full traceback)")
                    return 1
        return cmd


@click.command(cls=Pyc3lCLI, context_settings=CONTEXT_SETTINGS)
@click.option("-d", "--debug", is_flag=True, help="Enables debug mode.")
@click.option("-v", "--verbose", is_flag=True, help="Enables verbose mode.")
@click.option("-l", "--log-handler", help="Set logging levels.")
@pass_environment
def cli(ctx, verbose, debug, log_handler):
    """A Comchain API command line interface."""

    ctx._verbose = verbose or debug
    ctx._debug = debug

    if debug and not log_handler:
        log_handler = "pyc3l:DEBUG"

    ## Configure logging to go to stderr

    # formatter = logging.Formatter('%(asctime)s %(levelname)-5s [%(name)s] %(message)s')
    formatter = logging.Formatter('%(levelname)-5s [%(name)s] %(message)s')
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)

    if ":" in (log_handler or ""):
        ## at least one statement
        for statement in log_handler.split(","):
            if ":" not in statement:
                ctx.stderr("Invalid debug string.")
                exit(253)
            prefix, level = statement.rsplit(":", 1)
            target_logger = logging.getLogger(prefix) if prefix else logging.getLogger()
            target_logger.setLevel(getattr(logging, level))
            target_logger.addHandler(ch)

