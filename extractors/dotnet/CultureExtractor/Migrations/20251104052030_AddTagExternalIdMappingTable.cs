using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class AddTagExternalIdMappingTable : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "tag_external_ids",
                columns: table => new
                {
                    uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    external_id = table.Column<string>(type: "text", nullable: false),
                    created = table.Column<DateTime>(type: "timestamp", nullable: false),
                    last_updated = table.Column<DateTime>(type: "timestamp", nullable: false),
                    tag_uuid = table.Column<Guid>(type: "uuid", nullable: false),
                    target_system_uuid = table.Column<Guid>(type: "uuid", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_tag_external_ids", x => x.uuid);
                    table.ForeignKey(
                        name: "fk_tag_external_ids_tags_tag_temp_id",
                        column: x => x.tag_uuid,
                        principalTable: "tags",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "fk_tag_external_ids_target_systems_target_system_temp_id4",
                        column: x => x.target_system_uuid,
                        principalTable: "target_systems",
                        principalColumn: "uuid",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "ix_tag_external_ids_tag_uuid_target_system_uuid",
                table: "tag_external_ids",
                columns: new[] { "tag_uuid", "target_system_uuid" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_tag_external_ids_target_system_uuid_external_id",
                table: "tag_external_ids",
                columns: new[] { "target_system_uuid", "external_id" },
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "tag_external_ids");
        }
    }
}
