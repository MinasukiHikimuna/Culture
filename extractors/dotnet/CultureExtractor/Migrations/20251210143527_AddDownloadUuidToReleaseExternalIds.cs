using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class AddDownloadUuidToReleaseExternalIds : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // Add download_uuid column (nullable)
            migrationBuilder.AddColumn<Guid>(
                name: "download_uuid",
                table: "release_external_ids",
                type: "uuid",
                nullable: true);

            // Add foreign key to downloads table
            migrationBuilder.AddForeignKey(
                name: "fk_release_external_ids_downloads_download_uuid",
                table: "release_external_ids",
                column: "download_uuid",
                principalTable: "downloads",
                principalColumn: "uuid",
                onDelete: ReferentialAction.Cascade);

            // Drop the old unique index
            migrationBuilder.DropIndex(
                name: "ix_release_external_ids_release_uuid_target_system_uuid",
                table: "release_external_ids");

            // Create new unique index including download_uuid
            // NULLS NOT DISTINCT ensures (release, target, NULL) is treated as unique
            migrationBuilder.Sql(
                @"CREATE UNIQUE INDEX ix_release_external_ids_rel_ts_dl
                  ON release_external_ids (release_uuid, target_system_uuid, download_uuid)
                  NULLS NOT DISTINCT");

            // Add index on download_uuid for faster lookups
            migrationBuilder.CreateIndex(
                name: "ix_release_external_ids_download_uuid",
                table: "release_external_ids",
                column: "download_uuid");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            // Drop the new indexes
            migrationBuilder.DropIndex(
                name: "ix_release_external_ids_rel_ts_dl",
                table: "release_external_ids");

            migrationBuilder.DropIndex(
                name: "ix_release_external_ids_download_uuid",
                table: "release_external_ids");

            // Drop the foreign key
            migrationBuilder.DropForeignKey(
                name: "fk_release_external_ids_downloads_download_uuid",
                table: "release_external_ids");

            // Drop the column
            migrationBuilder.DropColumn(
                name: "download_uuid",
                table: "release_external_ids");

            // Recreate the old unique index
            migrationBuilder.CreateIndex(
                name: "ix_release_external_ids_release_uuid_target_system_uuid",
                table: "release_external_ids",
                columns: new[] { "release_uuid", "target_system_uuid" },
                unique: true);
        }
    }
}
