using UUIDNext;

namespace CultureExtractor;

public static class UuidGenerator
{
    public static Guid Generate()
    {
        return Uuid.NewDatabaseFriendly(Database.SQLite);
    }
}
