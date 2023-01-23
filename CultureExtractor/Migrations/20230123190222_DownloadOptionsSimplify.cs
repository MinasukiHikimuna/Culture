using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class DownloadOptionsSimplify : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "DownloadOptions");

            migrationBuilder.AddColumn<string>(
                name: "DownloadOptions",
                table: "Scenes",
                type: "TEXT",
                nullable: false,
                defaultValue: "");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "DownloadOptions",
                table: "Scenes");

            migrationBuilder.CreateTable(
                name: "DownloadOptions",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    Codec = table.Column<string>(type: "TEXT", nullable: true),
                    Description = table.Column<string>(type: "TEXT", nullable: false),
                    FileSize = table.Column<double>(type: "REAL", nullable: true),
                    Fps = table.Column<double>(type: "REAL", nullable: true),
                    ResolutionHeight = table.Column<int>(type: "INTEGER", nullable: true),
                    ResolutionWidth = table.Column<int>(type: "INTEGER", nullable: true),
                    SceneEntityId = table.Column<int>(type: "INTEGER", nullable: true),
                    Url = table.Column<string>(type: "TEXT", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_DownloadOptions", x => x.Id);
                    table.ForeignKey(
                        name: "FK_DownloadOptions_Scenes_SceneEntityId",
                        column: x => x.SceneEntityId,
                        principalTable: "Scenes",
                        principalColumn: "Id");
                });

            migrationBuilder.CreateIndex(
                name: "IX_DownloadOptions_SceneEntityId",
                table: "DownloadOptions",
                column: "SceneEntityId");
        }
    }
}
