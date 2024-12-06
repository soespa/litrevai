import os
import re
import sqlite3
from shutil import copyfile
import numpy as np
import pandas as pd
import tempfile

from litrevai.util import extract_year


class ZoteroConnector:

    def __init__(self, zotero_path: str | None = None):

        if not zotero_path:
            zotero_path = f'{os.environ["HOME"]}/Zotero'

        self.zotero_path = zotero_path

        filename = 'zotero.sqlite'

        sql_db = os.path.join(zotero_path, filename)

        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.sqlite')

        self.file_path = self.temp_file.name

        copyfile(sql_db, self.file_path)

        self.storage_path = os.path.join(zotero_path, 'storage')

    def __del__(self):
        self.temp_file.close()

    @property
    def df(self):
        items = self.items

        authors = self.authors

        def authors_as_list(group):
            s = group.sort_values('orderIndex')
            return (s['last_name'] + ', ' + s['first_name']).to_list()

        authors = authors.groupby('key').apply(authors_as_list).rename('author')
        df = items.join(authors)

        return df


    @property
    def libraries(self):
        conn = sqlite3.connect(self.file_path)

        sql_query = '''
        SELECT groups.groupID, groups.libraryID, groups.name FROM groups
        '''

        df = pd.read_sql(sql_query, conn).set_index('libraryID')

        df.loc[1, 'name'] = 'Personal'

        conn.close()

        return df


    @property
    def collections(self):

        conn = sqlite3.connect(self.file_path)

        sql_query = '''
SELECT items.key, collections.collectionID, collections.libraryID, collections.parentCollectionID, collections.collectionName FROM items
JOIN collectionItems ON items.itemID=collectionItems.itemID
JOIN collections ON collectionItems.collectionID=collections.collectionID;
        '''

        sql_query = '''
        SELECT collections.collectionID, collections.libraryID, collections.parentCollectionID, collections.collectionName FROM collections
        '''

        collections = pd.read_sql(sql_query, conn).set_index('collectionID')

        conn.close()

        libraries = self.libraries

        def get_path(row):
            parent = row['parentCollectionID']
            name = row['collectionName']
            library_id = row['libraryID']
            if pd.isna(parent):
                library = libraries.loc[int(library_id)]
                library_name = library['name']
                return os.path.join(library_name, name)
            else:
                parent_row = collections.loc[int(parent)]
                return os.path.join(get_path(parent_row), name)

        collections['collectionPath'] = collections.apply(get_path, axis=1)

        return collections


    @property
    def authors(self):

        conn = sqlite3.connect(self.file_path)

        sql_query = '''
                SELECT creators.creatorID, creators.first_name, creators.last_name FROM creators
                '''

        authors = pd.read_sql(sql_query, conn).set_index('creatorID')

        conn.close()

        return authors

    @property
    def items(self):

        conn = sqlite3.connect(self.file_path)

        sql_query = '''
        SELECT itemDataValues.value, fields.fieldName, items.key FROM items
        LEFT JOIN itemData ON items.itemID=itemData.itemID
        LEFT JOIN itemDataValues ON itemData.valueID=itemDataValues.valueID
        LEFT JOIN fields ON itemData.fieldID=fields.fieldID
        '''

        fields = pd.read_sql(sql_query, conn)

        fields = fields.pivot(columns='fieldName', index='key', values='value')

        fields = fields.drop(np.nan, axis=1)

        sql_query = '''
SELECT items.key, itemTypes.typeName, items.libraryID FROM items
LEFT JOIN itemTypes ON items.itemTypeID=itemTypes.itemTypeID
        '''


        items = pd.read_sql(sql_query, conn).set_index('key')

        items = items.join(fields)

        sql_query = '''
        SELECT items.key, parent.key AS parentKey, itemAttachments.contentType, itemAttachments.path
        FROM itemAttachments
        LEFT JOIN items ON itemAttachments.itemID=items.itemID
        LEFT JOIN items AS parent ON itemAttachments.parentItemID=parent.itemID
        WHERE itemAttachments.contentType in ('application/pdf') AND parentKey IS NOT NULL;
        '''

        attachments = pd.read_sql(sql_query, conn).set_index('key')

        storage_path = os.path.join(self.zotero_path, 'storage')

        def extract_filename(row):
            path = row['path']
            if type(path) is not str:
                return None
            match = re.search(r'storage:(.*.pdf)', path)
            if match is not None:
                path = os.path.join(storage_path, row.name, match.group(1))
                return path

        attachments['path'] = attachments.apply(extract_filename, axis=1)

        attachments = attachments.set_index('parentKey')

        items = items.join(attachments)

        items = items[~items['path'].isna()]

        items['year'] = items['date'].apply(extract_year)

        sql_query = '''
        SELECT items.key, collectionItems.collectionID, collectionItems.itemID FROM collectionItems
        LEFT JOIN items on items.itemID = collectionItems.itemID
        '''

        collections_items = pd.read_sql(sql_query, conn).groupby('key')['collectionID'].apply(lambda s: s.to_list())

        collections_items.name = 'collectionIDs'

        items = items.join(collections_items)

        sql_query = '''
                SELECT items.key, itemCreators.creatorID, itemCreators.itemID, itemCreators.orderIndex FROM itemCreators
                LEFT JOIN items on items.itemID = itemCreators.itemID
                '''


        creators_items = pd.read_sql(sql_query, conn).groupby('key').apply(
            lambda g: g.sort_values('orderIndex')['creatorID'].to_list(),
            include_groups=False
        )

        creators_items.name = 'creatorIDs'

        items = items.join(creators_items)

        conn.close()

        return items
