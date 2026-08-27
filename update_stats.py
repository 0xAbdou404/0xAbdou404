#!/usr/bin/env python3
"""
update_stats.py  -  Fetch live GitHub stats, then re-render the profile card.

Designed to run in CI (see .github/workflows/build.yaml), but you can run it
locally too if you export a token first:

    export ACCESS_TOKEN=github_pat_xxx      # a GitHub personal access token
    export USER_NAME=0xAbdou404             # optional, defaults to 0xAbdou404
    python update_stats.py

What it does:
  1. Queries the GitHub GraphQL API for your public/owned repos, stars,
     followers, total commits, and lines of code (added / deleted / net).
  2. Writes those numbers into the "stats" block of config.json
     (everything else in config.json is left untouched).
  3. Runs generate.py to rebuild assets/dark_mode.svg + light_mode.svg.

Lines-of-code + commit counting is cached in cache/<hash>.txt so repeat runs
only re-walk repositories whose commit count changed. Commit that cache file
so the cache survives between runs.

The GitHub-API fetching logic is adapted from Andrew6rant's today.py (the
profile this card is modeled on). The rendering is our own pycairo generator.
"""
import os
import sys
import json
import time
import hashlib
import subprocess

import requests

HERE = os.path.dirname(os.path.abspath(__file__))

TOKEN = os.environ.get("ACCESS_TOKEN")
if not TOKEN:
    raise SystemExit(
        "\nACCESS_TOKEN is not set.\n\n"
        "Create a GitHub personal access token and export it first, e.g.\n"
        "  export ACCESS_TOKEN=github_pat_xxx\n"
        "In CI this comes from the repo secret named ACCESS_TOKEN.\n"
    )
USER_NAME = os.environ.get("USER_NAME", "0xAbdou404")
HEADERS = {"authorization": "token " + TOKEN}

COMMENT_SIZE = 7            # lines of free-text comment kept at the top of the cache
OWNER_ID = None            # set in main(); used to count only commits authored by you
QUERY_COUNT = {"user_getter": 0, "follower_getter": 0, "graph_repos_stars": 0,
               "recursive_loc": 0, "loc_query": 0}


def query_count(name):
    QUERY_COUNT[name] += 1


def cache_filename():
    return os.path.join(HERE, "cache",
                        hashlib.sha256(USER_NAME.encode("utf-8")).hexdigest() + ".txt")


def simple_request(func_name, query, variables):
    r = requests.post("https://api.github.com/graphql",
                      json={"query": query, "variables": variables}, headers=HEADERS)
    if r.status_code == 200:
        return r
    raise Exception(func_name, "failed with", r.status_code, r.text, QUERY_COUNT)


# --------------------------------------------------------------------------
# account + followers
# --------------------------------------------------------------------------
def user_getter(username):
    """Return ({'id': ...}, createdAt) for the user."""
    query_count("user_getter")
    query = """
    query($login: String!){
        user(login: $login) { id createdAt }
    }"""
    r = simple_request(user_getter.__name__, query, {"login": username})
    data = r.json()["data"]["user"]
    return {"id": data["id"]}, data["createdAt"]


def follower_getter(username):
    query_count("follower_getter")
    query = """
    query($login: String!){
        user(login: $login) { followers { totalCount } }
    }"""
    r = simple_request(follower_getter.__name__, query, {"login": username})
    return int(r.json()["data"]["user"]["followers"]["totalCount"])


# --------------------------------------------------------------------------
# repos + stars
# --------------------------------------------------------------------------
def graph_repos_stars(count_type, owner_affiliation, cursor=None):
    """Return the total repository count, or the summed star count."""
    query_count("graph_repos_stars")
    query = """
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 100, after: $cursor, ownerAffiliations: $owner_affiliation) {
                totalCount
                edges { node { ... on Repository { nameWithOwner stargazers { totalCount } } } }
                pageInfo { endCursor hasNextPage }
            }
        }
    }"""
    variables = {"owner_affiliation": owner_affiliation, "login": USER_NAME, "cursor": cursor}
    r = simple_request(graph_repos_stars.__name__, query, variables)
    repos = r.json()["data"]["user"]["repositories"]
    if count_type == "repos":
        return repos["totalCount"]
    if count_type == "stars":
        return stars_counter(repos["edges"])


