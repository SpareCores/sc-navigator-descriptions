"""
Generate human-friendly, plain English summaries for all servers.
"""

from json import dumps

import click

from src.summarize import database
from src.summarize.helpers import (
    _get_price_for_server,
    build_server_payload,
    generate_summary,
)


@click.command()
@click.option(
    "--n", type=int, default=None, help="Limit the number of servers to process"
)
def main(n):
    database.load(n)

    for server in database.servers:
        print(server.name)
        price = _get_price_for_server(server.server_id, database.prices)
        server_dict = build_server_payload(server, price)
        print(dumps(server_dict, indent=2))

        summary = generate_summary(server_dict)
        print(dumps(summary.model_dump(), indent=2))


if __name__ == "__main__":
    main()
