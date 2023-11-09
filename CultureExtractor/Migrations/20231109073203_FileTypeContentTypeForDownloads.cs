using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class FileTypeContentTypeForDownloads : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.RenameColumn(
                name: "DownloadQuality",
                table: "Downloads",
                newName: "Variant");

            migrationBuilder.AddColumn<string>(
                name: "ContentType",
                table: "Downloads",
                type: "TEXT",
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddColumn<string>(
                name: "FileType",
                table: "Downloads",
                type: "TEXT",
                nullable: false,
                defaultValue: "");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "ContentType",
                table: "Downloads");

            migrationBuilder.DropColumn(
                name: "FileType",
                table: "Downloads");

            migrationBuilder.RenameColumn(
                name: "Variant",
                table: "Downloads",
                newName: "DownloadQuality");
        }
    }
}
