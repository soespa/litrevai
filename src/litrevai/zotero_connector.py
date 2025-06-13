import os
import re
import sqlite3
import tempfile
import pandas as pd
import numpy as np
from shutil import copyfile
from typing import Optional, List

from litrevai.util import extract_year


class ZoteroConnector:
    def __init__(self, like: Optional[str] = None, zotero_path: Optional[str] = None, include_types: List[str] | None = ['journalArticle', 'conferencePaper']):
        if not zotero_path:
            zotero_path = os.path.join(os.environ["HOME"], "Zotero")

        self.zotero_path = zotero_path
        self.include_types = include_types
        db_file = os.path.join(zotero_path, "zotero.sqlite")

        self.temp_file = tempfile.NamedTemporaryFile(mode="w+b", suffix=".sqlite", delete=False)
        copyfile(db_file, self.temp_file.name)
        self.file_path = self.temp_file.name
        self.conn = sqlite3.connect(self.file_path)
        self.storage_path = os.path.join(zotero_path, "storage")

        self.libraries = self._load_libraries()
        self.collections = self._load_collections()
        self.authors = self._load_authors()
        self.items = self._load_items()
        self.item_creators = self._load_item_creators()
        self.item_collections = self._load_item_collections()

        if like:
            self._filter_items_by_regex(like)

    def __del__(self):
        self.conn.close()
        self.temp_file.close()

    def _load_libraries(self):
        query = "SELECT groups.groupID, groups.libraryID, groups.name FROM groups"
        df = pd.read_sql(query, self.conn).set_index("libraryID")
        df.loc[1, "name"] = "Personal"
        return df

    def _load_collections(self):
        query = "SELECT collectionID, libraryID, parentCollectionID, collectionName FROM collections"
        collections = pd.read_sql(query, self.conn).set_index("collectionID")

        def build_path(row):
            parent = row['parentCollectionID']
            name = row['collectionName']
            library_id = row['libraryID']
            if pd.isna(parent):
                library_name = self.libraries.loc[int(library_id)]['name']
                return os.path.join(library_name, name)
            else:
                parent_row = collections.loc[int(parent)]
                return os.path.join(build_path(parent_row), name)

        collections['collectionPath'] = collections.apply(build_path, axis=1)
        return collections

    def _load_authors(self):
        query = "SELECT creatorID, firstName, lastName FROM creators"
        return pd.read_sql(query, self.conn).set_index("creatorID")

    def _load_items(self):
        # Load core metadata
        fields_query = """
            SELECT itemDataValues.value, fields.fieldName, items.key
            FROM items
            LEFT JOIN itemData ON items.itemID=itemData.itemID
            LEFT JOIN itemDataValues ON itemData.valueID=itemDataValues.valueID
            LEFT JOIN fields ON itemData.fieldID=fields.fieldID
        """
        fields = pd.read_sql(fields_query, self.conn)
        fields = fields.pivot(columns="fieldName", index="key", values="value").dropna(axis=1, how='all')

        item_types_query = """
            SELECT items.key, itemTypes.typeName, items.libraryID FROM items
            LEFT JOIN itemTypes ON items.itemTypeID=itemTypes.itemTypeID
        """
        items = pd.read_sql(item_types_query, self.conn).set_index("key")
        items = items.join(fields)

        # Apply include_types filter
        if self.include_types is not None:
            items = items[items['typeName'].isin(self.include_types)]

        # Load file attachments
        attachments_query = """
            SELECT items.key, parent.key AS parentKey, itemAttachments.contentType, itemAttachments.path
            FROM itemAttachments
            LEFT JOIN items ON itemAttachments.itemID=items.itemID
            LEFT JOIN items AS parent ON itemAttachments.parentItemID=parent.itemID
            WHERE itemAttachments.contentType IN ('application/pdf') AND parentKey IS NOT NULL
        """
        attachments = pd.read_sql(attachments_query, self.conn).set_index("key")
        attachments['path'] = attachments.apply(self._extract_path, axis=1)
        attachments = attachments.set_index('parentKey')
        items = items.join(attachments).dropna(subset=["path"])

        # Extract year
        items['year'] = items['date'].apply(extract_year)

        return items

    def _load_item_collections(self):
        query = """
            SELECT items.key, collectionItems.collectionID
            FROM collectionItems
            LEFT JOIN items ON items.itemID=collectionItems.itemID
        """
        return pd.read_sql(query, self.conn)

    def _load_item_creators(self):
        query = """
            SELECT items.key, itemCreators.creatorID, itemCreators.orderIndex
            FROM itemCreators
            LEFT JOIN items ON items.itemID=itemCreators.itemID
        """
        return pd.read_sql(query, self.conn)

    def _filter_items_by_regex(self, pattern: str):
        """
        Filter items, collections, creators, authors, and libraries based on a regex applied to collectionPath.
        """

        # Find collections whose path matches the regex pattern
        regex = re.compile(pattern)
        matching_collections = self.collections[
            self.collections['collectionPath'].apply(lambda p: bool(regex.search(p)))]
        self.collection_ids = matching_collections.index.tolist()

        # Filter item_collections to only relevant collections
        self.item_collections = self.item_collections[
            self.item_collections['collectionID'].isin(self.collection_ids)
        ]

        # Restrict items to those belonging to filtered collections
        valid_item_keys = self.item_collections['key'].unique()
        self.items = self.items[self.items.index.isin(valid_item_keys)]

        # Filter item_creators to only filtered items
        self.item_creators = self.item_creators[self.item_creators['key'].isin(self.items.index)]

        # Filter authors to only those linked to filtered items
        valid_author_ids = self.item_creators['creatorID'].unique()
        self.authors = self.authors[self.authors.index.isin(valid_author_ids)]

        # Filter libraries to only those containing filtered items
        valid_library_ids = self.items['libraryID'].unique()
        self.libraries = self.libraries[self.libraries.index.isin(valid_library_ids)]

        # Finally restrict collections itself
        self.collections = self.collections[self.collections.index.isin(self.collection_ids)]

    def _extract_path(self, row):
        path = row['path']
        if not isinstance(path, str):
            return None
        match = re.search(r"storage:(.*\.pdf)", path)
        if match:
            return os.path.join(self.storage_path, row.name, match.group(1))
        return None