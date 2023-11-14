using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class InitialCreate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "sites",
                columns: table => new
                {
                    uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    short_name = table.Column<string>(type: "text", nullable: false),
                    name = table.Column<string>(type: "text", nullable: false),
                    url = table.Column<string>(type: "text", nullable: false),
                    username = table.Column<string>(type: "text", nullable: false),
                    password = table.Column<string>(type: "text", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_sites", x => x.uuid);
                });

            migrationBuilder.CreateTable(
                name: "performers",
                columns: table => new
                {
                    uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    short_name = table.Column<string>(type: "text", nullable: true),
                    name = table.Column<string>(type: "text", nullable: false),
                    url = table.Column<string>(type: "text", nullable: true),
                    site_uuid = table.Column<Guid>(type: "uuid", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_performers", x => x.uuid);
                    table.ForeignKey(
                        name: "fk_performers_sites_site_temp_id",
                        column: x => x.site_uuid,
                        principalTable: "sites",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "storage_states",
                columns: table => new
                {
                    uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    storage_state = table.Column<string>(type: "text", nullable: false),
                    site_uuid = table.Column<Guid>(type: "uuid", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_storage_states", x => x.uuid);
                    table.ForeignKey(
                        name: "fk_storage_states_sites_site_uuid",
                        column: x => x.site_uuid,
                        principalTable: "sites",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "sub_sites",
                columns: table => new
                {
                    uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    short_name = table.Column<string>(type: "text", nullable: false),
                    name = table.Column<string>(type: "text", nullable: false),
                    site_uuid = table.Column<Guid>(type: "uuid", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_sub_sites", x => x.uuid);
                    table.ForeignKey(
                        name: "fk_sub_sites_sites_site_uuid",
                        column: x => x.site_uuid,
                        principalTable: "sites",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "tags",
                columns: table => new
                {
                    uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    short_name = table.Column<string>(type: "text", nullable: true),
                    name = table.Column<string>(type: "text", nullable: false),
                    url = table.Column<string>(type: "text", nullable: true),
                    site_uuid = table.Column<Guid>(type: "uuid", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_tags", x => x.uuid);
                    table.ForeignKey(
                        name: "fk_tags_sites_site_uuid",
                        column: x => x.site_uuid,
                        principalTable: "sites",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "releases",
                columns: table => new
                {
                    uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    release_date = table.Column<DateOnly>(type: "date", nullable: false),
                    short_name = table.Column<string>(type: "text", nullable: false),
                    name = table.Column<string>(type: "text", nullable: false),
                    url = table.Column<string>(type: "text", nullable: false),
                    description = table.Column<string>(type: "text", nullable: false),
                    duration = table.Column<double>(type: "double precision", nullable: false),
                    created = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    last_updated = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    available_files = table.Column<string>(type: "jsonb", nullable: false),
                    json_document = table.Column<string>(type: "jsonb", nullable: false),
                    site_uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    sub_site_uuid = table.Column<Guid>(type: "uuid", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_releases", x => x.uuid);
                    table.ForeignKey(
                        name: "fk_releases_sites_site_temp_id1",
                        column: x => x.site_uuid,
                        principalTable: "sites",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "fk_releases_sub_sites_sub_site_temp_id",
                        column: x => x.sub_site_uuid,
                        principalTable: "sub_sites",
                        principalColumn: "uuid");
                });

            migrationBuilder.CreateTable(
                name: "downloads",
                columns: table => new
                {
                    uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    downloaded_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    file_type = table.Column<string>(type: "text", nullable: false),
                    content_type = table.Column<string>(type: "text", nullable: false),
                    variant = table.Column<string>(type: "text", nullable: false),
                    available_file = table.Column<string>(type: "jsonb", nullable: false),
                    original_filename = table.Column<string>(type: "text", nullable: true),
                    saved_filename = table.Column<string>(type: "text", nullable: true),
                    release_uuid = table.Column<Guid>(type: "uuid", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_downloads", x => x.uuid);
                    table.ForeignKey(
                        name: "fk_downloads_releases_release_temp_id",
                        column: x => x.release_uuid,
                        principalTable: "releases",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "release_entity_site_performer_entity",
                columns: table => new
                {
                    performers_uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    releases_uuid = table.Column<Guid>(type: "uuid", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_release_entity_site_performer_entity", x => new { x.performers_uuid, x.releases_uuid });
                    table.ForeignKey(
                        name: "fk_release_entity_site_performer_entity_performers_performers_",
                        column: x => x.performers_uuid,
                        principalTable: "performers",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "fk_release_entity_site_performer_entity_releases_releases_uuid",
                        column: x => x.releases_uuid,
                        principalTable: "releases",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "release_entity_site_tag_entity",
                columns: table => new
                {
                    releases_uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    tags_uuid = table.Column<Guid>(type: "uuid", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_release_entity_site_tag_entity", x => new { x.releases_uuid, x.tags_uuid });
                    table.ForeignKey(
                        name: "fk_release_entity_site_tag_entity_releases_releases_uuid",
                        column: x => x.releases_uuid,
                        principalTable: "releases",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "fk_release_entity_site_tag_entity_tags_tags_uuid",
                        column: x => x.tags_uuid,
                        principalTable: "tags",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "ix_downloads_release_uuid",
                table: "downloads",
                column: "release_uuid");

            migrationBuilder.CreateIndex(
                name: "ix_performers_site_uuid",
                table: "performers",
                column: "site_uuid");

            migrationBuilder.CreateIndex(
                name: "ix_release_entity_site_performer_entity_releases_uuid",
                table: "release_entity_site_performer_entity",
                column: "releases_uuid");

            migrationBuilder.CreateIndex(
                name: "ix_release_entity_site_tag_entity_tags_uuid",
                table: "release_entity_site_tag_entity",
                column: "tags_uuid");

            migrationBuilder.CreateIndex(
                name: "ix_releases_site_uuid",
                table: "releases",
                column: "site_uuid");

            migrationBuilder.CreateIndex(
                name: "ix_releases_sub_site_uuid",
                table: "releases",
                column: "sub_site_uuid");

            migrationBuilder.CreateIndex(
                name: "ix_storage_states_site_uuid",
                table: "storage_states",
                column: "site_uuid",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_sub_sites_site_uuid",
                table: "sub_sites",
                column: "site_uuid");

            migrationBuilder.CreateIndex(
                name: "ix_tags_site_uuid",
                table: "tags",
                column: "site_uuid");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "downloads");

            migrationBuilder.DropTable(
                name: "release_entity_site_performer_entity");

            migrationBuilder.DropTable(
                name: "release_entity_site_tag_entity");

            migrationBuilder.DropTable(
                name: "storage_states");

            migrationBuilder.DropTable(
                name: "performers");

            migrationBuilder.DropTable(
                name: "releases");

            migrationBuilder.DropTable(
                name: "tags");

            migrationBuilder.DropTable(
                name: "sub_sites");

            migrationBuilder.DropTable(
                name: "sites");
        }
    }
}
