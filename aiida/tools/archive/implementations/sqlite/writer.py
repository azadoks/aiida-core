# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""AiiDA archive writer implementation."""
from datetime import datetime
import functools
import hashlib
from io import BytesIO
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, BinaryIO, Dict, List, Optional, Set, Union
import zipfile

from archive_path import NOTSET, ZipPath, extract_file_in_zip, read_file_in_zip
from sqlalchemy import insert, inspect
from sqlalchemy.exc import IntegrityError as SqlaIntegrityError
from sqlalchemy.future.engine import Connection

from aiida import get_version
from aiida.common.exceptions import IntegrityError
from aiida.common.hashing import chunked_file_hash
from aiida.common.progress_reporter import get_progress_reporter
from aiida.orm.entities import EntityTypes
from aiida.tools.archive.abstract import ArchiveFormatAbstract, ArchiveWriterAbstract
from aiida.tools.archive.exceptions import CorruptArchive, IncompatibleArchiveVersionError

from . import backend as db
from .common import DB_FILENAME, META_FILENAME, REPO_FOLDER, create_sqla_engine

try:
    from typing import Literal  # pylint: disable=ungrouped-imports
except ImportError:
    # Python <3.8 backport
    from typing_extensions import Literal  # type: ignore


@functools.lru_cache(maxsize=10)
def _get_model_from_entity(entity_type: EntityTypes):
    """Return the Sqlalchemy model and column names corresponding to the given entity."""
    model = {
        EntityTypes.USER: db.DbUser,
        EntityTypes.AUTHINFO: db.DbAuthInfo,
        EntityTypes.GROUP: db.DbGroup,
        EntityTypes.NODE: db.DbNode,
        EntityTypes.COMMENT: db.DbComment,
        EntityTypes.COMPUTER: db.DbComputer,
        EntityTypes.LOG: db.DbLog,
        EntityTypes.LINK: db.DbLink,
        EntityTypes.GROUP_NODE: db.DbGroupNodes
    }[entity_type]
    mapper = inspect(model).mapper
    column_names = {col.name for col in mapper.c.values()}
    return model, column_names


