using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class DownloadsReferredViaSceneUuid : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Downloads_Scenes_SceneId",
                table: "Downloads");

            migrationBuilder.DropIndex(
                name: "IX_Downloads_SceneId",
                table: "Downloads");

            migrationBuilder.DropColumn(
                name: "SceneId",
                table: "Downloads");

            migrationBuilder.AlterColumn<string>(
                name: "SceneUuid",
                table: "Downloads",
                type: "TEXT",
                nullable: false,
                defaultValue: "",
                oldClrType: typeof(string),
                oldType: "TEXT",
                oldNullable: true);

            migrationBuilder.AddUniqueConstraint(
                name: "AK_Scenes_Uuid",
                table: "Scenes",
                column: "Uuid");

            migrationBuilder.CreateIndex(
                name: "IX_Downloads_SceneUuid",
                table: "Downloads",
                column: "SceneUuid");

            migrationBuilder.AddForeignKey(
                name: "FK_Downloads_Scenes_SceneUuid",
                table: "Downloads",
                column: "SceneUuid",
                principalTable: "Scenes",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Downloads_Scenes_SceneUuid",
                table: "Downloads");

            migrationBuilder.DropUniqueConstraint(
                name: "AK_Scenes_Uuid",
                table: "Scenes");

            migrationBuilder.DropIndex(
                name: "IX_Downloads_SceneUuid",
                table: "Downloads");

            migrationBuilder.AlterColumn<string>(
                name: "SceneUuid",
                table: "Downloads",
                type: "TEXT",
                nullable: true,
                oldClrType: typeof(string),
                oldType: "TEXT");

            migrationBuilder.AddColumn<int>(
                name: "SceneId",
                table: "Downloads",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.CreateIndex(
                name: "IX_Downloads_SceneId",
                table: "Downloads",
                column: "SceneId");

            migrationBuilder.AddForeignKey(
                name: "FK_Downloads_Scenes_SceneId",
                table: "Downloads",
                column: "SceneId",
                principalTable: "Scenes",
                principalColumn: "Id",
                onDelete: ReferentialAction.Cascade);
        }
    }
}
