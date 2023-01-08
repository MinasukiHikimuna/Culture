using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace RipperPlaywright.Migrations
{
    /// <inheritdoc />
    public partial class Galleries : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<int>(
                name: "GalleryEntityId",
                table: "Tags",
                type: "INTEGER",
                nullable: true);

            migrationBuilder.AddColumn<int>(
                name: "GalleryEntityId",
                table: "Performers",
                type: "INTEGER",
                nullable: true);

            migrationBuilder.CreateTable(
                name: "Galleries",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    ReleaseDate = table.Column<DateOnly>(type: "TEXT", nullable: false),
                    ShortName = table.Column<string>(type: "TEXT", nullable: false),
                    Name = table.Column<string>(type: "TEXT", nullable: false),
                    Url = table.Column<string>(type: "TEXT", nullable: false),
                    Description = table.Column<string>(type: "TEXT", nullable: false),
                    Pictures = table.Column<int>(type: "INTEGER", nullable: false),
                    SiteId = table.Column<int>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Galleries", x => x.Id);
                    table.ForeignKey(
                        name: "FK_Galleries_Sites_SiteId",
                        column: x => x.SiteId,
                        principalTable: "Sites",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_Tags_GalleryEntityId",
                table: "Tags",
                column: "GalleryEntityId");

            migrationBuilder.CreateIndex(
                name: "IX_Performers_GalleryEntityId",
                table: "Performers",
                column: "GalleryEntityId");

            migrationBuilder.CreateIndex(
                name: "IX_Galleries_SiteId",
                table: "Galleries",
                column: "SiteId");

            migrationBuilder.AddForeignKey(
                name: "FK_Performers_Galleries_GalleryEntityId",
                table: "Performers",
                column: "GalleryEntityId",
                principalTable: "Galleries",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_Tags_Galleries_GalleryEntityId",
                table: "Tags",
                column: "GalleryEntityId",
                principalTable: "Galleries",
                principalColumn: "Id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Performers_Galleries_GalleryEntityId",
                table: "Performers");

            migrationBuilder.DropForeignKey(
                name: "FK_Tags_Galleries_GalleryEntityId",
                table: "Tags");

            migrationBuilder.DropTable(
                name: "Galleries");

            migrationBuilder.DropIndex(
                name: "IX_Tags_GalleryEntityId",
                table: "Tags");

            migrationBuilder.DropIndex(
                name: "IX_Performers_GalleryEntityId",
                table: "Performers");

            migrationBuilder.DropColumn(
                name: "GalleryEntityId",
                table: "Tags");

            migrationBuilder.DropColumn(
                name: "GalleryEntityId",
                table: "Performers");
        }
    }
}
