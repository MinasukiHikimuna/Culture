using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class SitePerformerUuidPrimaryKey : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySitePerformerEntity_Performers_PerformersId",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.DropPrimaryKey(
                name: "PK_SceneEntitySitePerformerEntity",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.DropPrimaryKey(
                name: "PK_Performers",
                table: "Performers");

            migrationBuilder.DropColumn(
                name: "PerformersId",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.DropColumn(
                name: "Id",
                table: "Performers");

            migrationBuilder.AddColumn<string>(
                name: "PerformersUuid",
                table: "SceneEntitySitePerformerEntity",
                type: "TEXT",
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddPrimaryKey(
                name: "PK_SceneEntitySitePerformerEntity",
                table: "SceneEntitySitePerformerEntity",
                columns: new[] { "PerformersUuid", "ScenesUuid" });

            migrationBuilder.AddPrimaryKey(
                name: "PK_Performers",
                table: "Performers",
                column: "Uuid");

            migrationBuilder.AddForeignKey(
                name: "FK_SceneEntitySitePerformerEntity_Performers_PerformersUuid",
                table: "SceneEntitySitePerformerEntity",
                column: "PerformersUuid",
                principalTable: "Performers",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySitePerformerEntity_Performers_PerformersUuid",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.DropPrimaryKey(
                name: "PK_SceneEntitySitePerformerEntity",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.DropPrimaryKey(
                name: "PK_Performers",
                table: "Performers");

            migrationBuilder.DropColumn(
                name: "PerformersUuid",
                table: "SceneEntitySitePerformerEntity");

            migrationBuilder.AddColumn<int>(
                name: "PerformersId",
                table: "SceneEntitySitePerformerEntity",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddColumn<int>(
                name: "Id",
                table: "Performers",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0)
                .Annotation("Sqlite:Autoincrement", true);

            migrationBuilder.AddPrimaryKey(
                name: "PK_SceneEntitySitePerformerEntity",
                table: "SceneEntitySitePerformerEntity",
                columns: new[] { "PerformersId", "ScenesUuid" });

            migrationBuilder.AddPrimaryKey(
                name: "PK_Performers",
                table: "Performers",
                column: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_SceneEntitySitePerformerEntity_Performers_PerformersId",
                table: "SceneEntitySitePerformerEntity",
                column: "PerformersId",
                principalTable: "Performers",
                principalColumn: "Id",
                onDelete: ReferentialAction.Cascade);
        }
    }
}
