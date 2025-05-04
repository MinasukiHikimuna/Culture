# Scrapy commands

Standard run:

```
scrapy crawl hegre
```

Force update with the following command. This will force the spider to update all releases, even if they already exist and all the files are downloaded.

```
scrapy crawl hegre -s FORCE_UPDATE=true
```
