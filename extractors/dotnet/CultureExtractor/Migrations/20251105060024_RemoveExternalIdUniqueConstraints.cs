using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class RemoveExternalIdUniqueConstraints : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "ix_tag_external_ids_target_system_uuid_external_id",
                table: "tag_external_ids");

            migrationBuilder.DropIndex(
                name: "ix_sub_site_external_ids_target_system_uuid_external_id",
                table: "sub_site_external_ids");

            migrationBuilder.DropIndex(
                name: "ix_site_external_ids_target_system_uuid_external_id",
                table: "site_external_ids");

            migrationBuilder.DropIndex(
                name: "ix_release_external_ids_target_system_uuid_external_id",
                table: "release_external_ids");

            migrationBuilder.DropIndex(
                name: "ix_performer_external_ids_target_system_uuid_external_id",
                table: "performer_external_ids");

            migrationBuilder.CreateIndex(
                name: "ix_tag_external_ids_target_system_uuid",
                table: "tag_external_ids",
                column: "target_system_uuid");

            migrationBuilder.CreateIndex(
                name: "ix_sub_site_external_ids_target_system_uuid",
                table: "sub_site_external_ids",
                column: "target_system_uuid");

            migrationBuilder.CreateIndex(
                name: "ix_site_external_ids_target_system_uuid",
                table: "site_external_ids",
                column: "target_system_uuid");

            migrationBuilder.CreateIndex(
                name: "ix_release_external_ids_target_system_uuid",
                table: "release_external_ids",
                column: "target_system_uuid");

            migrationBuilder.CreateIndex(
                name: "ix_performer_external_ids_target_system_uuid",
                table: "performer_external_ids",
                column: "target_system_uuid");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "ix_tag_external_ids_target_system_uuid",
                table: "tag_external_ids");

            migrationBuilder.DropIndex(
                name: "ix_sub_site_external_ids_target_system_uuid",
                table: "sub_site_external_ids");

            migrationBuilder.DropIndex(
                name: "ix_site_external_ids_target_system_uuid",
                table: "site_external_ids");

            migrationBuilder.DropIndex(
                name: "ix_release_external_ids_target_system_uuid",
                table: "release_external_ids");

            migrationBuilder.DropIndex(
                name: "ix_performer_external_ids_target_system_uuid",
                table: "performer_external_ids");

            migrationBuilder.CreateIndex(
                name: "ix_tag_external_ids_target_system_uuid_external_id",
                table: "tag_external_ids",
                columns: new[] { "target_system_uuid", "external_id" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_sub_site_external_ids_target_system_uuid_external_id",
                table: "sub_site_external_ids",
                columns: new[] { "target_system_uuid", "external_id" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_site_external_ids_target_system_uuid_external_id",
                table: "site_external_ids",
                columns: new[] { "target_system_uuid", "external_id" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_release_external_ids_target_system_uuid_external_id",
                table: "release_external_ids",
                columns: new[] { "target_system_uuid", "external_id" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_performer_external_ids_target_system_uuid_external_id",
                table: "performer_external_ids",
                columns: new[] { "target_system_uuid", "external_id" },
                unique: true);
        }
    }
}
