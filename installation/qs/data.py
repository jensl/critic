import sys
import os
import pwd
import grp
import subprocess
import json
import multiprocessing

import installation

def config(key):
    return "installation.config." + key
def system(key):
    return "installation.system." + key
def admin(key):
    return "installation.admin." + key
def database(key):
    return "installation.database." + key
def prereqs(key):
    return "installation.prereqs." + key
def paths(key):
    return "installation.paths." + key
def smtp(key):
    return "installation.smtp." + key
def extensions(key):
    return "installation.extensions." + key

def username():
    return pwd.getpwuid(os.getuid()).pw_name
def groupname():
    return grp.getgrgid(pwd.getpwuid(os.getuid()).pw_gid).gr_name

def which(name):
    return subprocess.check_output("which " + name, shell=True).strip()

def generate(arguments, database_path):
    data = { config("password_hash_schemes"): [installation.config.default_password_hash_scheme],
             config("default_password_hash_scheme"): installation.config.default_password_hash_scheme,
             config("minimum_password_hash_time"): installation.config.minimum_password_hash_time,
             config("minimum_rounds"): { installation.config.default_password_hash_scheme: 100 },
             config("auth_database"): "internal",
             system("username"): username(),
             system("email"): username() + "@localhost",
             system("groupname"): groupname(),
             admin("username"): username(),
             admin("email"): username() + "@localhost",
             admin("fullname"): username(),
             system("hostname"): "localhost",
             system("recipients"): arguments.system_recipient or [username() + "@localhost"],
             config("auth_mode"): "critic",
             config("session_type"): "cookie",
             config("allow_anonymous_user"): True,
             config("allow_user_registration"): True,
             config("verify_email_addresses"): arguments.testing,
             config("access_scheme"): "http",
             config("enable_access_tokens"): True,
             config("repository_url_types"): ["http"],
             config("default_encodings"): ["utf-8", "latin-1"],
             database("driver"): "sqlite",
             database("parameters"): { "database": database_path },
             config("is_development"): True,
             config("coverage_dir"): None,
             prereqs("python"): sys.executable,
             prereqs("git"): which("git"),
             prereqs("tar"): which("tar"),
             paths("etc_dir"): installation.paths.etc_dir,
             paths("install_dir"): installation.paths.install_dir,
             paths("data_dir"): installation.paths.data_dir,
             paths("cache_dir"): installation.paths.cache_dir,
             paths("log_dir"): installation.paths.log_dir,
             paths("run_dir"): installation.paths.run_dir,
             paths("git_dir"): installation.paths.git_dir,
             smtp("host"): arguments.smtp_host,
             smtp("port"): arguments.smtp_port,
             smtp("username"): json.dumps(arguments.smtp_username),
             smtp("password"): json.dumps(arguments.smtp_password),
             smtp("use_ssl"): False,
             smtp("use_starttls"): False,
             config("is_quickstart"): True,
             config("is_testing"): arguments.testing,
             config("ldap_url"): "",
             config("ldap_search_base"): "",
             config("ldap_create_user"): False,
             config("ldap_username_attribute"): "",
             config("ldap_fullname_attribute"): "",
             config("ldap_email_attribute"): "",
             config("ldap_cache_max_age"): 600,
             extensions("enabled"): False,
             extensions("critic_v8_jsshell"): "NOT_INSTALLED",
             extensions("default_flavor"): "js/v8",
             config("highlight.max_workers"): multiprocessing.cpu_count(),
             # Setting changeset.max_workers to 1 is a workaround for some race
             # conditions causing duplicate rows in (at least) the files table.
             config("changeset.max_workers"): 1,
             config("archive_review_branches"): True,
             config("web_server_integration"): "none" }

    def provider(name):
        prefix = "provider_%s." % name
        return { config(prefix + "enabled"): False,
                 config(prefix + "allow_user_registration"): False,
                 config(prefix + "verify_email_addresses"): False,
                 config(prefix + "client_id"): None,
                 config(prefix + "client_secret"): None,
                 config(prefix + "bypass_createuser"): False,
                 config(prefix + "redirect_uri"): None }

    data.update(provider("github"))
    data.update(provider("google"))

    return data
