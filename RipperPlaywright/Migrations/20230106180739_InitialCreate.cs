using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace RipperPlaywright.Migrations
{
    /// <inheritdoc />
    public partial class InitialCreate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "Sites",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    ShortName = table.Column<string>(type: "TEXT", nullable: false),
                    Name = table.Column<string>(type: "TEXT", nullable: false),
                    Url = table.Column<string>(type: "TEXT", nullable: false),
                    Username = table.Column<string>(type: "TEXT", nullable: false),
                    Password = table.Column<string>(type: "TEXT", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Sites", x => x.Id);
                    table.UniqueConstraint("AK_Sites_Name", x => x.Name);
                    table.UniqueConstraint("AK_Sites_ShortName", x => x.ShortName);
                    table.UniqueConstraint("AK_Sites_Url", x => x.Url);
                });

            migrationBuilder.CreateTable(
                name: "GalleryEntity",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    ReleaseDate = table.Column<DateOnly>(type: "TEXT", nullable: false),
                    ShortName = table.Column<string>(type: "TEXT", nullable: false),
                    Name = table.Column<string>(type: "TEXT", nullable: false),
                    Url = table.Column<string>(type: "TEXT", nullable: false),
                    Pictures = table.Column<int>(type: "INTEGER", nullable: false),
                    SiteId = table.Column<int>(type: "INTEGER", nullable: false)
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

            migrationBuilder.CreateTable(
                name: "Scenes",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    ReleaseDate = table.Column<DateOnly>(type: "TEXT", nullable: false),
                    ShortName = table.Column<string>(type: "TEXT", nullable: false),
                    Name = table.Column<string>(type: "TEXT", nullable: false),
                    Url = table.Column<string>(type: "TEXT", nullable: false),
                    Description = table.Column<string>(type: "TEXT", nullable: false),
                    Duration = table.Column<double>(type: "REAL", nullable: false),
                    SiteId = table.Column<int>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Scenes", x => x.Id);
                    table.UniqueConstraint("AK_Scenes_Name", x => x.Name);
                    table.UniqueConstraint("AK_Scenes_ShortName", x => x.ShortName);
                    table.UniqueConstraint("AK_Scenes_Url", x => x.Url);
                    table.ForeignKey(
                        name: "FK_Scenes_Sites_SiteId",
                        column: x => x.SiteId,
                        principalTable: "Sites",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "StorageStates",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    StorageState = table.Column<string>(type: "TEXT", nullable: false),
                    SiteId = table.Column<int>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_StorageStates", x => x.Id);
                    table.ForeignKey(
                        name: "FK_StorageStates_Sites_SiteId",
                        column: x => x.SiteId,
                        principalTable: "Sites",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "Performers",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    ShortName = table.Column<string>(type: "TEXT", nullable: false),
                    Name = table.Column<string>(type: "TEXT", nullable: false),
                    Url = table.Column<string>(type: "TEXT", nullable: false),
                    SiteId = table.Column<int>(type: "INTEGER", nullable: false),
                    GalleryEntityId = table.Column<int>(type: "INTEGER", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Performers", x => x.Id);
                    table.UniqueConstraint("AK_Performers_Name", x => x.Name);
                    table.UniqueConstraint("AK_Performers_ShortName", x => x.ShortName);
                    table.UniqueConstraint("AK_Performers_Url", x => x.Url);
                    table.ForeignKey(
                        name: "FK_Performers_GalleryEntity_GalleryEntityId",
                        column: x => x.GalleryEntityId,
                        principalTable: "GalleryEntity",
                        principalColumn: "Id");
                    table.ForeignKey(
                        name: "FK_Performers_Sites_SiteId",
                        column: x => x.SiteId,
                        principalTable: "Sites",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "Tags",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    ShortName = table.Column<string>(type: "TEXT", nullable: false),
                    Name = table.Column<string>(type: "TEXT", nullable: false),
                    Url = table.Column<string>(type: "TEXT", nullable: false),
                    SiteId = table.Column<int>(type: "INTEGER", nullable: false),
                    GalleryEntityId = table.Column<int>(type: "INTEGER", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Tags", x => x.Id);
                    table.UniqueConstraint("AK_Tags_Name", x => x.Name);
                    table.UniqueConstraint("AK_Tags_ShortName", x => x.ShortName);
                    table.UniqueConstraint("AK_Tags_Url", x => x.Url);
                    table.ForeignKey(
                        name: "FK_Tags_GalleryEntity_GalleryEntityId",
                        column: x => x.GalleryEntityId,
                        principalTable: "GalleryEntity",
                        principalColumn: "Id");
                    table.ForeignKey(
                        name: "FK_Tags_Sites_SiteId",
                        column: x => x.SiteId,
                        principalTable: "Sites",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "SceneEntitySitePerformerEntity",
                columns: table => new
                {
                    PerformersId = table.Column<int>(type: "INTEGER", nullable: false),
                    ScenesId = table.Column<int>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_SceneEntitySitePerformerEntity", x => new { x.PerformersId, x.ScenesId });
                    table.ForeignKey(
                        name: "FK_SceneEntitySitePerformerEntity_Performers_PerformersId",
                        column: x => x.PerformersId,
                        principalTable: "Performers",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_SceneEntitySitePerformerEntity_Scenes_ScenesId",
                        column: x => x.ScenesId,
                        principalTable: "Scenes",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "SceneEntitySiteTagEntity",
                columns: table => new
                {
                    ScenesId = table.Column<int>(type: "INTEGER", nullable: false),
                    TagsId = table.Column<int>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_SceneEntitySiteTagEntity", x => new { x.ScenesId, x.TagsId });
                    table.ForeignKey(
                        name: "FK_SceneEntitySiteTagEntity_Scenes_ScenesId",
                        column: x => x.ScenesId,
                        principalTable: "Scenes",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_SceneEntitySiteTagEntity_Tags_TagsId",
                        column: x => x.TagsId,
                        principalTable: "Tags",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_GalleryEntity_SiteId",
                table: "GalleryEntity",
                column: "SiteId");

            migrationBuilder.CreateIndex(
                name: "IX_Performers_GalleryEntityId",
                table: "Performers",
                column: "GalleryEntityId");

            migrationBuilder.CreateIndex(
                name: "IX_Performers_SiteId",
                table: "Performers",
                column: "SiteId");

            migrationBuilder.CreateIndex(
                name: "IX_SceneEntitySitePerformerEntity_ScenesId",
                table: "SceneEntitySitePerformerEntity",
                column: "ScenesId");

            migrationBuilder.CreateIndex(
                name: "IX_SceneEntitySiteTagEntity_TagsId",
                table: "SceneEntitySiteTagEntity",
                column: "TagsId");

            migrationBuilder.CreateIndex(
                name: "IX_Scenes_SiteId",
                table: "Scenes",
                column: "SiteId");

            migrationBuilder.CreateIndex(
                name: "IX_StorageStates_SiteId",
                table: "StorageStates",
                column: "SiteId",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_Tags_GalleryEntityId",
                table: "Tags",
                column: "GalleryEntityId");

            migrationBuilder.CreateIndex(
                name: "IX_Tags_SiteId",
                table: "Tags",
                column: "SiteId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "SceneEntitySitePerformerEntity");

            migrationBuilder.DropTable(
                name: "SceneEntitySiteTagEntity");

            migrationBuilder.DropTable(
                name: "StorageStates");

            migrationBuilder.DropTable(
                name: "Performers");

            migrationBuilder.DropTable(
                name: "Scenes");

            migrationBuilder.DropTable(
                name: "Tags");

            migrationBuilder.DropTable(
                name: "GalleryEntity");

            migrationBuilder.DropTable(
                name: "Sites");
        }
    }
}
