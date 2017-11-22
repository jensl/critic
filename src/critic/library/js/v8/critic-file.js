/* -*- mode: js; indent-tabs-mode: nil -*-

 Copyright 2013 Jens Lindström, Opera Software ASA

 Licensed under the Apache License, Version 2.0 (the "License"); you may not
 use this file except in compliance with the License.  You may obtain a copy of
 the License at

   http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 License for the specific language governing permissions and limitations under
 the License.

*/

"use strict";

/* Constructor for internal use.  External code (and in practice most internal
   code as well) uses CriticFile.find() to create or find previously created
   CriticFile objects.  That function is also exposed as the File "constructor"
   externally, to emulate the real constructors old behavior. */
function CriticFile(data)
{
  var result;

  if ("id" in data)
  {
    result = db.execute("SELECT id, path FROM files WHERE id=%d", data.id)[0];
    if (!result)
      throw CriticError(format("%s: invalid file ID", data.id));
  }
  else if ("path" in data)
  {
    result = db.execute("SELECT id, path FROM files WHERE MD5(path)=MD5(%s)", data.path)[0];
    if (!result)
      throw CriticError(format("%s: no such file", data.path));
  }
  else
    throw CriticError("invalid use; expected data.id or data.path");

  this.id = result.id;
  this.path = result.path;

  /* CriticFile has sub-classes whose constructors will first call this function
     and then extend the object further.  If that's the case, we don't freeze
     the object (expecting the sub-class constructor to do so instead.) */
  var is_subclass = Object.getPrototypeOf(this) !== CriticFile.prototype;

  if (!is_subclass)
    Object.freeze(this);
}

Object.defineProperties(
  CriticFile.prototype,
  {
    toString: { value: function () { return this.path; }, writable: true, configurable: true },
    valueOf: { value: function () { return this.id; }, writable: true, configurable: true }
  }
);

var file_cache_by_id = {};
var file_cache_by_path = {};

CriticFile.find = function (path_or_id)
  {
    var cached;

    if (typeof path_or_id == "string")
    {
      /* Normalize forward slashes in the path so that the cache lookup always
         uses the same format. */
      var path = path_or_id.replace(/^\/+|\/+(?=\/)|\/+$/g, "");

      if (cached = file_cache_by_path[path])
        return cached;
      else
        return file_cache_by_path[path] = new CriticFile({ path: path });
    }
    else
    {
      var id = ~~path_or_id;

      if (cached = file_cache_by_id[id])
        return cached;
      else
        return file_cache_by_path[id] = new CriticFile({ id: id });
    }
  };

/* Externally, CriticFile.find() doubles as the File constructor, so set its
   prototype property to make the instanceof operator work as expected. */
CriticFile.find.prototype = CriticFile.prototype;
/* It also needs to reference itself... */
CriticFile.find.find = CriticFile.find;

function CriticFileVersion(repository, file, mode, size, sha1, data)
{
  CriticFile.call(this, { path: file });

  this.repository = repository;
  this.mode = mode;
  this.size = size;
  this.sha1 = sha1;

  var self = this;
  var review = null;
  var bytes, lines;
  var commentChains = null;

  if (data)
    if (data.review)
      review = data.review;

  function isBinary(data)
  {
    /* Check if the file appears to be binary.

       Using information from .gitattributes would be nice, but git doesn't seem
       to have a command that directly exposes information from it, and parsing
       it here is quite sub-optimal.  And if the file really is binary then this
       function will find that out too typically, so using .gitattributes is
       mostly and optimization anyway.

       This code is essentially a copy of git's heuristics for determining if a
       file is binary, in convert.c::gather_stats() and convert.c::is_binary(). */

    var printable = 0, nonprintable = 0;

    for (var index = 0; index < data.length; ++index)
    {
      var byte = data[index];

      if (byte < 32)
      {
        switch (byte)
        {
        case 0:
          return true;

        case 8:
        case 9:
        case 10:
        case 12:
        case 13:
        case 27:
          ++printable;
          break;

        default:
          ++nonprintable;
        }
      }
      else if (byte == 127)
        ++nonprintable;
      else
        ++printable;
    }

    return (printable >> 7) < nonprintable;
  }

  function getBytes()
  {
    if (bytes === void 0)
      bytes = self.repository.fetch(self.sha1).data;
    return bytes;
  }

  function getLines()
  {
    if (lines === void 0)
    {
      /* Re-use 'bytes' if set, but if not don't set 'bytes' since that keeps
         the array (which might be huge) alive longer than what is probably
         necessary. */
      var data = bytes || self.repository.fetch(self.sha1).data;

      if (isBinary(data))
        lines = null;
      else
      {
        var source = data.decode();

        lines = source.split(/\r\n|\n/g);

        /* If the file ends in a line-break (as it typically should) the last
           element in the array will be empty.  We don't want to keep that
           empty element; it will only make it seem like there's an empty line
           at the end of the file. */
        if (lines.length && !lines[lines.length - 1])
          lines.pop();

        Object.freeze(lines);
      }
    }

    return lines;
  }

  function getCommentChains()
  {
    if (!commentChains)
    {
      commentChains = [];

      var result = db.execute("SELECT DISTINCT id, first_line, last_line FROM commentchains JOIN commentchainlines ON (chain=id) WHERE commentchains.state!='draft' AND commentchainlines.state!='draft' AND review=%d AND sha1=%s ORDER BY first_line ASC, last_line ASC", review.id, self.sha1);

      for (var index = 0; index < result.length; ++index)
        commentChains.push(new CriticCommentChain(result[index].id, { review: review }));

      Object.freeze(commentChains);
    }

    return commentChains;
  }

  Object.defineProperties(this, { lines: { get: getLines, enumerable: true },
                                  bytes: { get: getBytes, enumerable: true }});

  if (review)
    Object.defineProperty(this, "commentChains", { get: getCommentChains, enumerable: true });
  else
    this.commentChains = null;

  var is_subclass = Object.getPrototypeOf(this) !== CriticFileVersion.prototype;

  if (!is_subclass)
    Object.freeze(this);
}

CriticFileVersion.prototype = Object.create(CriticFile.prototype);
