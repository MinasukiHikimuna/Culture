using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class RenameDownloadOptionToAvailableFile : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.RenameColumn(
                name: "DownloadOptions",
                table: "Releases",
                newName: "AvailableFiles");

            migrationBuilder.RenameColumn(
                name: "DownloadOptions",
                table: "Downloads",
                newName: "AvailableFile");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.RenameColumn(
                name: "AvailableFiles",
                table: "Releases",
                newName: "DownloadOptions");

            migrationBuilder.RenameColumn(
                name: "AvailableFile",
                table: "Downloads",
                newName: "DownloadOptions");
        }
    }
}
