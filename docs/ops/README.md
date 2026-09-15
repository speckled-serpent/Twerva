# Twerva ops

Production notes for **Badger** (Twerva Server Manager) and anyone
touching the live box.

These files encode on-box facts from the Server Manager handoff. They do
**not** include AWS console walkthroughs, security-group recipes, or
secret values.

| Doc | Role |
|---|---|
| [`deploy.md`](deploy.md) | Production `twerva-server`: layout, deploy, migrate, verify, rollback, health, landmines |

Local API run, `DATABASE_URL`, and Alembic smoke stay in
[`apps/server/README.md`](../../apps/server/README.md). Schema revision
notes stay in [`docs/reports/task_1_2_report.md`](../reports/task_1_2_report.md).