class ArchiveWriterSqlZip(ArchiveWriterAbstract):
    """AiiDA archive writer implementation."""

    meta_name = META_FILENAME
    db_name = DB_FILENAME

    def __init__(
        self,
        path: Union[str, Path],
        fmt: ArchiveFormatAbstract,
        *,
        mode: Literal['x', 'w', 'a'] = 'x',
        compression: int = 6,
        work_dir: Optional[Path] = None,
        _debug: bool = False,
        _enforce_foreign_keys: bool = True,
    ):
        super().__init__(path, fmt, mode=mode, compression=compression)
        self._init_work_dir = work_dir
        self._in_context = False
        self._enforce_foreign_keys = _enforce_foreign_keys
        self._debug = _debug
        self._metadata: Dict[str, Any] = {}
        self._central_dir: Dict[str, Any] = {}
        self._deleted_paths: Set[str] = set()
        self._zip_path: Optional[ZipPath] = None
        self._work_dir: Optional[Path] = None
        self._conn: Optional[Connection] = None

    def _assert_in_context(self):
        if not self._in_context:
            raise AssertionError('Not in context')

    def __enter__(self) -> 'ArchiveWriterSqlZip':
        """Start writing to the archive"""
        self._metadata = {
            'export_version': self._format.latest_version,
            'aiida_version': get_version(),
            'key_format': 'sha256',
            'compression': self._compression,
        }
        self._work_dir = Path(tempfile.mkdtemp()) if self._init_work_dir is None else Path(self._init_work_dir)
        self._central_dir = {}
        self._zip_path = ZipPath(
            self._path,
            mode=self._mode,
            compression=zipfile.ZIP_DEFLATED if self._compression else zipfile.ZIP_STORED,
            compresslevel=self._compression,
            info_order=(self.meta_name, self.db_name),
            name_to_info=self._central_dir,
        )
        engine = create_sqla_engine(
            self._work_dir / self.db_name, enforce_foreign_keys=self._enforce_foreign_keys, echo=self._debug
        )
        db.ArchiveDbBase.metadata.create_all(engine)
        self._conn = engine.connect()
        self._in_context = True
        return self

    def __exit__(self, *args, **kwargs):
        """Finalise the archive"""
        if self._conn:
            self._conn.commit()
            self._conn.close()
        assert self._work_dir is not None
        with (self._work_dir / self.db_name).open('rb') as handle:
            self._stream_binary(self.db_name, handle)
        self._stream_binary(
            self.meta_name,
            BytesIO(json.dumps(self._metadata).encode('utf8')),
            compression=0,  # the metadata is small, so no benefit for compression
        )
        if self._zip_path:
            self._zip_path.close()
            self._central_dir = {}
        if self._work_dir is not None and self._init_work_dir is None:
            shutil.rmtree(self._work_dir, ignore_errors=True)
        self._zip_path = self._work_dir = self._conn = None
        self._in_context = False

    def update_metadata(self, data: Dict[str, Any], overwrite: bool = False) -> None:
        if not overwrite and set(self._metadata).intersection(set(data)):
            raise ValueError(f'Cannot overwrite existing keys: {set(self._metadata).intersection(set(data))}')
        self._metadata.update(data)

    def bulk_insert(
        self,
        entity_type: EntityTypes,
        rows: List[Dict[str, Any]],
        allow_defaults: bool = False,
    ) -> None:
        if not rows:
            return
        self._assert_in_context()
        assert self._conn is not None
        model, col_keys = _get_model_from_entity(entity_type)
        if allow_defaults:
            for row in rows:
                if not col_keys.issuperset(row):
                    raise IntegrityError(
                        f'Incorrect fields given for {entity_type}: {set(row)} not subset of {col_keys}'
                    )
        else:
            for row in rows:
                if set(row) != col_keys:
                    raise IntegrityError(f'Incorrect fields given for {entity_type}: {set(row)} != {col_keys}')
        try:
            self._conn.execute(insert(model.__table__), rows)
        except SqlaIntegrityError as exc:
            raise IntegrityError(f'Inserting {entity_type}: {exc}') from exc

    def _stream_binary(
        self,
        name: str,
        handle: BinaryIO,
        *,
        buffer_size: Optional[int] = None,
        compression: Optional[int] = None,
        comment: Optional[bytes] = None,
    ) -> None:
        """Add a binary stream to the archive.

        :param buffer_size: Number of bytes to buffer
        :param compression: Override global compression level
        :param comment: A binary meta comment about the object
        """
        self._assert_in_context()
        assert self._zip_path is not None
        kwargs: Dict[str, Any] = {'comment': NOTSET if comment is None else comment}
        if compression is not None:
            kwargs['compression'] = zipfile.ZIP_DEFLATED if compression else zipfile.ZIP_STORED
            kwargs['level'] = compression
        with self._zip_path.joinpath(name).open('wb', **kwargs) as zip_handle:
            if buffer_size is None:
                shutil.copyfileobj(handle, zip_handle)
            else:
                shutil.copyfileobj(handle, zip_handle, length=buffer_size)

    def put_object(self, stream: BinaryIO, *, buffer_size: Optional[int] = None, key: Optional[str] = None) -> str:
        if key is None:
            key = chunked_file_hash(stream, hashlib.sha256)
            stream.seek(0)
        if f'{REPO_FOLDER}/{key}' not in self._central_dir:
            self._stream_binary(f'{REPO_FOLDER}/{key}', stream, buffer_size=buffer_size)
        return key

    def delete_object(self, key: str) -> None:
        raise IOError(f'Cannot delete objects in {self._mode!r} mode')


