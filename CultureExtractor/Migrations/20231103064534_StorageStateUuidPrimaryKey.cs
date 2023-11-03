using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CultureExtractor.Migrations
{
    /// <inheritdoc />
    public partial class StorageStateUuidPrimaryKey : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropPrimaryKey(
                name: "PK_StorageStates",
                table: "StorageStates");

            migrationBuilder.DropColumn(
                name: "Id",
                table: "StorageStates");

            migrationBuilder.AddPrimaryKey(
                name: "PK_StorageStates",
                table: "StorageStates",
                column: "Uuid");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropPrimaryKey(
                name: "PK_StorageStates",
                table: "StorageStates");

            migrationBuilder.AddColumn<int>(
                name: "Id",
                table: "StorageStates",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0)
                .Annotation("Sqlite:Autoincrement", true);

            migrationBuilder.AddPrimaryKey(
                name: "PK_StorageStates",
                table: "StorageStates",
                column: "Id");
        }
    }
}
