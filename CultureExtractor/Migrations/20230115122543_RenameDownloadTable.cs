using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class RenameDownloadTable : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_DownloadEntities_Scenes_SceneId",
                table: "DownloadEntities");

            migrationBuilder.DropPrimaryKey(
                name: "PK_DownloadEntities",
                table: "DownloadEntities");

            migrationBuilder.RenameTable(
                name: "DownloadEntities",
                newName: "Downloads");

            migrationBuilder.RenameIndex(
                name: "IX_DownloadEntities_SceneId",
                table: "Downloads",
                newName: "IX_Downloads_SceneId");

            migrationBuilder.AddPrimaryKey(
                name: "PK_Downloads",
                table: "Downloads",
                column: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_Downloads_Scenes_SceneId",
                table: "Downloads",
                column: "SceneId",
                principalTable: "Scenes",
                principalColumn: "Id",
                onDelete: ReferentialAction.Cascade);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Downloads_Scenes_SceneId",
                table: "Downloads");

            migrationBuilder.DropPrimaryKey(
                name: "PK_Downloads",
                table: "Downloads");

            migrationBuilder.RenameTable(
                name: "Downloads",
                newName: "DownloadEntities");

            migrationBuilder.RenameIndex(
                name: "IX_Downloads_SceneId",
                table: "DownloadEntities",
                newName: "IX_DownloadEntities_SceneId");

            migrationBuilder.AddPrimaryKey(
                name: "PK_DownloadEntities",
                table: "DownloadEntities",
                column: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_DownloadEntities_Scenes_SceneId",
                table: "DownloadEntities",
                column: "SceneId",
                principalTable: "Scenes",
                principalColumn: "Id",
                onDelete: ReferentialAction.Cascade);
        }
    }
}
