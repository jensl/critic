from critic.api.filediff import (
    PartType,
    PART_TYPE_NEUTRAL,
    PART_TYPE_OPERATOR,
    PART_TYPE_IDENTIFIER,
    PART_TYPE_KEYWORD,
    PART_TYPE_CHARACTER,
    PART_TYPE_STRING,
    PART_TYPE_COMMENT,
    PART_TYPE_INTEGER,
    PART_TYPE_FLOAT,
    PART_TYPE_PREPROCESSING,
)


class TokenTypes:
    Whitespace: PartType = PART_TYPE_NEUTRAL
    Operator: PartType = PART_TYPE_OPERATOR
    Identifier: PartType = PART_TYPE_IDENTIFIER
    Keyword: PartType = PART_TYPE_KEYWORD
    Character: PartType = PART_TYPE_CHARACTER
    String: PartType = PART_TYPE_STRING
    Comment: PartType = PART_TYPE_COMMENT
    Integer: PartType = PART_TYPE_INTEGER
    Float: PartType = PART_TYPE_FLOAT
    Preprocessing: PartType = PART_TYPE_PREPROCESSING
