using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class TagsUuidPrimaryKey : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySiteTagEntity_Tags_TagsId",
                table: "SceneEntitySiteTagEntity");

            migrationBuilder.DropPrimaryKey(
                name: "PK_Tags",
                table: "Tags");

            migrationBuilder.DropPrimaryKey(
                name: "PK_SceneEntitySiteTagEntity",
                table: "SceneEntitySiteTagEntity");

            migrationBuilder.DropIndex(
                name: "IX_SceneEntitySiteTagEntity_TagsId",
                table: "SceneEntitySiteTagEntity");

            migrationBuilder.DropColumn(
                name: "Id",
                table: "Tags");

            migrationBuilder.DropColumn(
                name: "TagsId",
                table: "SceneEntitySiteTagEntity");

            migrationBuilder.AddColumn<string>(
                name: "TagsUuid",
                table: "SceneEntitySiteTagEntity",
                type: "TEXT",
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddPrimaryKey(
                name: "PK_Tags",
                table: "Tags",
                column: "Uuid");

            migrationBuilder.AddPrimaryKey(
                name: "PK_SceneEntitySiteTagEntity",
                table: "SceneEntitySiteTagEntity",
                columns: new[] { "ScenesUuid", "TagsUuid" });

            migrationBuilder.CreateIndex(
                name: "IX_SceneEntitySiteTagEntity_TagsUuid",
                table: "SceneEntitySiteTagEntity",
                column: "TagsUuid");

            migrationBuilder.AddForeignKey(
                name: "FK_SceneEntitySiteTagEntity_Tags_TagsUuid",
                table: "SceneEntitySiteTagEntity",
                column: "TagsUuid",
                principalTable: "Tags",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_SceneEntitySiteTagEntity_Tags_TagsUuid",
                table: "SceneEntitySiteTagEntity");

            migrationBuilder.DropPrimaryKey(
                name: "PK_Tags",
                table: "Tags");

            migrationBuilder.DropPrimaryKey(
                name: "PK_SceneEntitySiteTagEntity",
                table: "SceneEntitySiteTagEntity");

            migrationBuilder.DropIndex(
                name: "IX_SceneEntitySiteTagEntity_TagsUuid",
                table: "SceneEntitySiteTagEntity");

            migrationBuilder.DropColumn(
                name: "TagsUuid",
                table: "SceneEntitySiteTagEntity");

            migrationBuilder.AddColumn<int>(
                name: "Id",
                table: "Tags",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0)
                .Annotation("Sqlite:Autoincrement", true);

            migrationBuilder.AddColumn<int>(
                name: "TagsId",
                table: "SceneEntitySiteTagEntity",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddPrimaryKey(
                name: "PK_Tags",
                table: "Tags",
                column: "Id");

            migrationBuilder.AddPrimaryKey(
                name: "PK_SceneEntitySiteTagEntity",
                table: "SceneEntitySiteTagEntity",
                columns: new[] { "ScenesUuid", "TagsId" });

            migrationBuilder.CreateIndex(
                name: "IX_SceneEntitySiteTagEntity_TagsId",
                table: "SceneEntitySiteTagEntity",
                column: "TagsId");

            migrationBuilder.AddForeignKey(
                name: "FK_SceneEntitySiteTagEntity_Tags_TagsId",
                table: "SceneEntitySiteTagEntity",
                column: "TagsId",
                principalTable: "Tags",
                principalColumn: "Id",
                onDelete: ReferentialAction.Cascade);
        }
    }
}
