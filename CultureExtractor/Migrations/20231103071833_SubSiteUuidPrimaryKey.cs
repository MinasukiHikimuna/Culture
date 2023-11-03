using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class SubSiteUuidPrimaryKey : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Scenes_SubSites_SubSiteId",
                table: "Scenes");

            migrationBuilder.DropPrimaryKey(
                name: "PK_SubSites",
                table: "SubSites");

            migrationBuilder.DropIndex(
                name: "IX_Scenes_SubSiteId",
                table: "Scenes");

            migrationBuilder.DropColumn(
                name: "Id",
                table: "SubSites");

            migrationBuilder.DropColumn(
                name: "SubSiteId",
                table: "Scenes");

            migrationBuilder.AddColumn<string>(
                name: "SubSiteUuid",
                table: "Scenes",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddPrimaryKey(
                name: "PK_SubSites",
                table: "SubSites",
                column: "Uuid");

            migrationBuilder.CreateIndex(
                name: "IX_Scenes_SubSiteUuid",
                table: "Scenes",
                column: "SubSiteUuid");

            migrationBuilder.AddForeignKey(
                name: "FK_Scenes_SubSites_SubSiteUuid",
                table: "Scenes",
                column: "SubSiteUuid",
                principalTable: "SubSites",
                principalColumn: "Uuid");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Scenes_SubSites_SubSiteUuid",
                table: "Scenes");

            migrationBuilder.DropPrimaryKey(
                name: "PK_SubSites",
                table: "SubSites");

            migrationBuilder.DropIndex(
                name: "IX_Scenes_SubSiteUuid",
                table: "Scenes");

            migrationBuilder.DropColumn(
                name: "SubSiteUuid",
                table: "Scenes");

            migrationBuilder.AddColumn<int>(
                name: "Id",
                table: "SubSites",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0)
                .Annotation("Sqlite:Autoincrement", true);

            migrationBuilder.AddColumn<int>(
                name: "SubSiteId",
                table: "Scenes",
                type: "INTEGER",
                nullable: true);

            migrationBuilder.AddPrimaryKey(
                name: "PK_SubSites",
                table: "SubSites",
                column: "Id");

            migrationBuilder.CreateIndex(
                name: "IX_Scenes_SubSiteId",
                table: "Scenes",
                column: "SubSiteId");

            migrationBuilder.AddForeignKey(
                name: "FK_Scenes_SubSites_SubSiteId",
                table: "Scenes",
                column: "SubSiteId",
                principalTable: "SubSites",
                principalColumn: "Id");
        }
    }
}