class ArchiveAppenderSqlZip(ArchiveWriterSqlZip):
    """AiiDA archive appender implementation."""

    def delete_object(self, key: str) -> None:
        self._assert_in_context()
        if f'{REPO_FOLDER}/{key}' in self._central_dir:
            raise IOError(f'Cannot delete object {key!r} that has been added in the same append context')
        self._deleted_paths.add(f'{REPO_FOLDER}/{key}')

    def __enter__(self) -> 'ArchiveAppenderSqlZip':
        """Start appending to the archive"""
        # the file should already exist
        if not self._path.exists():
            raise FileNotFoundError(f'Archive {self._path} does not exist')
        # the file should be an archive with the correct version
        version = self._format.read_version(self._path)
        if not version == self._format.latest_version:
            raise IncompatibleArchiveVersionError(
                f'Archive is version {version!r} but expected {self._format.latest_version!r}'
            )
        # load the metadata
        self._metadata = json.loads(read_file_in_zip(self._path, META_FILENAME, 'utf8', search_limit=4))
        # overwrite metadata
        self._metadata['mtime'] = datetime.now().isoformat()
        self._metadata['compression'] = self._compression
        # create the work folder
        self._work_dir = Path(tempfile.mkdtemp()) if self._init_work_dir is None else Path(self._init_work_dir)
        # create a new zip file in the work folder
        self._central_dir = {}
        self._deleted_paths = set()
        self._zip_path = ZipPath(
            self._work_dir / 'archive.zip',
            mode='w',
            compression=zipfile.ZIP_DEFLATED if self._compression else zipfile.ZIP_STORED,
            compresslevel=self._compression,
            info_order=(self.meta_name, self.db_name),
            name_to_info=self._central_dir,
        )
        # extract the database to the work folder
        db_file = self._work_dir / self.db_name
        with db_file.open('wb') as handle:
            try:
                extract_file_in_zip(self.path, DB_FILENAME, handle, search_limit=4)
            except Exception as exc:
                raise CorruptArchive(f'database could not be read: {exc}') from exc
        # open a connection to the database
        engine = create_sqla_engine(
            self._work_dir / self.db_name, enforce_foreign_keys=self._enforce_foreign_keys, echo=self._debug
        )
        # to-do could check that the database has correct schema:
        # https://docs.sqlalchemy.org/en/14/core/reflection.html#reflecting-all-tables-at-once
        self._conn = engine.connect()
        self._in_context = True
        return self

    def __exit__(self, *args, **kwargs):
        """Finalise the archive"""
        if self._conn:
            self._conn.commit()
            self._conn.close()
        assert self._work_dir is not None
        # write the database and metadata to the new archive
        with (self._work_dir / self.db_name).open('rb') as handle:
            self._stream_binary(self.db_name, handle)
        self._stream_binary(
            self.meta_name,
            BytesIO(json.dumps(self._metadata).encode('utf8')),
            compression=0,
        )
        # finalise the new archive
        self._copy_old_zip_files()
        if self._zip_path is not None:
            self._zip_path.close()
        self._central_dir = {}
        self._deleted_paths = set()
        # now move it to the original location
        self._path.unlink()
        shutil.move(self._work_dir / 'archive.zip', self._path)  # type: ignore[arg-type]
        if self._init_work_dir is None:
            shutil.rmtree(self._work_dir, ignore_errors=True)
        self._zip_path = self._work_dir = self._conn = None
        self._in_context = False

    def _copy_old_zip_files(self):
        """Copy the old archive content to the new one (omitting any amended or deleted files)"""
        assert self._zip_path is not None
        with ZipPath(self._path, mode='r') as old_archive:
            length = sum(1 for _ in old_archive.glob('**/*', include_virtual=False))
            with get_progress_reporter()(desc='Writing amended archive', total=length) as progress:
                for subpath in old_archive.glob('**/*', include_virtual=False):
                    if subpath.at in self._central_dir or subpath.at in self._deleted_paths:
                        continue
                    new_path_sub = self._zip_path.joinpath(subpath.at)
                    if subpath.is_dir():
                        new_path_sub.mkdir(exist_ok=True)
                    else:
                        with subpath.open('rb') as handle:
                            with new_path_sub.open('wb') as new_handle:
                                shutil.copyfileobj(handle, new_handle)
                    progress.update()
