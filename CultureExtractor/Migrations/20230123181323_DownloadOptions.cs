using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class DownloadOptions : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.RenameColumn(
                name: "DownloadDetails",
                table: "Downloads",
                newName: "DownloadOptions");

            migrationBuilder.AddColumn<DateTime>(
                name: "Created",
                table: "Scenes",
                type: "TEXT",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.AddColumn<DateTime>(
                name: "LastUpdated",
                table: "Scenes",
                type: "TEXT",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.CreateTable(
                name: "DownloadOptions",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    Description = table.Column<string>(type: "TEXT", nullable: false),
                    Url = table.Column<string>(type: "TEXT", nullable: false),
                    ResolutionWidth = table.Column<int>(type: "INTEGER", nullable: true),
                    ResolutionHeight = table.Column<int>(type: "INTEGER", nullable: true),
                    FileSize = table.Column<double>(type: "REAL", nullable: true),
                    Fps = table.Column<double>(type: "REAL", nullable: true),
                    Codec = table.Column<string>(type: "TEXT", nullable: true),
                    SceneEntityId = table.Column<int>(type: "INTEGER", nullable: true)
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

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "DownloadOptions");

            migrationBuilder.DropColumn(
                name: "Created",
                table: "Scenes");

            migrationBuilder.DropColumn(
                name: "LastUpdated",
                table: "Scenes");

            migrationBuilder.RenameColumn(
                name: "DownloadOptions",
                table: "Downloads",
                newName: "DownloadDetails");
        }
    }
}
