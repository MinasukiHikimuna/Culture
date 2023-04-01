using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class SubSiteForeignKeyFix : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Scenes_Sites_SubSiteId",
                table: "Scenes");

            migrationBuilder.AddForeignKey(
                name: "FK_Scenes_SubSites_SubSiteId",
                table: "Scenes",
                column: "SubSiteId",
                principalTable: "SubSites",
                principalColumn: "Id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Scenes_SubSites_SubSiteId",
                table: "Scenes");

            migrationBuilder.AddForeignKey(
                name: "FK_Scenes_Sites_SubSiteId",
                table: "Scenes",
                column: "SubSiteId",
                principalTable: "Sites",
                principalColumn: "Id");
        }
    }
}