def stars_counter(data):
    total = 0
    for node in data:
        if node.get("node") is None:
            continue
        stargazers = node["node"].get("stargazers")
        if stargazers is None:
            continue
        total += stargazers["totalCount"]
    return total


# --------------------------------------------------------------------------
# lines of code + commits (cached, walks each repo's history)
# --------------------------------------------------------------------------
def recursive_loc(owner, repo_name, data, cache_comment,
                  addition_total=0, deletion_total=0, my_commits=0, cursor=None):
    query_count("recursive_loc")
    query = """
    query ($repo_name: String!, $owner: String!, $cursor: String) {
        repository(name: $repo_name, owner: $owner) {
            defaultBranchRef { target { ... on Commit {
                history(first: 100, after: $cursor) {
                    totalCount
                    edges { node { ... on Commit { committedDate }
                        author { user { id } } deletions additions } }
                    pageInfo { endCursor hasNextPage }
                }
            } } }
        }
    }"""
    variables = {"repo_name": repo_name, "owner": owner, "cursor": cursor}
    r = requests.post("https://api.github.com/graphql",
                      json={"query": query, "variables": variables}, headers=HEADERS)
    if r.status_code == 200:
        if r.json()["data"]["repository"]["defaultBranchRef"] is not None:
            history = r.json()["data"]["repository"]["defaultBranchRef"]["target"]["history"]
            return loc_counter_one_repo(owner, repo_name, data, cache_comment, history,
                                        addition_total, deletion_total, my_commits)
        return 0
    force_close_file(data, cache_comment)
    if r.status_code == 403:
        raise Exception("Too many requests in a short amount of time!\n"
                        "You've hit the non-documented anti-abuse limit!")
    raise Exception("recursive_loc() failed with", r.status_code, r.text, QUERY_COUNT)


def loc_counter_one_repo(owner, repo_name, data, cache_comment, history,
                         addition_total, deletion_total, my_commits):
    for node in history["edges"]:
        if node["node"]["author"]["user"] == OWNER_ID:
            my_commits += 1
            addition_total += node["node"]["additions"]
            deletion_total += node["node"]["deletions"]
    if history["edges"] == [] or not history["pageInfo"]["hasNextPage"]:
        return addition_total, deletion_total, my_commits
    return recursive_loc(owner, repo_name, data, cache_comment,
                         addition_total, deletion_total, my_commits,
                         history["pageInfo"]["endCursor"])


def loc_query(owner_affiliation, comment_size=0, force_cache=False, cursor=None, edges=None):
    query_count("loc_query")
    if edges is None:
        edges = []
    query = """
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 60, after: $cursor, ownerAffiliations: $owner_affiliation) {
                edges { node { ... on Repository {
                    nameWithOwner
                    defaultBranchRef { target { ... on Commit { history { totalCount } } } }
                } } }
                pageInfo { endCursor hasNextPage }
            }
        }
    }"""
    variables = {"owner_affiliation": owner_affiliation, "login": USER_NAME, "cursor": cursor}
    r = simple_request(loc_query.__name__, query, variables)
    repos = r.json()["data"]["user"]["repositories"]
    if repos["pageInfo"]["hasNextPage"]:
        edges += repos["edges"]
        return loc_query(owner_affiliation, comment_size, force_cache,
                         repos["pageInfo"]["endCursor"], edges)
    return cache_builder(edges + repos["edges"], comment_size, force_cache)


