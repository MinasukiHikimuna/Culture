using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class RenameDownloadsSceneReferenceToRelease : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Downloads_Releases_SceneUuid",
                table: "Downloads");

            migrationBuilder.RenameColumn(
                name: "SceneUuid",
                table: "Downloads",
                newName: "ReleaseUuid");

            migrationBuilder.RenameIndex(
                name: "IX_Downloads_SceneUuid",
                table: "Downloads",
                newName: "IX_Downloads_ReleaseUuid");

            migrationBuilder.AddForeignKey(
                name: "FK_Downloads_Releases_ReleaseUuid",
                table: "Downloads",
                column: "ReleaseUuid",
                principalTable: "Releases",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Downloads_Releases_ReleaseUuid",
                table: "Downloads");

            migrationBuilder.RenameColumn(
                name: "ReleaseUuid",
                table: "Downloads",
                newName: "SceneUuid");

            migrationBuilder.RenameIndex(
                name: "IX_Downloads_ReleaseUuid",
                table: "Downloads",
                newName: "IX_Downloads_SceneUuid");

            migrationBuilder.AddForeignKey(
                name: "FK_Downloads_Releases_SceneUuid",
                table: "Downloads",
                column: "SceneUuid",
                principalTable: "Releases",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);
        }
    }
}
