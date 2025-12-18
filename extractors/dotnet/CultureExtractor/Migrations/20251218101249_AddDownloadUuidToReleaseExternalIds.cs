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
            migrationBuilder.DropIndex(
                name: "ix_release_external_ids_release_uuid_target_system_uuid",
                table: "release_external_ids");

            migrationBuilder.AddColumn<Guid>(
                name: "download_uuid",
                table: "release_external_ids",
                type: "uuid",
                nullable: true);

            migrationBuilder.CreateIndex(
                name: "ix_release_external_ids_download_uuid",
                table: "release_external_ids",
                column: "download_uuid");

            migrationBuilder.CreateIndex(
                name: "ix_release_external_ids_release_uuid_target_system_uuid_downlo",
                table: "release_external_ids",
                columns: new[] { "release_uuid", "target_system_uuid", "download_uuid" },
                unique: true);

            migrationBuilder.AddForeignKey(
                name: "fk_release_external_ids_downloads_download_uuid",
                table: "release_external_ids",
                column: "download_uuid",
                principalTable: "downloads",
                principalColumn: "uuid",
                onDelete: ReferentialAction.Cascade);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "fk_release_external_ids_downloads_download_uuid",
                table: "release_external_ids");

            migrationBuilder.DropIndex(
                name: "ix_release_external_ids_download_uuid",
                table: "release_external_ids");

            migrationBuilder.DropIndex(
                name: "ix_release_external_ids_release_uuid_target_system_uuid_downlo",
                table: "release_external_ids");

            migrationBuilder.DropColumn(
                name: "download_uuid",
                table: "release_external_ids");

            migrationBuilder.CreateIndex(
                name: "ix_release_external_ids_release_uuid_target_system_uuid",
                table: "release_external_ids",
                columns: new[] { "release_uuid", "target_system_uuid" },
                unique: true);
        }
    }
}
