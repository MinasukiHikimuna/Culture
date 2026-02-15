# %%
import os
import sys
from pathlib import Path

import polars as pl
from dotenv import load_dotenv


sys.path.append(str(Path.cwd().parent))

import libraries.client_culture_extractor as client_culture_extractor


load_dotenv()

# Culture Extractor
user = os.environ.get("CE_DB_USERNAME")
pw = os.environ.get("CE_DB_PASSWORD")
host = os.environ.get("CE_DB_HOST")
port = os.environ.get("CE_DB_PORT")
db = os.environ.get("CE_DB_NAME")

connection_string = f"dbname={db} user={user} password={pw} host={host} port={port}"

culture_extractor_client = client_culture_extractor.ClientCultureExtractor(
    connection_string
)


# %%
sites = culture_extractor_client.get_sites()
sites


# %%
schema = culture_extractor_client.get_database_schema()
schema.write_json()

# %%
culture_extractor_client.get_sub_sites().filter(pl.col("ce_sites_name") == "Sexy Hub")


# %%
culture_extractor_client.create_site("whynotbi", "Why Not Bi", "https://whynotbi.com")
