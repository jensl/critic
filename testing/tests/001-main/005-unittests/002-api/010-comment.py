# @dependency 001-main/003-self/100-reviewing/001-comments.basic.py

args = ["--review=r/100-reviewing/001-comment.basic"]

instance.unittest("api.comment", ["basic"], args)
