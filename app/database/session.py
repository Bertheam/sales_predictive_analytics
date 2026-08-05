from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import settings


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
)

_SessionFactory = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


@event.listens_for(Session, "after_begin")
def apply_company_context(session, transaction, connection) -> None:
    """Attach the verified tenant to every SQLAlchemy transaction."""
    company_id = session.info.get("company_id")
    if not company_id:
        raise RuntimeError("Une session métier ne peut pas être ouverte sans dépôt.")
    if settings.STREAMLIT_USE_RUNTIME_ROLE:
        connection.exec_driver_sql(
            "SET LOCAL ROLE sales_predictive_tenant_runtime"
        )
    connection.execute(
        text("SELECT set_config('app.current_company_id', :company_id, TRUE)"),
        {"company_id": str(company_id)},
    )


def SessionLocal():
    """Return a session locked to the configured Streamlit company."""
    return _SessionFactory(info={"company_id": settings.company_id})


def session_for_company(company_id):
    """Return a SQLAlchemy session explicitly isolated to one company.

    Background workers do not have a browser session or a fixed Streamlit
    tenant. Requiring the company identifier here prevents an asynchronous
    task from accidentally reading another depot's data.
    """
    return _SessionFactory(info={"company_id": str(company_id)})


def get_db_session():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
