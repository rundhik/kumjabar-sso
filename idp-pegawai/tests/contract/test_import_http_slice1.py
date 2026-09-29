import io
from pathlib import Path
from zipfile import ZipFile

import pytest

from idp_pegawai import create_app
from idp_pegawai.extensions import db
from idp_pegawai.models.import_batch import ImportBatch
from idp_pegawai.access.catalog import Capability


@pytest.fixture
def import_app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "IMPORT_STORAGE_DIR": str(tmp_path),
        "IMPORT_GRANTS": [Capability.IMPORT_UPLOAD, Capability.IMPORT_VIEW],
    })
    with app.app_context():
        db.session.execute(db.text("CREATE TABLE import_batches (id INTEGER PRIMARY KEY, parent_batch_id INTEGER, root_batch_uuid CHAR(32) NOT NULL, retry_reason VARCHAR(80), retry_depth INTEGER NOT NULL DEFAULT 0, import_type VARCHAR(40) NOT NULL, input_profile VARCHAR(60) NOT NULL, status VARCHAR(40) NOT NULL, source_format VARCHAR(10) NOT NULL, original_filename VARCHAR(255) NOT NULL, file_hash VARCHAR(64) NOT NULL, storage_key VARCHAR(255) NOT NULL, uploaded_by VARCHAR(255) NOT NULL, received_at DATETIME NOT NULL, mapping_snapshot JSON NOT NULL, summary JSON NOT NULL, lock_version BIGINT NOT NULL DEFAULT 0, failed_at DATETIME, applied_at DATETIME, metadata JSON NOT NULL, uuid CHAR(32) NOT NULL UNIQUE, created_at DATETIME, updated_at DATETIME, deleted_at DATETIME)"))
        db.session.commit()
        yield app
        db.session.remove()
        ImportBatch.__table__.drop(db.engine)


def test_post_csv_registers_safe_batch_metadata(import_app):
    response = import_app.test_client().post(
        "/imports/batches",
        data={"file": (io.BytesIO(b"nip,nama_lengkap\nsynthetic-id,Synthetic\n"), "synthetic.csv")},
        content_type="multipart/form-data",
        headers={"X-Actor-Id": "synthetic-actor"},
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["data"]["status"] == "received"
    assert payload["data"]["source_format"] == "csv"
    assert set(payload["data"]) == {"batch_id", "status", "source_format"}
    assert "synthetic-id" not in response.get_data(as_text=True)
    assert "storage_key" not in response.get_data(as_text=True)


def test_post_xlsx_accepts_synthetic_fixture(import_app):
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
    response = import_app.test_client().post(
        "/imports/batches",
        data={"file": (io.BytesIO(stream.getvalue()), "synthetic.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    assert response.get_json()["data"]["source_format"] == "xlsx"


def test_get_batch_returns_only_safe_status_metadata(import_app):
    with import_app.app_context():
        batch = ImportBatch(source_format="csv", original_filename="private.csv", file_hash="a" * 64,
                            storage_key="opaque-storage-key", uploaded_by="private-person")
        db.session.add(batch)
        db.session.commit()
        batch_id = str(batch.uuid)
    response = import_app.test_client().get(f"/imports/batches/{batch_id}")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["batch_id"] == batch_id
    assert set(data) == {"batch_id", "status", "source_format", "summary"}
    assert "private.csv" not in response.get_data(as_text=True)
    assert "opaque-storage-key" not in response.get_data(as_text=True)
    assert "private-person" not in response.get_data(as_text=True)


def test_import_endpoints_use_fixed_authorization(import_app):
    import_app.config["IMPORT_GRANTS"] = []
    response = import_app.test_client().get("/imports/batches/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 403
    assert response.get_json() == {"error": "forbidden", "code": "capability_denied"}


def test_missing_batch_is_generic_not_found(import_app):
    response = import_app.test_client().get("/imports/batches/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.get_json()["code"] == "not_found"
    assert "storage" not in response.get_data(as_text=True).lower()
    assert "pii" not in response.get_data(as_text=True).lower()


def test_import_endpoints_have_flask_docstrings_for_openapi(import_app):
    from idp_pegawai.api.imports import batch_status, dry_run, register_batch, set_mapping

    for endpoint in (register_batch, batch_status, set_mapping, dry_run):
        assert "---" in (endpoint.__doc__ or "")
        assert "responses:" in (endpoint.__doc__ or "")


def test_upload_without_storage_is_generic_unavailable():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                      "IMPORT_GRANTS": [Capability.IMPORT_UPLOAD]})
    response = app.test_client().post("/imports/batches", data={"file": (io.BytesIO(b"a,b\n1,2\n"), "a.csv")},
                                      content_type="multipart/form-data")
    assert response.status_code == 503
    assert response.get_json()["code"] == "import_unavailable"
    assert "storage_key" not in response.get_data(as_text=True)