def cache_builder(edges, comment_size, force_cache, loc_add=0, loc_del=0):
    cached = True
    filename = cache_filename()
    try:
        with open(filename, "r") as f:
            data = f.readlines()
    except FileNotFoundError:
        data = []
        if comment_size > 0:
            for _ in range(comment_size):
                data.append("This line is a comment block. Write whatever you want here.\n")
        with open(filename, "w") as f:
            f.writelines(data)

    if len(data) - comment_size != len(edges) or force_cache:
        cached = False
        flush_cache(edges, filename, comment_size)
        with open(filename, "r") as f:
            data = f.readlines()

    cache_comment = data[:comment_size]
    data = data[comment_size:]
    for index in range(len(edges)):
        repo_hash, commit_count, *__ = data[index].split()
        if repo_hash == hashlib.sha256(edges[index]["node"]["nameWithOwner"].encode("utf-8")).hexdigest():
            try:
                if int(commit_count) != edges[index]["node"]["defaultBranchRef"]["target"]["history"]["totalCount"]:
                    owner, repo_name = edges[index]["node"]["nameWithOwner"].split("/")
                    loc = recursive_loc(owner, repo_name, data, cache_comment)
                    data[index] = (repo_hash + " "
                                   + str(edges[index]["node"]["defaultBranchRef"]["target"]["history"]["totalCount"])
                                   + " " + str(loc[2]) + " " + str(loc[0]) + " " + str(loc[1]) + "\n")
            except TypeError:  # empty repo (no defaultBranchRef)
                data[index] = repo_hash + " 0 0 0 0\n"
    with open(filename, "w") as f:
        f.writelines(cache_comment)
        f.writelines(data)
    for line in data:
        loc = line.split()
        loc_add += int(loc[3])
        loc_del += int(loc[4])
    return [loc_add, loc_del, loc_add - loc_del, cached]


def flush_cache(edges, filename, comment_size):
    with open(filename, "r") as f:
        data = []
        if comment_size > 0:
            data = f.readlines()[:comment_size]
    with open(filename, "w") as f:
        f.writelines(data)
        for node in edges:
            f.write(hashlib.sha256(node["node"]["nameWithOwner"].encode("utf-8")).hexdigest() + " 0 0 0 0\n")


def force_close_file(data, cache_comment):
    filename = cache_filename()
    with open(filename, "w") as f:
        f.writelines(cache_comment)
        f.writelines(data)
    print("Error while writing cache; partial data saved to", filename)


def commit_counter(comment_size):
    total = 0
    with open(cache_filename(), "r") as f:
        data = f.readlines()[comment_size:]
    for line in data:
        total += int(line.split()[2])
    return total


# --------------------------------------------------------------------------
# write config.json + render
# --------------------------------------------------------------------------
def render(stats):
    config_path = os.path.join(HERE, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["stats"] = stats
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("Wrote stats to config.json:", stats)
    subprocess.run([sys.executable, os.path.join(HERE, "generate.py")], cwd=HERE, check=True)


def main():
    global OWNER_ID
    t0 = time.perf_counter()
    os.makedirs(os.path.join(HERE, "cache"), exist_ok=True)

    user_data, _acc_date = user_getter(USER_NAME)
    OWNER_ID = user_data

    # LOC across everything you own or collaborate on (cached).
    total_loc = loc_query(["OWNER", "COLLABORATOR", "ORGANIZATION_MEMBER"], COMMENT_SIZE)
    commits = commit_counter(COMMENT_SIZE)
    stars = graph_repos_stars("stars", ["OWNER"])
    repos = graph_repos_stars("repos", ["OWNER"])
    followers = follower_getter(USER_NAME)

    add_loc, del_loc, net_loc, was_cached = total_loc
    stats = {
        "repos": "{:,}".format(repos),
        "stars": "{:,}".format(stars),
        "commits": "{:,}".format(commits),
        "followers": "{:,}".format(followers),
        "loc": "{:,}".format(net_loc),
        "added": "{:,}".format(add_loc),
        "deleted": "{:,}".format(del_loc),
    }
    render(stats)

    print("LOC cache {}used.".format("" if was_cached else "re-built, not "))
    print("GitHub GraphQL API calls:", sum(QUERY_COUNT.values()), QUERY_COUNT)
    print("Total time: {:.2f}s".format(time.perf_counter() - t0))


if __name__ == "__main__":
    main()
