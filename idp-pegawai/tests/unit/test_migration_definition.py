from pathlib import Path


MIGRATION = Path(__file__).parents[2] / "migrations/versions/0001_create_identity_schema.py"


def test_identity_migration_downgrade_drops_every_created_index():
    source = MIGRATION.read_text()
    upgrade = source.split("def upgrade():", 1)[1].split("def downgrade():", 1)[0]
    downgrade = source.split("def downgrade():", 1)[1]

    created = set()
    for line in upgrade.splitlines():
        if 'op.create_index(' in line:
            created.add(line.split('"', 2)[1])
    assert created
    assert all(f'"{name}"' in downgrade for name in created)
