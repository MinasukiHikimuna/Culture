using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class DownloadsDownloadedAtTimestamp : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AlterColumn<DateTime>(
                name: "downloaded_at",
                table: "downloads",
                type: "timestamp",
                nullable: false,
                oldClrType: typeof(DateTime),
                oldType: "timestamp with time zone");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AlterColumn<DateTime>(
                name: "downloaded_at",
                table: "downloads",
                type: "timestamp with time zone",
                nullable: false,
                oldClrType: typeof(DateTime),
                oldType: "timestamp");
        }
    }
}
