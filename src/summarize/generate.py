"""
Generate human-friendly, plain English summaries for all servers.
"""

import logging
import os

import click
import sc_data
from sc_crawler.tables import Server
from sqlmodel import Session, create_engine, select

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

DATA_FOLDER = os.environ.get("DATA_FOLDER", default="data")
os.makedirs(DATA_FOLDER, exist_ok=True)


@click.command()
@click.option(
    "--n", type=int, default=None, help="Limit the number of servers to process"
)
def main(n):
    engine = create_engine(f"sqlite:///{sc_data.db.path}")
    query = select(Server)
    if n is not None:
        query = query.limit(n)

    with Session(engine) as session:
        servers = session.exec(query).all()

    for server in servers:
        print(server.name)


if __name__ == "__main__":
    main()
