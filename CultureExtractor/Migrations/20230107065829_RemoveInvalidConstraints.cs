using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace RipperPlaywright.Migrations
{
    /// <inheritdoc />
    public partial class RemoveInvalidConstraints : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Performers_GalleryEntity_GalleryEntityId",
                table: "Performers");

            migrationBuilder.DropForeignKey(
                name: "FK_Tags_GalleryEntity_GalleryEntityId",
                table: "Tags");

            migrationBuilder.DropTable(
                name: "GalleryEntity");

            migrationBuilder.DropUniqueConstraint(
                name: "AK_Tags_Name",
                table: "Tags");

            migrationBuilder.DropUniqueConstraint(
                name: "AK_Tags_ShortName",
                table: "Tags");

            migrationBuilder.DropUniqueConstraint(
                name: "AK_Tags_Url",
                table: "Tags");

            migrationBuilder.DropIndex(
                name: "IX_Tags_GalleryEntityId",
                table: "Tags");

            migrationBuilder.DropUniqueConstraint(
                name: "AK_Sites_Name",
                table: "Sites");

            migrationBuilder.DropUniqueConstraint(
                name: "AK_Sites_ShortName",
                table: "Sites");

            migrationBuilder.DropUniqueConstraint(
                name: "AK_Sites_Url",
                table: "Sites");

            migrationBuilder.DropUniqueConstraint(
                name: "AK_Scenes_Name",
                table: "Scenes");

            migrationBuilder.DropUniqueConstraint(
                name: "AK_Scenes_ShortName",
                table: "Scenes");

            migrationBuilder.DropUniqueConstraint(
                name: "AK_Scenes_Url",
                table: "Scenes");

            migrationBuilder.DropUniqueConstraint(
                name: "AK_Performers_Name",
                table: "Performers");

            migrationBuilder.DropUniqueConstraint(
                name: "AK_Performers_ShortName",
                table: "Performers");

            migrationBuilder.DropUniqueConstraint(
                name: "AK_Performers_Url",
                table: "Performers");

            migrationBuilder.DropIndex(
                name: "IX_Performers_GalleryEntityId",
                table: "Performers");

            migrationBuilder.DropColumn(
                name: "GalleryEntityId",
                table: "Tags");

            migrationBuilder.DropColumn(
                name: "GalleryEntityId",
                table: "Performers");

            migrationBuilder.AlterColumn<string>(
                name: "Url",
                table: "Tags",
                type: "TEXT",
                nullable: true,
                oldClrType: typeof(string),
                oldType: "TEXT");

            migrationBuilder.AlterColumn<string>(
                name: "ShortName",
                table: "Tags",
                type: "TEXT",
                nullable: true,
                oldClrType: typeof(string),
                oldType: "TEXT");

            migrationBuilder.AlterColumn<string>(
                name: "Url",
                table: "Performers",
                type: "TEXT",
                nullable: true,
                oldClrType: typeof(string),
                oldType: "TEXT");

            migrationBuilder.AlterColumn<string>(
                name: "ShortName",
                table: "Performers",
                type: "TEXT",
                nullable: true,
                oldClrType: typeof(string),
                oldType: "TEXT");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AlterColumn<string>(
                name: "Url",
                table: "Tags",
                type: "TEXT",
                nullable: false,
                defaultValue: "",
                oldClrType: typeof(string),
                oldType: "TEXT",
                oldNullable: true);

            migrationBuilder.AlterColumn<string>(
                name: "ShortName",
                table: "Tags",
                type: "TEXT",
                nullable: false,
                defaultValue: "",
                oldClrType: typeof(string),
                oldType: "TEXT",
                oldNullable: true);

            migrationBuilder.AddColumn<int>(
                name: "GalleryEntityId",
                table: "Tags",
                type: "INTEGER",
                nullable: true);

            migrationBuilder.AlterColumn<string>(
                name: "Url",
                table: "Performers",
                type: "TEXT",
                nullable: false,
                defaultValue: "",
                oldClrType: typeof(string),
                oldType: "TEXT",
                oldNullable: true);

            migrationBuilder.AlterColumn<string>(
                name: "ShortName",
                table: "Performers",
                type: "TEXT",
                nullable: false,
                defaultValue: "",
                oldClrType: typeof(string),
                oldType: "TEXT",
                oldNullable: true);

            migrationBuilder.AddColumn<int>(
                name: "GalleryEntityId",
                table: "Performers",
                type: "INTEGER",
                nullable: true);

            migrationBuilder.AddUniqueConstraint(
                name: "AK_Tags_Name",
                table: "Tags",
                column: "Name");

            migrationBuilder.AddUniqueConstraint(
                name: "AK_Tags_ShortName",
                table: "Tags",
                column: "ShortName");

            migrationBuilder.AddUniqueConstraint(
                name: "AK_Tags_Url",
                table: "Tags",
                column: "Url");

            migrationBuilder.AddUniqueConstraint(
                name: "AK_Sites_Name",
                table: "Sites",
                column: "Name");

            migrationBuilder.AddUniqueConstraint(
                name: "AK_Sites_ShortName",
                table: "Sites",
                column: "ShortName");

            migrationBuilder.AddUniqueConstraint(
                name: "AK_Sites_Url",
                table: "Sites",
                column: "Url");

            migrationBuilder.AddUniqueConstraint(
                name: "AK_Scenes_Name",
                table: "Scenes",
                column: "Name");

            migrationBuilder.AddUniqueConstraint(
                name: "AK_Scenes_ShortName",
                table: "Scenes",
                column: "ShortName");

            migrationBuilder.AddUniqueConstraint(
                name: "AK_Scenes_Url",
                table: "Scenes",
                column: "Url");

            migrationBuilder.AddUniqueConstraint(
                name: "AK_Performers_Name",
                table: "Performers",
                column: "Name");

            migrationBuilder.AddUniqueConstraint(
                name: "AK_Performers_ShortName",
                table: "Performers",
                column: "ShortName");

            migrationBuilder.AddUniqueConstraint(
                name: "AK_Performers_Url",
                table: "Performers",
                column: "Url");

            migrationBuilder.CreateTable(
                name: "GalleryEntity",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    SiteId = table.Column<int>(type: "INTEGER", nullable: false),
                    Name = table.Column<string>(type: "TEXT", nullable: false),
                    Pictures = table.Column<int>(type: "INTEGER", nullable: false),
                    ReleaseDate = table.Column<DateOnly>(type: "TEXT", nullable: false),
                    ShortName = table.Column<string>(type: "TEXT", nullable: false),
                    Url = table.Column<string>(type: "TEXT", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_GalleryEntity", x => x.Id);
                    table.UniqueConstraint("AK_GalleryEntity_Name", x => x.Name);
                    table.UniqueConstraint("AK_GalleryEntity_ShortName", x => x.ShortName);
                    table.UniqueConstraint("AK_GalleryEntity_Url", x => x.Url);
                    table.ForeignKey(
                        name: "FK_GalleryEntity_Sites_SiteId",
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
                name: "IX_GalleryEntity_SiteId",
                table: "GalleryEntity",
                column: "SiteId");

            migrationBuilder.AddForeignKey(
                name: "FK_Performers_GalleryEntity_GalleryEntityId",
                table: "Performers",
                column: "GalleryEntityId",
                principalTable: "GalleryEntity",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_Tags_GalleryEntity_GalleryEntityId",
                table: "Tags",
                column: "GalleryEntityId",
                principalTable: "GalleryEntity",
                principalColumn: "Id");
        }
    }
}
