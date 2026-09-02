from idp_pegawai import create_app
from idp_pegawai.extensions import db
from idp_pegawai.services.org_unit_service import OrgUnitSeedService

app = create_app()
with app.app_context():
    result = OrgUnitSeedService(db.session).seed([
        {
            "code": "TUM_TI",
            "slug": "tum-ti",
            "name": "Tim Teknologi Informasi (Dummy)",
            "short_name": "TUM TI",
            "unit_type": "tim",
            "level": 0,
            "path": "/tum-ti",
            "keycloak_group_path": "/pegawai/tum-ti",
            "sort_order": 1,
            "is_active": True,
        }
    ])
    db.session.commit()
    print(f"development org seed: {result}", flush=True)
