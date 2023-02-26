using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class SubSite : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<int>(
                name: "SubSiteId",
                table: "Scenes",
                type: "INTEGER",
                nullable: true);

            migrationBuilder.CreateTable(
                name: "SubSites",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    ShortName = table.Column<string>(type: "TEXT", nullable: false),
                    Name = table.Column<string>(type: "TEXT", nullable: false),
                    SiteId = table.Column<int>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_SubSites", x => x.Id);
                    table.ForeignKey(
                        name: "FK_SubSites_Sites_SiteId",
                        column: x => x.SiteId,
                        principalTable: "Sites",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_Scenes_SubSiteId",
                table: "Scenes",
                column: "SubSiteId");

            migrationBuilder.CreateIndex(
                name: "IX_SubSites_SiteId",
                table: "SubSites",
                column: "SiteId");

            migrationBuilder.AddForeignKey(
                name: "FK_Scenes_Sites_SubSiteId",
                table: "Scenes",
                column: "SubSiteId",
                principalTable: "Sites",
                principalColumn: "Id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Scenes_Sites_SubSiteId",
                table: "Scenes");

            migrationBuilder.DropTable(
                name: "SubSites");

            migrationBuilder.DropIndex(
                name: "IX_Scenes_SubSiteId",
                table: "Scenes");

            migrationBuilder.DropColumn(
                name: "SubSiteId",
                table: "Scenes");
        }
    }
}
