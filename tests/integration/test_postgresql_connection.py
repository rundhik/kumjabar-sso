import os

import pytest
from sqlalchemy import text

from idp_pegawai import create_app
from idp_pegawai.extensions import db


@pytest.mark.integration
@pytest.mark.postgresql
def test_postgresql_connection_round_trip():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL belum dikonfigurasi")

    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": database_url})
    with app.app_context():
        with db.engine.begin() as connection:
            result = connection.execute(text("SELECT 1 AS value"))
            assert result.scalar_one() == 1
