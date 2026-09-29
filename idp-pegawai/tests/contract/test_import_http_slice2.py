import io
import pytest
from idp_pegawai import create_app
from idp_pegawai.extensions import db
from idp_pegawai.models.import_batch import ImportBatch
from idp_pegawai.access.catalog import Capability

@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'t.db'}", "IMPORT_STORAGE_DIR": str(tmp_path), "IMPORT_ORG_CODES": ["ORG-1"], "IMPORT_GRANTS": [Capability.IMPORT_UPLOAD, Capability.IMPORT_VIEW, Capability.IMPORT_VALIDATE]})
    with app.app_context():
        db.session.execute(db.text("CREATE TABLE import_batches (id INTEGER PRIMARY KEY, parent_batch_id INTEGER, root_batch_uuid CHAR(32) NOT NULL, retry_reason VARCHAR(80), retry_depth INTEGER NOT NULL DEFAULT 0, import_type VARCHAR(40) NOT NULL, input_profile VARCHAR(60) NOT NULL, status VARCHAR(40) NOT NULL, source_format VARCHAR(10) NOT NULL, original_filename VARCHAR(255) NOT NULL, file_hash VARCHAR(64) NOT NULL, storage_key VARCHAR(255) NOT NULL, uploaded_by VARCHAR(255) NOT NULL, received_at DATETIME NOT NULL, mapping_snapshot JSON NOT NULL, summary JSON NOT NULL, lock_version BIGINT NOT NULL DEFAULT 0, failed_at DATETIME, applied_at DATETIME, metadata JSON NOT NULL, uuid CHAR(32) NOT NULL UNIQUE, created_at DATETIME, updated_at DATETIME, deleted_at DATETIME)"))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

def batch(client):
    r = client.post('/imports/batches', data={'file': (io.BytesIO(b'nip,nama_lengkap,status_pegawai,org_unit_code,email_dinas\n123456789012345678,Synthetic,aktif,ORG-1,s@example.test\n'), 's.csv')}, content_type='multipart/form-data')
    return r.get_json()['data']['batch_id']

def mapping():
    return {'nip':'nip','nama_lengkap':'nama_lengkap','status_pegawai':'status_pegawai','org_unit_code':'org_unit_code','email_dinas':'email_dinas'}

def test_mapping_fixed_allowlist_and_status(app):
    c=app.test_client(); bid=batch(c)
    r=c.post(f'/imports/batches/{bid}/mapping', json={'mapping': mapping()})
    assert r.status_code == 200 and r.get_json()['data']['status']=='mapped'
    assert 'storage_key' not in r.get_data(as_text=True)
    bad_bid=batch(c)
    bad=c.post(f'/imports/batches/{bad_bid}/mapping', json={'mapping': {'role':'role'}})
    assert bad.status_code == 400 and bad.get_json()['code']=='invalid_mapping'

def test_mapping_auth_and_status_and_not_found(app):
    c=app.test_client(); bid=batch(c); app.config['IMPORT_GRANTS']=[Capability.IMPORT_UPLOAD]
    assert c.post(f'/imports/batches/{bid}/mapping', json={'mapping':{}}).status_code==403
    app.config['IMPORT_GRANTS']=[Capability.IMPORT_VALIDATE]
    assert c.post('/imports/batches/00000000-0000-0000-0000-000000000000/mapping', json={'mapping':{}}).status_code==404

def test_dry_run_summary_and_error_catalog(app):
    c=app.test_client(); bid=batch(c)
    assert c.post(f'/imports/batches/{bid}/mapping', json={'mapping':mapping()}).status_code==200
    r=c.post(f'/imports/batches/{bid}/dry-run')
    assert r.status_code==200
    data=r.get_json()['data']; assert data['summary']['planned_create']==1
    assert 'errors' in data and 'storage_key' not in r.get_data(as_text=True)
    assert c.post(f'/imports/batches/{bid}/dry-run').status_code==409


def test_preview_contains_bounded_rows_and_errors_for_blocking_batch(app):
    c=app.test_client(); bid=batch(c)
    assert c.post(f'/imports/batches/{bid}/mapping', json={'mapping':mapping()}).status_code==200
    with app.app_context():
        from uuid import UUID
        b=db.session.query(ImportBatch).filter_by(uuid=UUID(bid)).one()
        b.status='mapped'
        b.mapping_snapshot=mapping()
        b.summary={'planned_create': 0, 'planned_update': 0, 'planned_noop': 0, 'planned_reject': 1,
                   'errors': [{'row': 2, 'field': 'nip', 'code': 'invalid_nip', 'message': 'NIP tidak valid'}]}
        db.session.commit()
    response=c.get(f'/imports/batches/{bid}/preview')
    assert response.status_code==200
    preview=response.get_json()['data']['preview']
    assert preview['rows'] and preview['rows'][0]['nip']=='123456789012345678'
    assert preview['errors'][0]['row']==2
    assert preview['errors'][0]['field']=='nip'


def test_error_report_is_available_for_blocking_mapped_batch(app):
    app.config['IMPORT_GRANTS'] = [Capability.IMPORT_UPLOAD, Capability.IMPORT_VALIDATE, Capability.IMPORT_ERROR_WORKBOOK_DOWNLOAD]
    c=app.test_client(); bid=batch(c)
    assert c.post(f'/imports/batches/{bid}/mapping', json={'mapping':mapping()}).status_code==200
    response=c.get(f'/imports/batches/{bid}/error-report')
    assert response.status_code==200
    assert response.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert len(response.data)>100

def test_mapping_unknown_field_is_rejected(app):
    c=app.test_client(); bid=batch(c)
    r=c.post(f'/imports/batches/{bid}/mapping', json={'mapping': {'nip':'not_a_column'}})
    assert r.status_code==400 and r.get_json()['code']=='invalid_mapping'

def test_mapping_status_transition_rejects_wrong_state(app):
    c=app.test_client(); bid=batch(c)
    with app.app_context():
        from uuid import UUID
        b=db.session.query(ImportBatch).filter_by(uuid=UUID(bid)).one(); b.status='validated'; db.session.commit()
    assert c.post(f'/imports/batches/{bid}/mapping', json={'mapping':{}}).status_code==409

if __name__ == '__main__':
    raise SystemExit()
