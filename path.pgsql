-- -*- mode: sql -*-
--
-- Copyright 2012 Jens Lindström, Opera Software ASA
--
-- Licensed under the Apache License, Version 2.0 (the "License"); you may not
-- use this file except in compliance with the License.  You may obtain a copy of
-- the License at
--
--   http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
-- WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
-- License for the specific language governing permissions and limitations under
-- the License.

-- Returns a single-column table containing the IDs of each directory in the
-- file's path, with the file's immediate containing directory first and the
-- directory at the root last.  The root directory (ID=zero) is not included.
CREATE OR REPLACE FUNCTION filepath(file INTEGER) RETURNS TABLE (directory_out INTEGER) AS
$$
BEGIN
  SELECT files.directory INTO STRICT directory_out FROM files WHERE files.id=file;

  WHILE directory_out != 0 LOOP
    RETURN NEXT;
    SELECT directories.directory INTO STRICT directory_out FROM directories WHERE directories.id=directory_out;
  END LOOP;

  RETURN;
END
$$
LANGUAGE 'plpgsql';

-- Returns a single-column table containing the IDs of each directory in the
-- directory's path, with the directory's immediate containing directory first
-- and the directory at the root last.  Neither the directory itself nor the
-- root directory (ID=zero) is not included.
CREATE OR REPLACE FUNCTION directorypath(directory_in INTEGER) RETURNS TABLE (directory_out INTEGER) AS
$$
BEGIN
  SELECT directories.directory INTO STRICT directory_out FROM directories WHERE directories.id=directory_in;

  WHILE directory_out != 0 LOOP
    RETURN NEXT;
    SELECT directories.directory INTO STRICT directory_out FROM directories WHERE directories.id=directory_out;
  END LOOP;

  RETURN;
END
$$
LANGUAGE 'plpgsql';

-- Returns a single-column table containing the IDs of every directory that has
-- this directory in its path (as returned by the directorypath() function.)
-- The order is undefined except that parent directories come before all of
-- their sub-directories.
CREATE OR REPLACE FUNCTION subdirectories(directory_in INTEGER) RETURNS TABLE (directory_out INTEGER) AS
$$
BEGIN
  FOR directory_out IN SELECT directories.id FROM directories WHERE directories.directory=directory_in LOOP
    RETURN NEXT;
    RETURN QUERY SELECT recursive.directory FROM subdirectories(directory_out) AS recursive;
  END LOOP;

  RETURN;
END
$$
LANGUAGE 'plpgsql';

-- Returns a single-column table containing the IDs of every file that has this
-- directory in its path (as returned by the filepath() function.)  The order is
-- undefined except that files in parent directories come before any files in
-- those directories' sub-directories.
CREATE OR REPLACE FUNCTION containedfiles(directory_in INTEGER) RETURNS TABLE (file_out INTEGER) AS
$$
DECLARE
  directory_id INTEGER;
BEGIN
  RETURN QUERY SELECT files.id FROM files WHERE files.directory=directory_in;
  FOR directory_id IN SELECT directories.id FROM directories WHERE directories.directory=directory_in LOOP
    RETURN QUERY SELECT recursive.file_out FROM containedfiles(directory_id) AS recursive;
  END LOOP;

  RETURN;
END;
$$
LANGUAGE 'plpgsql';

-- Returns a file's full path name, with no leading '/'.
CREATE OR REPLACE FUNCTION fullfilename(file_in INTEGER) RETURNS TEXT AS
$$
DECLARE
  result TEXT;
BEGIN
  SELECT fulldirectoryname(files.directory) || files.name INTO result FROM files WHERE files.id=file_in;
  RETURN result;
END;
$$
LANGUAGE 'plpgsql';

-- Returns a directory's full path name, with no leading '/' but with a trailing
-- '/'.  If the argument is zero, the empty string is returned.
CREATE OR REPLACE FUNCTION fulldirectoryname(directory_in INTEGER) RETURNS TEXT AS
$$
DECLARE
  result TEXT;
BEGIN
  IF directory_in = 0 THEN
    result := '';
  ELSE
    SELECT fulldirectoryname(directories.directory) || directories.name || '/' INTO result FROM directories WHERE directories.id=directory_in;
  END IF;
  RETURN result;
END;
$$
LANGUAGE 'plpgsql';

-- Returns a file ID such that <path> = fullfilename(<id>) is true.  If no such
-- file ID exists, NULL is returned.  Leading '/' are stripped from the path
-- argument.
CREATE OR REPLACE FUNCTION findfile(path TEXT) RETURNS INTEGER AS
$$
DECLARE
  directory_name TEXT;
  directory_id INTEGER;
  stripped_path TEXT;
  file_name TEXT;
  result INTEGER;
BEGIN
  stripped_path := TRIM(LEADING '/' FROM path);
  file_name := SUBSTRING(stripped_path FROM '[^/]+$');

  IF file_name IS NULL OR file_name = stripped_path THEN
    directory_id := 0;
  ELSE
    directory_name := SUBSTRING(stripped_path FROM 1 FOR CHARACTER_LENGTH(stripped_path) - (CHARACTER_LENGTH(file_name) + 1));
    directory_id := finddirectory(directory_name);
  END IF;

  SELECT files.id INTO result FROM files WHERE files.directory=directory_id AND files.name=file_name;

  RETURN result;
END;
$$
LANGUAGE 'plpgsql';

-- Returns a directory ID such that <path>||'/' = fulldirectoryname(<id>) is
-- true.  If no such directory ID exists, NULL is returned.  Leading and
-- trailing '/' are stripped from the path argument.
CREATE OR REPLACE FUNCTION finddirectory(path TEXT) RETURNS INTEGER AS
$$
DECLARE
  directory_name TEXT;
  directory_id INTEGER;
  stripped_path TEXT;
  base_name TEXT;
  result INTEGER;
BEGIN
  stripped_path := TRIM(BOTH '/' FROM path);
  base_name := SUBSTRING(stripped_path FROM '[^/]+$');

  IF base_name IS NULL OR base_name = stripped_path THEN
    directory_id := 0;
  ELSE
    directory_name := SUBSTRING(stripped_path FROM 1 FOR CHARACTER_LENGTH(stripped_path) - (CHARACTER_LENGTH(base_name) + 1));
    directory_id := finddirectory(directory_name);
  END IF;

  SELECT directories.id INTO result FROM directories WHERE directories.directory=directory_id AND directories.name=base_name;

  RETURN result;
END;
$$
LANGUAGE 'plpgsql';
