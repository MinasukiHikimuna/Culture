using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class SiteEntityUuidPrimaryKey : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Performers_Sites_SiteId",
                table: "Performers");

            migrationBuilder.DropForeignKey(
                name: "FK_Scenes_Sites_SiteId",
                table: "Scenes");

            migrationBuilder.DropForeignKey(
                name: "FK_StorageStates_Sites_SiteId",
                table: "StorageStates");

            migrationBuilder.DropForeignKey(
                name: "FK_SubSites_Sites_SiteId",
                table: "SubSites");

            migrationBuilder.DropForeignKey(
                name: "FK_Tags_Sites_SiteId",
                table: "Tags");

            migrationBuilder.DropIndex(
                name: "IX_Tags_SiteId",
                table: "Tags");

            migrationBuilder.DropIndex(
                name: "IX_SubSites_SiteId",
                table: "SubSites");

            migrationBuilder.DropIndex(
                name: "IX_StorageStates_SiteId",
                table: "StorageStates");

            migrationBuilder.DropPrimaryKey(
                name: "PK_Sites",
                table: "Sites");

            migrationBuilder.DropIndex(
                name: "IX_Scenes_SiteId",
                table: "Scenes");

            migrationBuilder.DropIndex(
                name: "IX_Performers_SiteId",
                table: "Performers");

            migrationBuilder.DropColumn(
                name: "SiteId",
                table: "Tags");

            migrationBuilder.DropColumn(
                name: "SiteId",
                table: "SubSites");

            migrationBuilder.DropColumn(
                name: "SiteId",
                table: "StorageStates");

            migrationBuilder.DropColumn(
                name: "Id",
                table: "Sites");

            migrationBuilder.DropColumn(
                name: "SiteId",
                table: "Scenes");

            migrationBuilder.DropColumn(
                name: "SiteId",
                table: "Performers");

            migrationBuilder.AddColumn<string>(
                name: "SiteUuid",
                table: "Tags",
                type: "TEXT",
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddColumn<string>(
                name: "SiteUuid",
                table: "SubSites",
                type: "TEXT",
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddColumn<string>(
                name: "SiteUuid",
                table: "StorageStates",
                type: "TEXT",
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddColumn<string>(
                name: "SiteUuid",
                table: "Scenes",
                type: "TEXT",
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddColumn<string>(
                name: "SiteUuid",
                table: "Performers",
                type: "TEXT",
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddPrimaryKey(
                name: "PK_Sites",
                table: "Sites",
                column: "Uuid");

            migrationBuilder.CreateIndex(
                name: "IX_Tags_SiteUuid",
                table: "Tags",
                column: "SiteUuid");

            migrationBuilder.CreateIndex(
                name: "IX_SubSites_SiteUuid",
                table: "SubSites",
                column: "SiteUuid");

            migrationBuilder.CreateIndex(
                name: "IX_StorageStates_SiteUuid",
                table: "StorageStates",
                column: "SiteUuid",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_Scenes_SiteUuid",
                table: "Scenes",
                column: "SiteUuid");

            migrationBuilder.CreateIndex(
                name: "IX_Performers_SiteUuid",
                table: "Performers",
                column: "SiteUuid");

            migrationBuilder.AddForeignKey(
                name: "FK_Performers_Sites_SiteUuid",
                table: "Performers",
                column: "SiteUuid",
                principalTable: "Sites",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_Scenes_Sites_SiteUuid",
                table: "Scenes",
                column: "SiteUuid",
                principalTable: "Sites",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_StorageStates_Sites_SiteUuid",
                table: "StorageStates",
                column: "SiteUuid",
                principalTable: "Sites",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_SubSites_Sites_SiteUuid",
                table: "SubSites",
                column: "SiteUuid",
                principalTable: "Sites",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_Tags_Sites_SiteUuid",
                table: "Tags",
                column: "SiteUuid",
                principalTable: "Sites",
                principalColumn: "Uuid",
                onDelete: ReferentialAction.Cascade);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Performers_Sites_SiteUuid",
                table: "Performers");

            migrationBuilder.DropForeignKey(
                name: "FK_Scenes_Sites_SiteUuid",
                table: "Scenes");

            migrationBuilder.DropForeignKey(
                name: "FK_StorageStates_Sites_SiteUuid",
                table: "StorageStates");

            migrationBuilder.DropForeignKey(
                name: "FK_SubSites_Sites_SiteUuid",
                table: "SubSites");

            migrationBuilder.DropForeignKey(
                name: "FK_Tags_Sites_SiteUuid",
                table: "Tags");

            migrationBuilder.DropIndex(
                name: "IX_Tags_SiteUuid",
                table: "Tags");

            migrationBuilder.DropIndex(
                name: "IX_SubSites_SiteUuid",
                table: "SubSites");

            migrationBuilder.DropIndex(
                name: "IX_StorageStates_SiteUuid",
                table: "StorageStates");

            migrationBuilder.DropPrimaryKey(
                name: "PK_Sites",
                table: "Sites");

            migrationBuilder.DropIndex(
                name: "IX_Scenes_SiteUuid",
                table: "Scenes");

            migrationBuilder.DropIndex(
                name: "IX_Performers_SiteUuid",
                table: "Performers");

            migrationBuilder.DropColumn(
                name: "SiteUuid",
                table: "Tags");

            migrationBuilder.DropColumn(
                name: "SiteUuid",
                table: "SubSites");

            migrationBuilder.DropColumn(
                name: "SiteUuid",
                table: "StorageStates");

            migrationBuilder.DropColumn(
                name: "SiteUuid",
                table: "Scenes");

            migrationBuilder.DropColumn(
                name: "SiteUuid",
                table: "Performers");

            migrationBuilder.AddColumn<int>(
                name: "SiteId",
                table: "Tags",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddColumn<int>(
                name: "SiteId",
                table: "SubSites",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddColumn<int>(
                name: "SiteId",
                table: "StorageStates",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddColumn<int>(
                name: "Id",
                table: "Sites",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0)
                .Annotation("Sqlite:Autoincrement", true);

            migrationBuilder.AddColumn<int>(
                name: "SiteId",
                table: "Scenes",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddColumn<int>(
                name: "SiteId",
                table: "Performers",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddPrimaryKey(
                name: "PK_Sites",
                table: "Sites",
                column: "Id");

            migrationBuilder.CreateIndex(
                name: "IX_Tags_SiteId",
                table: "Tags",
                column: "SiteId");

            migrationBuilder.CreateIndex(
                name: "IX_SubSites_SiteId",
                table: "SubSites",
                column: "SiteId");

            migrationBuilder.CreateIndex(
                name: "IX_StorageStates_SiteId",
                table: "StorageStates",
                column: "SiteId",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_Scenes_SiteId",
                table: "Scenes",
                column: "SiteId");

            migrationBuilder.CreateIndex(
                name: "IX_Performers_SiteId",
                table: "Performers",
                column: "SiteId");

            migrationBuilder.AddForeignKey(
                name: "FK_Performers_Sites_SiteId",
                table: "Performers",
                column: "SiteId",
                principalTable: "Sites",
                principalColumn: "Id",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_Scenes_Sites_SiteId",
                table: "Scenes",
                column: "SiteId",
                principalTable: "Sites",
                principalColumn: "Id",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_StorageStates_Sites_SiteId",
                table: "StorageStates",
                column: "SiteId",
                principalTable: "Sites",
                principalColumn: "Id",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_SubSites_Sites_SiteId",
                table: "SubSites",
                column: "SiteId",
                principalTable: "Sites",
                principalColumn: "Id",
                onDelete: ReferentialAction.Cascade);

            migrationBuilder.AddForeignKey(
                name: "FK_Tags_Sites_SiteId",
                table: "Tags",
                column: "SiteId",
                principalTable: "Sites",
                principalColumn: "Id",
                onDelete: ReferentialAction.Cascade);
        }
    }
}
