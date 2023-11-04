using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class RenameSitePerformerEntitySceneReferenceToRelease : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySitePerformerEntity_Releases_ScenesUuid",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.RenameColumn(
                name: "ScenesUuid",
                table: "SceneEntitySitePerformerEntity",
                newName: "ReleasesUuid");

            migrationBuilder.RenameIndex(
                name: "IX_SceneEntitySitePerformerEntity_ScenesUuid",
                table: "SceneEntitySitePerformerEntity",
                newName: "IX_SceneEntitySitePerformerEntity_ReleasesUuid");

            migrationBuilder.AddForeignKey(
                name: "FK_SceneEntitySitePerformerEntity_Releases_ReleasesUuid",
                table: "SceneEntitySitePerformerEntity",
                column: "ReleasesUuid",
                principalTable: "Releases",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySitePerformerEntity_Releases_ReleasesUuid",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.RenameColumn(
                name: "ReleasesUuid",
                table: "SceneEntitySitePerformerEntity",
                newName: "ScenesUuid");

            migrationBuilder.RenameIndex(
                name: "IX_SceneEntitySitePerformerEntity_ReleasesUuid",
                table: "SceneEntitySitePerformerEntity",
                newName: "IX_SceneEntitySitePerformerEntity_ScenesUuid");

            migrationBuilder.AddForeignKey(
                name: "FK_SceneEntitySitePerformerEntity_Releases_ScenesUuid",
                table: "SceneEntitySitePerformerEntity",
                column: "ScenesUuid",
                principalTable: "Releases",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);
        }
    }
}
