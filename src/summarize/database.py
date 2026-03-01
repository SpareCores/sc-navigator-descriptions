"""
Load and preprocess DB data for summary generation.
Exposes servers, benchmarks, prices after load(n) is called.
"""

from sc_crawler.table_fields import Status
from sc_crawler.tables import BenchmarkScore, Server, ServerPrice, Vendor
from sc_data import db
from sqlalchemy.orm import contains_eager
from sqlmodel import Session, create_engine, func, select

# Set by load(); other modules use these after calling load(n).
servers: list = []
benchmarks: list = []
prices: list = []


def load(n: int | None = None) -> None:
    """Load active servers, their benchmarks, and min ONDEMAND prices.

    Preprocess benchmarks (remove framework version from config).
    """
    global servers, benchmarks, prices
    engine = create_engine(f"sqlite:///{db.path}")
    query = select(Server).where(Server.status == Status.ACTIVE)
    if n is not None:
        query = query.limit(n)
    query = query.join(Vendor).options(contains_eager(Server.vendor))

    with Session(engine) as session:
        servers = session.exec(query).all()

        benchmarks = session.exec(
            select(BenchmarkScore).where(BenchmarkScore.status == Status.ACTIVE)
        ).all()
        for b in benchmarks:
            if isinstance(getattr(b, "config", None), dict):
                b.config.pop("framework_version", None)

        prices = session.exec(
            select(
                ServerPrice.vendor_id,
                ServerPrice.server_id,
                func.min(ServerPrice.price).label("price"),
            )
            .where(
                ServerPrice.allocation == "ONDEMAND"
                and ServerPrice.status == Status.ACTIVE
            )
            .group_by(ServerPrice.vendor_id, ServerPrice.server_id)
        ).all()
