using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class SceneIdRemoved : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySitePerformerEntity_Scenes_ScenesId",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySiteTagEntity_Scenes_ScenesUuid",
                table: "SceneEntitySiteTagEntity");

            migrationBuilder.DropUniqueConstraint(
                name: "AK_Scenes_Uuid",
                table: "Scenes");

            migrationBuilder.DropPrimaryKey(
                name: "PK_Scenes",
                table: "Scenes");

            migrationBuilder.DropPrimaryKey(
                name: "PK_SceneEntitySitePerformerEntity",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.DropIndex(
                name: "IX_SceneEntitySitePerformerEntity_ScenesId",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.DropColumn(
                name: "Id",
                table: "Scenes");

            migrationBuilder.DropColumn(
                name: "ScenesId",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.AlterColumn<string>(
                name: "ScenesUuid",
                table: "SceneEntitySiteTagEntity",
                type: "TEXT",
                nullable: false,
                oldClrType: typeof(int),
                oldType: "INTEGER");

            migrationBuilder.AddColumn<string>(
                name: "ScenesUuid",
                table: "SceneEntitySitePerformerEntity",
                type: "TEXT",
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddPrimaryKey(
                name: "PK_Scenes",
                table: "Scenes",
                column: "Uuid");

            migrationBuilder.AddPrimaryKey(
                name: "PK_SceneEntitySitePerformerEntity",
                table: "SceneEntitySitePerformerEntity",
                columns: new[] { "PerformersId", "ScenesUuid" });

            migrationBuilder.CreateIndex(
                name: "IX_SceneEntitySitePerformerEntity_ScenesUuid",
                table: "SceneEntitySitePerformerEntity",
                column: "ScenesUuid");

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
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySitePerformerEntity_Scenes_ScenesUuid",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySiteTagEntity_Scenes_ScenesUuid",
                table: "SceneEntitySiteTagEntity");

            migrationBuilder.DropPrimaryKey(
                name: "PK_Scenes",
                table: "Scenes");

            migrationBuilder.DropPrimaryKey(
                name: "PK_SceneEntitySitePerformerEntity",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.DropIndex(
                name: "IX_SceneEntitySitePerformerEntity_ScenesUuid",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.DropColumn(
                name: "ScenesUuid",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.AddColumn<int>(
                name: "Id",
                table: "Scenes",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0)
                .Annotation("Sqlite:Autoincrement", true);

            migrationBuilder.AlterColumn<int>(
                name: "ScenesUuid",
                table: "SceneEntitySiteTagEntity",
                type: "INTEGER",
                nullable: false,
                oldClrType: typeof(string),
                oldType: "TEXT");

            migrationBuilder.AddColumn<int>(
                name: "ScenesId",
                table: "SceneEntitySitePerformerEntity",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddUniqueConstraint(
                name: "AK_Scenes_Uuid",
                table: "Scenes",
                column: "Uuid");

            migrationBuilder.AddPrimaryKey(
                name: "PK_Scenes",
                table: "Scenes",
                column: "Id");

            migrationBuilder.AddPrimaryKey(
                name: "PK_SceneEntitySitePerformerEntity",
                table: "SceneEntitySitePerformerEntity",
                columns: new[] { "PerformersId", "ScenesId" });

            migrationBuilder.CreateIndex(
                name: "IX_SceneEntitySitePerformerEntity_ScenesId",
                table: "SceneEntitySitePerformerEntity",
                column: "ScenesId");

            migrationBuilder.AddForeignKey(
                name: "FK_SceneEntitySitePerformerEntity_Scenes_ScenesId",
                table: "SceneEntitySitePerformerEntity",
                column: "ScenesId",
                principalTable: "Scenes",
                principalColumn: "Id",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_SceneEntitySiteTagEntity_Scenes_ScenesUuid",
                table: "SceneEntitySiteTagEntity",
                column: "ScenesUuid",
                principalTable: "Scenes",
                principalColumn: "Id",
                onDelete: ReferentialAction.Cascade);
        }
    }
}
