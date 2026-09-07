"""enforce tenant and source sheet relationships"""

from alembic import op
import sqlalchemy as sa

revision = "8224fc00c7af"
down_revision = "1f0234a8df87"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_ai_usage_log_tenant_id", "ai_usage_log", ["tenant_id", "id"], schema="audit"
    )
    op.create_unique_constraint("uq_event_log_tenant_id", "event_log", ["tenant_id", "id"], schema="audit")
    op.create_unique_constraint("uq_app_user_tenant_id", "app_user", ["tenant_id", "id"], schema="platform")
    op.create_unique_constraint("uq_approval_tenant_id", "approval", ["tenant_id", "id"], schema="platform")
    op.create_unique_constraint(
        "uq_configuration_artifact_tenant_id",
        "configuration_artifact",
        ["tenant_id", "id"],
        schema="platform",
    )
    op.create_unique_constraint(
        "uq_config_sheet_tenant",
        "configuration_version",
        ["tenant_id", "source_sheet_id", "id"],
        schema="platform",
    )
    op.create_unique_constraint(
        "uq_configuration_version_tenant_id", "configuration_version", ["tenant_id", "id"], schema="platform"
    )
    op.create_unique_constraint(
        "uq_data_product_tenant_id", "data_product", ["tenant_id", "id"], schema="platform"
    )
    op.create_unique_constraint(
        "uq_data_source_tenant_id", "data_source", ["tenant_id", "id"], schema="platform"
    )
    op.create_unique_constraint("uq_etl_run_tenant_id", "etl_run", ["tenant_id", "id"], schema="platform")
    op.create_unique_constraint("uq_job_tenant_id", "job", ["tenant_id", "id"], schema="platform")
    op.create_unique_constraint(
        "uq_nl2sql_request_log_tenant_id", "nl2sql_request_log", ["tenant_id", "id"], schema="platform"
    )
    op.create_unique_constraint(
        "uq_profiling_run_tenant_id", "profiling_run", ["tenant_id", "id"], schema="platform"
    )
    op.create_unique_constraint(
        "uq_refresh_token_tenant_id", "refresh_token", ["tenant_id", "id"], schema="platform"
    )
    op.create_unique_constraint(
        "uq_sheet_source_tenant", "source_sheet", ["tenant_id", "source_id", "id"], schema="platform"
    )
    op.create_unique_constraint(
        "uq_source_sheet_tenant_id", "source_sheet", ["tenant_id", "id"], schema="platform"
    )
    op.create_unique_constraint(
        "uq_validated_query_template_tenant_id",
        "validated_query_template",
        ["tenant_id", "id"],
        schema="platform",
    )
    op.create_unique_constraint(
        "uq_row_issue_tenant_id", "row_issue", ["tenant_id", "id"], schema="quarantine"
    )
    op.create_unique_constraint("uq_snapshot_tenant_id", "snapshot", ["tenant_id", "id"], schema="raw")
    op.create_unique_constraint("uq_row_tenant_id", "row", ["tenant_id", "id"], schema="staging")
    op.create_foreign_key(
        "fk_tenant_approval_configuration_id_e28bf8d3",
        "approval",
        "configuration_version",
        ["tenant_id", "configuration_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_approval_reviewer_id_f25732e5",
        "approval",
        "app_user",
        ["tenant_id", "reviewer_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_configuration_arti_configuration_ve_4c1e63b1",
        "configuration_artifact",
        "configuration_version",
        ["tenant_id", "configuration_version_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_configuration_vers_approved_by_a0078f79",
        "configuration_version",
        "app_user",
        ["tenant_id", "approved_by"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_configuration_vers_source_sheet_id_c2aefd26",
        "configuration_version",
        "source_sheet",
        ["tenant_id", "source_sheet_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_configuration_vers_source_id_9f2cbd9a",
        "configuration_version",
        "data_source",
        ["tenant_id", "source_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_configuration_vers_created_by_03021a67",
        "configuration_version",
        "app_user",
        ["tenant_id", "created_by"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_configuration_version_same_source_sheet",
        "configuration_version",
        "source_sheet",
        ["tenant_id", "source_id", "source_sheet_id"],
        ["tenant_id", "source_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_data_product_source_sheet_id_d15f19e6",
        "data_product",
        "source_sheet",
        ["tenant_id", "source_sheet_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_data_source_owner_user_id_d5e89734",
        "data_source",
        "app_user",
        ["tenant_id", "owner_user_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_etl_run_snapshot_id_c17287b8",
        "etl_run",
        "snapshot",
        ["tenant_id", "snapshot_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="raw",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_etl_run_source_id_f0357bc5",
        "etl_run",
        "data_source",
        ["tenant_id", "source_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_etl_run_configuration_id_8ab68496",
        "etl_run",
        "configuration_version",
        ["tenant_id", "configuration_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_etl_run_source_sheet_id_b8a8cc0f",
        "etl_run",
        "source_sheet",
        ["tenant_id", "source_sheet_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_etl_run_same_source_sheet",
        "etl_run",
        "source_sheet",
        ["tenant_id", "source_id", "source_sheet_id"],
        ["tenant_id", "source_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_job_source_id_6f636b60",
        "job",
        "data_source",
        ["tenant_id", "source_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_job_requested_by_6d04cc02",
        "job",
        "app_user",
        ["tenant_id", "requested_by"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_nl2sql_request_log_user_id_8cb7255b",
        "nl2sql_request_log",
        "app_user",
        ["tenant_id", "user_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_profiling_run_source_sheet_id_657c4a3b",
        "profiling_run",
        "source_sheet",
        ["tenant_id", "source_sheet_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_profiling_run_source_id_5377661f",
        "profiling_run",
        "data_source",
        ["tenant_id", "source_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_profiling_run_same_source_sheet",
        "profiling_run",
        "source_sheet",
        ["tenant_id", "source_id", "source_sheet_id"],
        ["tenant_id", "source_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_refresh_token_user_id_599cf422",
        "refresh_token",
        "app_user",
        ["tenant_id", "user_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_active_config_same_sheet",
        "source_sheet",
        "configuration_version",
        ["tenant_id", "id", "active_configuration_id"],
        ["tenant_id", "source_sheet_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_source_sheet_source_id_78baff30",
        "source_sheet",
        "data_source",
        ["tenant_id", "source_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_source_sheet_active_configura_fa7f22c9",
        "source_sheet",
        "configuration_version",
        ["tenant_id", "active_configuration_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_validated_query_te_created_by_093e2a44",
        "validated_query_template",
        "app_user",
        ["tenant_id", "created_by"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_row_issue_source_id_3ad608e5",
        "row_issue",
        "data_source",
        ["tenant_id", "source_id"],
        ["tenant_id", "id"],
        source_schema="quarantine",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_row_issue_etl_run_id_2f59f394",
        "row_issue",
        "etl_run",
        ["tenant_id", "etl_run_id"],
        ["tenant_id", "id"],
        source_schema="quarantine",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_snapshot_source_id_e768669b",
        "snapshot",
        "data_source",
        ["tenant_id", "source_id"],
        ["tenant_id", "id"],
        source_schema="raw",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_snapshot_same_source_sheet",
        "snapshot",
        "source_sheet",
        ["tenant_id", "source_id", "source_sheet_id"],
        ["tenant_id", "source_id", "id"],
        source_schema="raw",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_snapshot_source_sheet_id_f9db684a",
        "snapshot",
        "source_sheet",
        ["tenant_id", "source_sheet_id"],
        ["tenant_id", "id"],
        source_schema="raw",
        referent_schema="platform",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_tenant_row_etl_run_id_d939e7fb",
        "row",
        "etl_run",
        ["tenant_id", "etl_run_id"],
        ["tenant_id", "id"],
        source_schema="staging",
        referent_schema="platform",
        use_alter=True,
    )


def downgrade():
    op.drop_constraint("fk_tenant_row_etl_run_id_d939e7fb", "row", schema="staging", type_="foreignkey")
    op.drop_constraint(
        "fk_tenant_snapshot_source_sheet_id_f9db684a", "snapshot", schema="raw", type_="foreignkey"
    )
    op.drop_constraint("fk_snapshot_same_source_sheet", "snapshot", schema="raw", type_="foreignkey")
    op.drop_constraint("fk_tenant_snapshot_source_id_e768669b", "snapshot", schema="raw", type_="foreignkey")
    op.drop_constraint(
        "fk_tenant_row_issue_etl_run_id_2f59f394", "row_issue", schema="quarantine", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_tenant_row_issue_source_id_3ad608e5", "row_issue", schema="quarantine", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_tenant_validated_query_te_created_by_093e2a44",
        "validated_query_template",
        schema="platform",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_tenant_source_sheet_active_configura_fa7f22c9",
        "source_sheet",
        schema="platform",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_tenant_source_sheet_source_id_78baff30", "source_sheet", schema="platform", type_="foreignkey"
    )
    op.drop_constraint("fk_active_config_same_sheet", "source_sheet", schema="platform", type_="foreignkey")
    op.drop_constraint(
        "fk_tenant_refresh_token_user_id_599cf422", "refresh_token", schema="platform", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_profiling_run_same_source_sheet", "profiling_run", schema="platform", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_tenant_profiling_run_source_id_5377661f", "profiling_run", schema="platform", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_tenant_profiling_run_source_sheet_id_657c4a3b",
        "profiling_run",
        schema="platform",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_tenant_nl2sql_request_log_user_id_8cb7255b",
        "nl2sql_request_log",
        schema="platform",
        type_="foreignkey",
    )
    op.drop_constraint("fk_tenant_job_requested_by_6d04cc02", "job", schema="platform", type_="foreignkey")
    op.drop_constraint("fk_tenant_job_source_id_6f636b60", "job", schema="platform", type_="foreignkey")
    op.drop_constraint("fk_etl_run_same_source_sheet", "etl_run", schema="platform", type_="foreignkey")
    op.drop_constraint(
        "fk_tenant_etl_run_source_sheet_id_b8a8cc0f", "etl_run", schema="platform", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_tenant_etl_run_configuration_id_8ab68496", "etl_run", schema="platform", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_tenant_etl_run_source_id_f0357bc5", "etl_run", schema="platform", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_tenant_etl_run_snapshot_id_c17287b8", "etl_run", schema="platform", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_tenant_data_source_owner_user_id_d5e89734", "data_source", schema="platform", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_tenant_data_product_source_sheet_id_d15f19e6",
        "data_product",
        schema="platform",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_configuration_version_same_source_sheet",
        "configuration_version",
        schema="platform",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_tenant_configuration_vers_created_by_03021a67",
        "configuration_version",
        schema="platform",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_tenant_configuration_vers_source_id_9f2cbd9a",
        "configuration_version",
        schema="platform",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_tenant_configuration_vers_source_sheet_id_c2aefd26",
        "configuration_version",
        schema="platform",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_tenant_configuration_vers_approved_by_a0078f79",
        "configuration_version",
        schema="platform",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_tenant_configuration_arti_configuration_ve_4c1e63b1",
        "configuration_artifact",
        schema="platform",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_tenant_approval_reviewer_id_f25732e5", "approval", schema="platform", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_tenant_approval_configuration_id_e28bf8d3", "approval", schema="platform", type_="foreignkey"
    )
    op.drop_constraint("uq_row_tenant_id", "row", schema="staging", type_="unique")
    op.drop_constraint("uq_snapshot_tenant_id", "snapshot", schema="raw", type_="unique")
    op.drop_constraint("uq_row_issue_tenant_id", "row_issue", schema="quarantine", type_="unique")
    op.drop_constraint(
        "uq_validated_query_template_tenant_id", "validated_query_template", schema="platform", type_="unique"
    )
    op.drop_constraint("uq_source_sheet_tenant_id", "source_sheet", schema="platform", type_="unique")
    op.drop_constraint("uq_sheet_source_tenant", "source_sheet", schema="platform", type_="unique")
    op.drop_constraint("uq_refresh_token_tenant_id", "refresh_token", schema="platform", type_="unique")
    op.drop_constraint("uq_profiling_run_tenant_id", "profiling_run", schema="platform", type_="unique")
    op.drop_constraint(
        "uq_nl2sql_request_log_tenant_id", "nl2sql_request_log", schema="platform", type_="unique"
    )
    op.drop_constraint("uq_job_tenant_id", "job", schema="platform", type_="unique")
    op.drop_constraint("uq_etl_run_tenant_id", "etl_run", schema="platform", type_="unique")
    op.drop_constraint("uq_data_source_tenant_id", "data_source", schema="platform", type_="unique")
    op.drop_constraint("uq_data_product_tenant_id", "data_product", schema="platform", type_="unique")
    op.drop_constraint(
        "uq_configuration_version_tenant_id", "configuration_version", schema="platform", type_="unique"
    )
    op.drop_constraint("uq_config_sheet_tenant", "configuration_version", schema="platform", type_="unique")
    op.drop_constraint(
        "uq_configuration_artifact_tenant_id", "configuration_artifact", schema="platform", type_="unique"
    )
    op.drop_constraint("uq_approval_tenant_id", "approval", schema="platform", type_="unique")
    op.drop_constraint("uq_app_user_tenant_id", "app_user", schema="platform", type_="unique")
    op.drop_constraint("uq_event_log_tenant_id", "event_log", schema="audit", type_="unique")
    op.drop_constraint("uq_ai_usage_log_tenant_id", "ai_usage_log", schema="audit", type_="unique")
