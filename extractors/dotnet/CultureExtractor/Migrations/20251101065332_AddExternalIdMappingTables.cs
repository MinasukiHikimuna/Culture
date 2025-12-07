using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class AddExternalIdMappingTables : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "target_systems",
                columns: table => new
                {
                    uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    name = table.Column<string>(type: "text", nullable: false),
                    description = table.Column<string>(type: "text", nullable: true),
                    created = table.Column<DateTime>(type: "timestamp", nullable: false),
                    last_updated = table.Column<DateTime>(type: "timestamp", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_target_systems", x => x.uuid);
                });

            migrationBuilder.CreateTable(
                name: "performer_external_ids",
                columns: table => new
                {
                    uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    external_id = table.Column<string>(type: "text", nullable: false),
                    created = table.Column<DateTime>(type: "timestamp", nullable: false),
                    last_updated = table.Column<DateTime>(type: "timestamp", nullable: false),
                    performer_uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    target_system_uuid = table.Column<Guid>(type: "uuid", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_performer_external_ids", x => x.uuid);
                    table.ForeignKey(
                        name: "fk_performer_external_ids_performers_performer_temp_id",
                        column: x => x.performer_uuid,
                        principalTable: "performers",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "fk_performer_external_ids_target_systems_target_system_temp_id",
                        column: x => x.target_system_uuid,
                        principalTable: "target_systems",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "release_external_ids",
                columns: table => new
                {
                    uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    external_id = table.Column<string>(type: "text", nullable: false),
                    created = table.Column<DateTime>(type: "timestamp", nullable: false),
                    last_updated = table.Column<DateTime>(type: "timestamp", nullable: false),
                    release_uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    target_system_uuid = table.Column<Guid>(type: "uuid", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_release_external_ids", x => x.uuid);
                    table.ForeignKey(
                        name: "fk_release_external_ids_releases_release_temp_id1",
                        column: x => x.release_uuid,
                        principalTable: "releases",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "fk_release_external_ids_target_systems_target_system_temp_id1",
                        column: x => x.target_system_uuid,
                        principalTable: "target_systems",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "site_external_ids",
                columns: table => new
                {
                    uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    external_id = table.Column<string>(type: "text", nullable: false),
                    created = table.Column<DateTime>(type: "timestamp", nullable: false),
                    last_updated = table.Column<DateTime>(type: "timestamp", nullable: false),
                    site_uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    target_system_uuid = table.Column<Guid>(type: "uuid", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_site_external_ids", x => x.uuid);
                    table.ForeignKey(
                        name: "fk_site_external_ids_sites_site_temp_id2",
                        column: x => x.site_uuid,
                        principalTable: "sites",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "fk_site_external_ids_target_systems_target_system_temp_id2",
                        column: x => x.target_system_uuid,
                        principalTable: "target_systems",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "sub_site_external_ids",
                columns: table => new
                {
                    uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    external_id = table.Column<string>(type: "text", nullable: false),
                    created = table.Column<DateTime>(type: "timestamp", nullable: false),
                    last_updated = table.Column<DateTime>(type: "timestamp", nullable: false),
                    sub_site_uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    target_system_uuid = table.Column<Guid>(type: "uuid", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_sub_site_external_ids", x => x.uuid);
                    table.ForeignKey(
                        name: "fk_sub_site_external_ids_sub_sites_sub_site_temp_id1",
                        column: x => x.sub_site_uuid,
                        principalTable: "sub_sites",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "fk_sub_site_external_ids_target_systems_target_system_temp_id3",
                        column: x => x.target_system_uuid,
                        principalTable: "target_systems",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "ix_performer_external_ids_performer_uuid_target_system_uuid",
                table: "performer_external_ids",
                columns: new[] { "performer_uuid", "target_system_uuid" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_performer_external_ids_target_system_uuid_external_id",
                table: "performer_external_ids",
                columns: new[] { "target_system_uuid", "external_id" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_release_external_ids_release_uuid_target_system_uuid",
                table: "release_external_ids",
                columns: new[] { "release_uuid", "target_system_uuid" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_release_external_ids_target_system_uuid_external_id",
                table: "release_external_ids",
                columns: new[] { "target_system_uuid", "external_id" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_site_external_ids_site_uuid_target_system_uuid",
                table: "site_external_ids",
                columns: new[] { "site_uuid", "target_system_uuid" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_site_external_ids_target_system_uuid_external_id",
                table: "site_external_ids",
                columns: new[] { "target_system_uuid", "external_id" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_sub_site_external_ids_sub_site_uuid_target_system_uuid",
                table: "sub_site_external_ids",
                columns: new[] { "sub_site_uuid", "target_system_uuid" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_sub_site_external_ids_target_system_uuid_external_id",
                table: "sub_site_external_ids",
                columns: new[] { "target_system_uuid", "external_id" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_target_systems_name",
                table: "target_systems",
                column: "name",
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "performer_external_ids");

            migrationBuilder.DropTable(
                name: "release_external_ids");

            migrationBuilder.DropTable(
                name: "site_external_ids");

            migrationBuilder.DropTable(
                name: "sub_site_external_ids");

            migrationBuilder.DropTable(
                name: "target_systems");
        }
    }
}
