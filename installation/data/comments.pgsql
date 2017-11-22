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

CREATE OR REPLACE FUNCTION chaincomments(chain_id INTEGER) RETURNS INTEGER AS
$$
DECLARE
  result INTEGER;
BEGIN
  SELECT COUNT(*) INTO STRICT result FROM comments WHERE chain=chain_id AND state='current';
  RETURN result;
END;
$$
LANGUAGE 'plpgsql';

CREATE OR REPLACE FUNCTION chainunread(chain_id INTEGER, user_id INTEGER) RETURNS INTEGER AS
$$
DECLARE
  result INTEGER;
BEGIN
  SELECT COUNT(*) INTO STRICT result FROM commentstoread JOIN comments ON (comments.id=commentstoread.comment) WHERE comments.chain=chain_id AND comments.state='current' AND commentstoread.uid=user_id;
  RETURN result;
END;
$$
LANGUAGE 'plpgsql';
