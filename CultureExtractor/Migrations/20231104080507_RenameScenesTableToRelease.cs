using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class RenameScenesTableToRelease : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Downloads_Scenes_SceneUuid",
                table: "Downloads");

            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySitePerformerEntity_Scenes_ScenesUuid",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySiteTagEntity_Scenes_ScenesUuid",
                table: "SceneEntitySiteTagEntity");

            migrationBuilder.DropForeignKey(
                name: "FK_Scenes_Sites_SiteUuid",
                table: "Scenes");

            migrationBuilder.DropForeignKey(
                name: "FK_Scenes_SubSites_SubSiteUuid",
                table: "Scenes");

            migrationBuilder.DropPrimaryKey(
                name: "PK_Scenes",
                table: "Scenes");

            migrationBuilder.RenameTable(
                name: "Scenes",
                newName: "Releases");

            migrationBuilder.RenameIndex(
                name: "IX_Scenes_SubSiteUuid",
                table: "Releases",
                newName: "IX_Releases_SubSiteUuid");

            migrationBuilder.RenameIndex(
                name: "IX_Scenes_SiteUuid",
                table: "Releases",
                newName: "IX_Releases_SiteUuid");

            migrationBuilder.AddPrimaryKey(
                name: "PK_Releases",
                table: "Releases",
                column: "Uuid");

            migrationBuilder.AddForeignKey(
                name: "FK_Downloads_Releases_SceneUuid",
                table: "Downloads",
                column: "SceneUuid",
                principalTable: "Releases",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_Releases_Sites_SiteUuid",
                table: "Releases",
                column: "SiteUuid",
                principalTable: "Sites",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_Releases_SubSites_SubSiteUuid",
                table: "Releases",
                column: "SubSiteUuid",
                principalTable: "SubSites",
                principalColumn: "Uuid");

            migrationBuilder.AddForeignKey(
                name: "FK_SceneEntitySitePerformerEntity_Releases_ScenesUuid",
                table: "SceneEntitySitePerformerEntity",
                column: "ScenesUuid",
                principalTable: "Releases",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_SceneEntitySiteTagEntity_Releases_ScenesUuid",
                table: "SceneEntitySiteTagEntity",
                column: "ScenesUuid",
                principalTable: "Releases",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Downloads_Releases_SceneUuid",
                table: "Downloads");

            migrationBuilder.DropForeignKey(
                name: "FK_Releases_Sites_SiteUuid",
                table: "Releases");

            migrationBuilder.DropForeignKey(
                name: "FK_Releases_SubSites_SubSiteUuid",
                table: "Releases");

            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySitePerformerEntity_Releases_ScenesUuid",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySiteTagEntity_Releases_ScenesUuid",
                table: "SceneEntitySiteTagEntity");

            migrationBuilder.DropPrimaryKey(
                name: "PK_Releases",
                table: "Releases");

            migrationBuilder.RenameTable(
                name: "Releases",
                newName: "Scenes");

            migrationBuilder.RenameIndex(
                name: "IX_Releases_SubSiteUuid",
                table: "Scenes",
                newName: "IX_Scenes_SubSiteUuid");

            migrationBuilder.RenameIndex(
                name: "IX_Releases_SiteUuid",
                table: "Scenes",
                newName: "IX_Scenes_SiteUuid");

            migrationBuilder.AddPrimaryKey(
                name: "PK_Scenes",
                table: "Scenes",
                column: "Uuid");

            migrationBuilder.AddForeignKey(
                name: "FK_Downloads_Scenes_SceneUuid",
                table: "Downloads",
                column: "SceneUuid",
                principalTable: "Scenes",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_SceneEntitySitePerformerEntity_Scenes_ScenesUuid",
                table: "SceneEntitySitePerformerEntity",
                column: "ScenesUuid",
                principalTable: "Scenes",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_SceneEntitySiteTagEntity_Scenes_ScenesUuid",
                table: "SceneEntitySiteTagEntity",
                column: "ScenesUuid",
                principalTable: "Scenes",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_Scenes_Sites_SiteUuid",
                table: "Scenes",
                column: "SiteUuid",
                principalTable: "Sites",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_Scenes_SubSites_SubSiteUuid",
                table: "Scenes",
                column: "SubSiteUuid",
                principalTable: "SubSites",
                principalColumn: "Uuid");
        }
    }
}
