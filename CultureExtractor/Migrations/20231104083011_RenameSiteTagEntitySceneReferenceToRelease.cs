using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class RenameSiteTagEntitySceneReferenceToRelease : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySiteTagEntity_Releases_ScenesUuid",
                table: "SceneEntitySiteTagEntity");

            migrationBuilder.RenameColumn(
                name: "ScenesUuid",
                table: "SceneEntitySiteTagEntity",
                newName: "ReleasesUuid");

            migrationBuilder.AddForeignKey(
                name: "FK_SceneEntitySiteTagEntity_Releases_ReleasesUuid",
                table: "SceneEntitySiteTagEntity",
                column: "ReleasesUuid",
                principalTable: "Releases",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySiteTagEntity_Releases_ReleasesUuid",
                table: "SceneEntitySiteTagEntity");

            migrationBuilder.RenameColumn(
                name: "ReleasesUuid",
                table: "SceneEntitySiteTagEntity",
                newName: "ScenesUuid");

            migrationBuilder.AddForeignKey(
                name: "FK_SceneEntitySiteTagEntity_Releases_ScenesUuid",
                table: "SceneEntitySiteTagEntity",
                column: "ScenesUuid",
                principalTable: "Releases",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);
        }
    }
}
