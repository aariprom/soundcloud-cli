import typer
import logging
from sc_cli.repl import REPL

app = typer.Typer(help="SoundCloud CLI Client")


@app.command()
def start():
    """
    Start the SoundCloud CLI Interactive Mode.
    """
    logging.basicConfig(level=logging.WARN)
    try:
        repl = REPL()
        repl.start()
    except Exception as e:
        print(f"Error starting interactive mode: {e}")


def main():
    # Directly invoke the logic without requiring 'start' subcommand if possible,
    # but with Typer we can just have one command or use a callback without subcommands.
    # Simpler: just run the REPL logic if no typer args, but sticking to Typer structure is fine.
    # actually, purely replacing Typer might be cleaner if we have NO subcommands.
    # But let's keep Typer for --help and potentail future args.
    # We'll use a callback-only pattern for the root command.
    pass


if __name__ == "__main__":
    # We can just instantiate and run if we want to be minimal,
    # or use typer for robust help flags.
    # Let's use the simplest Typer invocation that runs default.
    typer.run(start)
